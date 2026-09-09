from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict
import time
import uuid

# --- AHP Manifest & Discovery Models ---

class AhpKeys(BaseModel):
    sign: str = Field(..., description="Ed25519 public key in format ed25519:<base64url>")
    encrypt: Optional[str] = Field(None, description="X25519 public key in format x25519:<base64url>")
    not_after: Optional[int] = Field(None, description="Expiration timestamp (unix epoch seconds)")
    binding: Optional[str] = Field(None, description="Signature binding encrypt key to sign key")

class AhpGatewayEndpoints(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    register_url: str = Field("/api/v1/gateway/register", serialization_alias="register")
    session: str = "/api/v1/gateway/session"
    settlements: str = "/api/v1/gateway/settlements"
    ratings: str = "/api/v1/gateway/ratings"

class AhpManifest(BaseModel):
    ahp: str = "1"
    name: str = "obol"
    principal: str
    keys: AhpKeys
    openapi: str = "/openapi.json"
    tools: str = "/tools"
    search: str = "/@search"
    auth: Dict[str, str] = {"token": "/auth", "verify": "/api/verify"}
    rails: List[str] = ["balance", "l402", "cashu"]
    unit: str = "sat"
    gateway: Optional[AhpGatewayEndpoints] = None
    reputation: str = "/.well-known/ahp/reputation"

# --- Tool Models (AHP §3, §4) ---

class AhpCost(BaseModel):
    cost: str = "0"
    unit: str = "sat"
    metered: bool = False
    per: Optional[str] = None
    free_quota: Optional[Dict[str, Any]] = None

class ToolRegistration(BaseModel):
    path: str = Field(..., description="Canonical path, e.g. /tool/calculate")
    name: str = Field(..., description="Human/Agent friendly name")
    description: str = Field(..., description="Detailed documentation of what tool accomplishes")
    cost: str = Field("0", description="Cost in declared unit (e.g. sat)")
    unit: str = Field("sat", description="Amount unit (sat, msat, usd)")
    metered: bool = Field(False, description="True if priced per usage unit")
    per: Optional[str] = Field(None, description="Unit denominator if metered (e.g. 1000_tokens)")
    free_quota: Optional[Dict[str, Any]] = Field(None, description="Quota policy if applicable")
    parameters_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema for parameters")
    endpoint_url: Optional[str] = Field(None, description="Target execution URL if proxied")
    tags: List[str] = Field(default_factory=list)

class ToolSummary(BaseModel):
    path: str
    name: str
    description: str
    cost: str
    unit: str = "sat"
    metered: bool = False
    per: Optional[str] = None
    free_quota: Optional[str] = None
    provider: str

# --- Agent Identity Models (AHP §5) ---

class AgentIdentity(BaseModel):
    principal: str = Field(..., description="ed25519:<base64url>")
    name: str = Field(..., description="Display name of the agent (e.g. 'Hurt Crow 🥦')")
    role: str = Field("worker", description="Agent specialty or job title")
    tenant_user_id: Optional[str] = Field(None, description="nuts-auth user_id/email owner")
    encrypt_key: Optional[str] = Field(None, description="x25519:<base64url>")
    binding: Optional[str] = None
    not_after: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)
    registered_at: int = Field(default_factory=lambda: int(time.time()))
    last_seen: int = Field(default_factory=lambda: int(time.time()))

# --- Attachment Models (Multimodal: PDF, Image, Audio, etc.) ---

class AttachmentMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    content_type: str = Field(..., description="MIME type, e.g. application/pdf, image/png, audio/wav")
    size_bytes: int
    sha256_hash: str = Field(..., description="Content-addressable SHA-256 hex digest")
    uploader_principal: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    download_url: str = ""
    gcs_uri: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- Message Models ---

class MessageCreate(BaseModel):
    recipient: str = Field(..., description="Target principal (ed25519:...) or 'broadcast' or channel name")
    channel: Optional[str] = Field("general", description="Discussion or topic channel")
    subject: Optional[str] = None
    content: str = Field(..., description="Message text, instruction, prompt, or reply")
    attachment_ids: List[str] = Field(default_factory=list, description="IDs of previously uploaded attachments")
    reply_to_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MessageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_principal: str
    recipient: str
    channel: str = "general"
    subject: Optional[str] = None
    content: str
    attachments: List[AttachmentMetadata] = Field(default_factory=list)
    reply_to_id: Optional[str] = None
    created_at: int = Field(default_factory=lambda: int(time.time()))
    read_by: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# --- AHP Fiscal Models (402, Receipts, Ledger) ---

class AhpPaymentOffer(BaseModel):
    rail: str = "cashu"
    mints: Optional[List[str]] = None
    payreq: Optional[str] = None

class AhpProblemDetails(BaseModel):
    type: str = "urn:ahp:problem:payment-required"
    title: str = "Payment Required"
    status: int = 402
    detail: Optional[str] = "Invocation of this tool requires payment."
    tool: str
    amount: str
    unit: str = "sat"
    offers: List[AhpPaymentOffer] = Field(default_factory=list)

class AhpReceipt(BaseModel):
    v: int = 1
    type: str = "ahp-receipt"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: int = Field(default_factory=lambda: int(time.time()))
    provider: str
    consumer: str
    tool: str
    request_hash: str
    response_hash: str
    amount: str
    unit: str = "sat"
    sig: Optional[str] = None

class FiscalLedgerEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    consumer_principal: str
    provider_principal: str
    tool_path: str
    amount: str
    unit: str = "sat"
    rail: str = "balance"
    status: str = "settled"  # settled, held, refunded, failed
    receipt_id: Optional[str] = None
    notes: Optional[str] = None
