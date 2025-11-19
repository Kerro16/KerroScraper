from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from dotenv import load_dotenv
import redis
import os
import base64

load_dotenv()

security = HTTPBearer()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
)

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise ValueError("JWT_SECRET is not set in environment variables")

def decode_secret(secret: str) -> bytes:
    if not secret:
        raise ValueError("JWT secret is None")

    try:
        return base64.b64decode(secret)
    except Exception:
        pass

    try:
        return bytes.fromhex(secret)
    except Exception:
        pass

    return secret.encode('utf-8')

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    if redis_client.get(token):
        raise HTTPException(status_code=401, detail="Token in blacklist")

    try:
        secret_key = decode_secret(JWT_SECRET)

        payload = jwt.decode(token, secret_key, algorithms=["HS384"])
        username = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Token missing subject")
        return username
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")