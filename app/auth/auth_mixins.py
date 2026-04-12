import jwt as pyjwt
from fastapi import Header, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .jwt_auth import SECRET_KEY, ALGORITHM
from ..config import get_settings

security = HTTPBearer(auto_error=False)


async def jwt_or_api_key(
    request: Request,
    x_api_key: str = Header(default=None),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    settings = get_settings()
    manager = getattr(request.app.state, "api_key_manager", None)

    # 1. Try X-API-Key header
    if x_api_key:
        token = x_api_key.strip()
        # Static key check
        if token == settings.api_key.strip():
            return "api_key_user"
        # Managed key check (mr_ prefix)
        if manager and token.startswith("mr_"):
            user_id = manager.verify_key(token)
            if user_id:
                manager.log_usage(token, endpoint=request.url.path, success=True)
                return user_id
            manager.log_usage(token, endpoint=request.url.path, success=False)

    # 2. Try Authorization Bearer header
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()

        # Static key check
        if token == settings.api_key.strip():
            return "api_key_user"

        # Managed key check
        if manager and token.startswith("mr_"):
            user_id = manager.verify_key(token)
            if user_id:
                manager.log_usage(token, endpoint=request.url.path, success=True)
                return user_id
            manager.log_usage(token, endpoint=request.url.path, success=False)

        # JWT check
        try:
            payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                return username
        except Exception:
            pass

    raise HTTPException(status_code=401, detail="Invalid token or not authenticated")
