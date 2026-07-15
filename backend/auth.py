from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import httpx
from typing import Optional, Dict, Any
import logging
from backend.config import settings

logger = logging.getLogger("auth")

security = HTTPBearer(auto_error=False)

# Cache JWKS key set to avoid round-trips
_jwks_cache: Optional[Dict[str, Any]] = None

async def fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=5.0)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from Clerk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying authentication provider keys"
        )

async def verify_clerk_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """
    Verifies the JWT token from Clerk.
    If Clerk environment variables are not set, we fall back to a mock user for local development.
    """
    # 1. Fallback for local development when Clerk configs are missing
    if not settings.CLERK_JWKS_URL and not settings.CLERK_API_KEY:
        # Development mode bypass - accept "dev_user" or custom header
        logger.warning("Clerk API keys/JWKS not configured. Bypassing token validation, using mock dev user.")
        if credentials and credentials.credentials:
            # If a token is passed, use it as user ID if it doesn't look like JWT, or parse simple string
            user_id = credentials.credentials
            if len(user_id) > 50:
                user_id = "user_dev_12345"
            return {"sub": user_id, "email": f"{user_id}@example.com"}
        return {"sub": "user_dev_12345", "email": "dev_user@example.com"}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Get Key ID (kid) from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header structure"
            )

        # Get JWT Public Keys (JWKS)
        jwks_url = settings.CLERK_JWKS_URL or f"https://api.clerk.com/v1/jwks"
        jwks = await fetch_jwks(jwks_url)

        # Find matching key in JWKS
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Public key not found for token verification"
            )

        # Decode token and verify signature
        # Clerk issuer format can vary, verify standard fields
        options = {"verify_aud": False} # Set to True if audience is verified
        
        # Decode utilizing PyJWT
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=settings.CLERK_JWT_ISSUER,
            options=options
        )
        
        # Verify sub field is present
        if "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is missing subject claim"
            )
            
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )

async def get_current_user_id(payload: Dict[str, Any] = Depends(verify_clerk_token)) -> str:
    """Dependency to retrieve user ID directly from token endpoint"""
    return payload["sub"]

async def get_current_user_email(payload: Dict[str, Any] = Depends(verify_clerk_token)) -> str:
    """Dependency to retrieve email address from claims"""
    return payload.get("email") or payload.get("email_address") or "user@example.com"
