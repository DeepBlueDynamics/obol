from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from ..config import settings
from ..models import AhpManifest, AhpKeys, AhpGatewayEndpoints

router = APIRouter(tags=["manifest"])

HTML_PATH = Path(__file__).parent.parent / "static" / "index.html"

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root_index():
    """Serve the Obol marketing landing page and coordination dashboard."""
    if HTML_PATH.exists():
        return HTMLResponse(content=HTML_PATH.read_text(encoding="utf-8"))
    return RedirectResponse(url="/docs")

# Gateway public principal key (ed25519)
GATEWAY_PRINCIPAL = "ed25519:obol_gateway_master_key_ahp_2026"
GATEWAY_SIGN_KEY = "ed25519:MCowBQYDK2VwAyEAdX9b_obol_gateway_sign_key_default"
GATEWAY_ENCRYPT_KEY = "x25519:hSDwCYkwp1R0i33ctD73Wg2_Og0mOBr066SpjqqbTmo"

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "auth_service": settings.auth_service_url,
        "environment": settings.environment
    }

@router.get("/.well-known/ahp.json", response_model=AhpManifest)
async def get_ahp_manifest():
    """AHP Manifest per Section 4.1 of draft-campbell-agentic-market-00."""
    return AhpManifest(
        ahp=settings.ahp_version,
        name=settings.app_name,
        principal=GATEWAY_PRINCIPAL,
        keys=AhpKeys(
            sign=GATEWAY_SIGN_KEY,
            encrypt=GATEWAY_ENCRYPT_KEY,
            not_after=1799999999,
            binding="base64url_sig_obol_gateway"
        ),
        openapi="/openapi.json",
        tools="/tools",
        search="/@search",
        auth={
            "token": f"{settings.auth_service_url}/auth",
            "verify": f"{settings.auth_service_url}/api/verify",
            "dashboard": f"{settings.auth_service_url}/dashboard"
        },
        rails=["balance", "l402", "cashu"],
        unit=settings.default_unit,
        gateway=AhpGatewayEndpoints(
            register_url="/api/v1/gateway/register",
            session="/api/v1/gateway/session",
            settlements="/api/v1/fiscal/receipts",
            ratings="/api/v1/fiscal/ratings"
        ) if settings.gateway_enabled else None,
        reputation="/.well-known/ahp/reputation"
    )
