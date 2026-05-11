from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY="qZoFqTYFZKNo_zr8FTeZ9Ah7GmhR9xHfKjHHNH5lA9G7Ld9MlzGBk3KQbPvzq9fj-jRHqrfzR1DdCZ9_JjvUPA"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: int = 60):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)