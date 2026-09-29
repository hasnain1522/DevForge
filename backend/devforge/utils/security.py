"""Password hashing and signed, expiring session tokens."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException, status

from devforge.config import settings

PASSWORD_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: str) -> str:
    secret = _auth_secret()
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": user_id,
        "iat": now,
        "exp": now + settings.auth_session_hours * 3600,
        "iss": "devforge",
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = _b64(hmac.new(secret, unsigned.encode(), hashlib.sha256).digest())
    return f"{unsigned}.{signature}"


def read_session_token(token: str) -> str:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(_auth_secret(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            raise ValueError("Invalid signature")
        claims = json.loads(_unb64(payload))
        if claims.get("iss") != "devforge" or int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError("Expired or invalid token")
        return str(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def _auth_secret() -> bytes:
    secret = settings.auth_secret
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured; set AUTH_SECRET to a random value of at least 32 characters",
        )
    return secret.encode()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
