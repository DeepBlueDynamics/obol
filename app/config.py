import os
from pathlib import Path
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="allow")
    
    app_name: str = "obol"
    app_title: str = "Obol AHP Economic Gateway & Fiscal Governance Engine"
    app_version: str = "0.1.0"
    
    # Network & Binding
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8085"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # nuts-auth Integration
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "https://auth.nuts.services").rstrip("/")
    jwks_url: str = os.getenv("JWKS_URL", "https://auth.nuts.services/.well-known/jwks.json")
    auth_validate_url: str = os.getenv("AUTH_VALIDATE_URL", "https://auth.nuts.services/api/validate")
    auth_exchange_url: str = os.getenv("AUTH_EXCHANGE_URL", "https://auth.nuts.services/auth")
    disable_auth_for_local_dev: bool = os.getenv("DISABLE_AUTH", "false").lower() in ("true", "1", "yes")
    
    # Storage Paths
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", str(Path(__file__).parent.parent / "storage")))
    attachments_dir: Path = Path(os.getenv("ATTACHMENTS_DIR", str(Path(__file__).parent.parent / "storage" / "attachments")))
    
    # AHP Constants
    ahp_version: str = "1"
    default_unit: str = "sat"
    gateway_enabled: bool = True

settings = Settings()

# Ensure storage directories exist
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.attachments_dir.mkdir(parents=True, exist_ok=True)
