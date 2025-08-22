from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# --- Configuration ---
# In a real production environment, this secret key should be loaded securely,
# for example from an environment variable or a secret management system.
SECRET_KEY = os.environ.get("CRAWLER_SECRET_KEY", "a_very_secret_key_for_development_only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Token valid for 24 hours

security = HTTPBearer()

# --- Token Logic ---

def create_access_token(data: dict) -> str:
    """Creates a new JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> str:
    """
    Verifies the JWT token.
    If valid, returns the implant_id (from the 'sub' claim).
    If invalid, raises an HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        implant_id: str = payload.get("sub")
        if implant_id is None:
            raise credentials_exception
        return implant_id
    except JWTError:
        raise credentials_exception

async def get_current_implant_id(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    A FastAPI dependency that can be used in path operations to protect them.
    It extracts the token from the Authorization header, verifies it, and returns the implant_id.
    """
    return verify_token(credentials.credentials)
