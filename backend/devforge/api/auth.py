"""Registration, login, and logout using an HttpOnly signed session cookie."""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from devforge.api.dependencies import get_current_user
from devforge.config import settings
from devforge.db.models import User
from devforge.db.session import get_session
from devforge.utils.security import create_session_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE_NAME = "devforge_session"


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Enter a valid email address")
        return normalized


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, httponly=True,
        secure=settings.auth_cookie_secure, samesite="lax", max_age=settings.auth_session_hours * 3600,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    credentials: Credentials,
    response: Response,
    session: Session = Depends(get_session),  # noqa: B008
) -> UserOut:
    if session.exec(select(User).where(User.email == credentials.email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=credentials.email, password_hash=hash_password(credentials.password))
    # Validate signing configuration before persisting an account. A missing secret
    # must never leave a newly registered user unable to establish a session.
    token = create_session_token(user.id)
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    session.refresh(user)
    _set_session(response, token)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login(
    credentials: Credentials,
    response: Response,
    session: Session = Depends(get_session),  # noqa: B008
) -> UserOut:
    user = session.exec(select(User).where(User.email == credentials.email)).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    _set_session(response, create_session_token(user.id))
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def current_user(user: User = Depends(get_current_user)) -> UserOut:  # noqa: B008
    return UserOut.model_validate(user)
