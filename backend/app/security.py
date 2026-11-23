import base64
import hashlib
import hmac
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def _secret_key() -> str:
    secret = os.getenv("SECRET_KEY")
    if secret:
        return secret
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("SECRET_KEY must be configured in production")
    return "local-development-key-change-before-deploy"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.urlsafe_b64encode(salt + digest).decode("ascii")


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, value = encoded.split("$", 1)
        if algorithm != "scrypt":
            return False
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        salt, expected = decoded[:16], decoded[16:]
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    serializer = URLSafeTimedSerializer(_secret_key(), salt="compra-juegos-auth-v1")
    return serializer.dumps({"sub": user.id, "role": user.role})


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Inicia sesión para continuar",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    serializer = URLSafeTimedSerializer(_secret_key(), salt="compra-juegos-auth-v1")
    try:
        payload = serializer.loads(
            credentials.credentials, max_age=int(os.getenv("TOKEN_TTL_SECONDS", "3600"))
        )
        user_id = payload.get("sub")
    except (BadSignature, SignatureExpired, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La cuenta está dada de baja",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol admin")
    return user
