import time
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status, Depends
from pydantic import BaseModel
from .config import settings

class AuthIdentity(BaseModel):
    user_id: str
    email: Optional[str] = None
    actor: Optional[str] = None
    principal: str  # ed25519:... or nuts:<user_id>
    scopes: list[str] = []
    is_authenticated: bool = True

class NutsAuthClient:
    def __init__(self):
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cached_at: float = 0
        self.jwks_ttl: float = 3600  # 1 hour
        self.token_cache: Dict[str, Dict[str, Any]] = {}
        
    async def get_jwks(self) -> Dict[str, Any]:
        now = time.time()
        if self.jwks_cache and (now - self.jwks_cached_at) < self.jwks_ttl:
            return self.jwks_cache
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(settings.jwks_url)
                if res.status_code == 200:
                    self.jwks_cache = res.json()
                    self.jwks_cached_at = now
                    return self.jwks_cache
        except Exception as e:
            if self.jwks_cache:
                return self.jwks_cache
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch authentication keys: {str(e)}"
            )
        return {"keys": []}

    async def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        jwks = await self.get_jwks()
        keys = jwks.get("keys", [])
        if not keys:
            return None
        
        try:
            # Check unverified header to match kid if present
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            matching_key = None
            for key in keys:
                if not kid or key.get("kid") == kid:
                    matching_key = key
                    break
            if not matching_key:
                matching_key = keys[0]
            
            public_key = RSAAlgorithm.from_jwk(matching_key)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False}
            )
            return claims
        except Exception:
            return None

    async def validate_api_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate an ahp_ token against nuts-auth validation/exchange endpoints."""
        now = time.time()
        cached = self.token_cache.get(token)
        if cached and cached.get("exp", 0) > now:
            return cached.get("data")
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Option 1: Try api/validate (JSON payload)
                val_res = await client.post(
                    settings.auth_validate_url,
                    json={"token": token}
                )
                if val_res.status_code == 200:
                    data = val_res.json()
                    if data.get("valid"):
                        self.token_cache[token] = {"data": data, "exp": now + 600}
                        return data

                # Option 2: Try /auth exchange endpoint (form payload)
                ex_res = await client.post(
                    settings.auth_exchange_url,
                    data={"token": token}
                )
                if ex_res.status_code == 200:
                    jwt_data = ex_res.json()
                    access_jwt = jwt_data.get("access_token")
                    if access_jwt:
                        claims = await self.verify_jwt(access_jwt)
                        if claims:
                            res_data = {
                                "valid": True,
                                "subject": claims.get("sub"),
                                "user_uid": claims.get("user_id", claims.get("sub")),
                                "actor": claims.get("name", "agent")
                            }
                            self.token_cache[token] = {"data": res_data, "exp": now + 600}
                            return res_data
        except Exception:
            pass
        return None

auth_client = NutsAuthClient()

async def get_current_identity(
    authorization: Optional[str] = Header(None),
    x_ahp_principal: Optional[str] = Header(None)
) -> AuthIdentity:
    """Dependency for securing endpoints via nuts-auth (Bearer JWT or ahp_ token)."""
    if not authorization:
        if settings.disable_auth_for_local_dev:
            principal = x_ahp_principal or "ed25519:local-dev-agent"
            return AuthIdentity(
                user_id="local-dev-user",
                email="dev@nuts.services",
                actor="local-dev",
                principal=principal
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required (Bearer <jwt> or Bearer <ahp_token>)",
            headers={"WWW-Authenticate": "Bearer"}
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Must be 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    # Shape 1: ahp_ API token
    if token.startswith("ahp_"):
        val = await auth_client.validate_api_token(token)
        if not val:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired ahp_ API token from auth.nuts.services",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
            )
        user_id = val.get("user_uid", val.get("subject", "anonymous"))
        email = val.get("subject")
        actor = val.get("actor", "agent")
        principal = x_ahp_principal or f"nuts:{user_id}"
        return AuthIdentity(
            user_id=user_id,
            email=email,
            actor=actor,
            principal=principal
        )

    # Shape 2: RS256 JWT
    claims = await auth_client.verify_jwt(token)
    if not claims:
        if settings.disable_auth_for_local_dev:
            principal = x_ahp_principal or "ed25519:local-dev-agent"
            return AuthIdentity(
                user_id="local-dev-user",
                email="dev@nuts.services",
                actor="local-dev",
                principal=principal
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT against auth.nuts.services JWKS",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )

    user_id = str(claims.get("user_id", claims.get("sub", "unknown")))
    email = claims.get("sub")
    actor = claims.get("name", "agent")
    principal = x_ahp_principal or f"nuts:{user_id}"

    return AuthIdentity(
        user_id=user_id,
        email=email,
        actor=actor,
        principal=principal
    )

async def get_optional_identity(
    authorization: Optional[str] = Header(None),
    x_ahp_principal: Optional[str] = Header(None)
) -> Optional[AuthIdentity]:
    if not authorization:
        if settings.disable_auth_for_local_dev:
            return AuthIdentity(
                user_id="anonymous",
                principal=x_ahp_principal or "ed25519:anonymous"
            )
        return None
    try:
        return await get_current_identity(authorization, x_ahp_principal)
    except HTTPException:
        return None
