# app/auth/tokens.py
from datetime import datetime, timedelta
from typing import Optional
import jwt
from app.auth.jwt_bearer import SECRET_KEY, ALGORITHM


def create_verification_token(email: str, expires_minutes: Optional[int] = 60):
    payload = {"sub": email}
    if expires_minutes is not None:
        expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
        payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_verification_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None