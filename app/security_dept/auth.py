import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

# Load .env file BEFORE reading any environment variables
load_dotenv()

# No default value - forces explicit configuration
SECRET_KEY = os.getenv("MRC_JWT_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError(
        "MRC_JWT_SECRET_KEY environment variable is required. "
        "Add it to your .env file with a strong random value (min 32 chars). "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

# Reject weak/default secrets at startup
if SECRET_KEY == "changeme-super-secret-key":
    raise ValueError(
        "JWT secret is still set to the default placeholder value. "
        "Generate a strong secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

if len(SECRET_KEY) < 32:
    raise ValueError(
        f"JWT secret must be at least 32 characters for security. "
        f"Current length: {len(SECRET_KEY)}. "
        "Generate a strong secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
