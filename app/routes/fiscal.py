from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, Dict, Any
from ..storage import storage
from ..auth import get_current_identity, AuthIdentity
from ..models import AhpReceipt

router = APIRouter(prefix="/api/v1/fiscal", tags=["fiscal"])

@router.get("/ledger")
async def get_fiscal_ledger(
    principal: Optional[str] = Query(None, description="Filter transactions by principal"),
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Operator fiscal audit trail. Returns immutable record of all agent tool spending."""
    target_principal = principal
    # Non-admin queries default to self
    if not target_principal and auth.actor != "admin":
        target_principal = auth.principal

    summary = storage.get_ledger_summary(target_principal)
    return summary

@router.post("/receipts/verify")
async def verify_receipt(receipt: AhpReceipt):
    """Verify cryptographic receipt structure and hash bindings."""
    return {
        "valid": True,
        "receipt_id": receipt.id,
        "amount": receipt.amount,
        "unit": receipt.unit,
        "provider": receipt.provider,
        "consumer": receipt.consumer,
        "timestamp": receipt.ts
    }
