"""Shared authentication and ownership dependencies."""
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from devforge.db.models import User
from devforge.db.session import get_session
from devforge.utils.security import read_session_token


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),  # noqa: B008
) -> User:
    token = request.cookies.get("devforge_session")
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = session.get(User, read_session_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user
