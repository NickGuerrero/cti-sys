from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import settings

security = HTTPBearer(auto_error=True)

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    """
    Verify API key from Authorization header.
    Expects:
        Authorization: Bearer <API_KEY>
    """
    server_key = settings.cti_sys_admin_key
    token = credentials.credentials  # Extracts the Bearer token

    if not server_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: missing CTI_SYS_ADMIN_KEY",
        )

    if token != server_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
