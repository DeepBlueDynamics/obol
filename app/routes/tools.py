import hashlib
import json
import base64
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query, Header
from fastapi.responses import JSONResponse, RedirectResponse
from typing import List, Dict, Any, Optional
import httpx

from ..models import (
    ToolRegistration,
    AhpProblemDetails,
    AhpPaymentOffer,
    AhpReceipt,
    FiscalLedgerEntry
)
from ..storage import storage
from ..auth import get_current_identity, get_optional_identity, AuthIdentity
from ..config import settings

router = APIRouter(tags=["tools"])

@router.post("/api/v1/tools/register", response_model=ToolRegistration)
async def register_tool(
    tool: ToolRegistration,
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Register an agent capability / tool with AHP pricing metadata."""
    # Ensure path begins with /tool/
    if not tool.path.startswith("/tool/"):
        tool.path = f"/tool/{tool.path.lstrip('/')}"
        
    saved = storage.save_tool(tool, provider_principal=auth.principal)
    return saved

@router.get("/tools")
async def list_tools_ahp():
    """Flatter AHP tool listing per AHP §4.3."""
    tools = storage.list_tools()
    ahp_listing = []
    for t in tools:
        entry = {
            "path": t.get("path"),
            "name": t.get("name"),
            "description": t.get("description"),
            "cost": str(t.get("cost", "0")),
            "unit": t.get("unit", "sat"),
            "provider": t.get("provider_principal", "unknown")
        }
        if t.get("metered"):
            entry["metered"] = True
            entry["per"] = t.get("per")
        if t.get("free_quota"):
            entry["free_quota"] = t.get("free_quota")
        ahp_listing.append(entry)
    return ahp_listing

@router.get("/@search")
async def search_tools(q: str = Query(..., min_length=1)):
    """Ranked tool discovery search per AHP §4.4."""
    results = storage.search_tools(q)
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "path": r.get("path"),
                "name": r.get("name"),
                "description": r.get("description"),
                "cost": str(r.get("cost", "0")),
                "unit": r.get("unit", "sat")
            }
            for r in results
        ]
    }

# --- Dynamic Hypercall Dispatcher & Aperture Engine (AHP §3, §6, §8) ---

@router.get("/tool/{tool_name:path}")
async def invoke_tool_get(
    tool_name: str,
    request: Request,
    auth: Optional[AuthIdentity] = Depends(get_optional_identity),
    x_cashu: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    """AHP GET Hypercall (Safe/Idempotent)."""
    params = dict(request.query_params)
    return await _handle_hypercall(
        tool_name=tool_name,
        params=params,
        method="GET",
        auth=auth,
        x_cashu=x_cashu,
        authorization=authorization
    )

@router.post("/tool/{tool_name:path}")
async def invoke_tool_post(
    tool_name: str,
    request: Request,
    auth: Optional[AuthIdentity] = Depends(get_optional_identity),
    x_cashu: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    """AHP POST Hypercall (Large params / Non-idempotent)."""
    try:
        params = await request.json()
    except Exception:
        params = {}
    return await _handle_hypercall(
        tool_name=tool_name,
        params=params,
        method="POST",
        auth=auth,
        x_cashu=x_cashu,
        authorization=authorization
    )

async def _handle_hypercall(
    tool_name: str,
    params: Dict[str, Any],
    method: str,
    auth: Optional[AuthIdentity],
    x_cashu: Optional[str],
    authorization: Optional[str]
):
    canonical_path = f"/tool/{tool_name.lstrip('/')}"
    tool = storage.get_tool(canonical_path)
    
    # AHP §3.4: No Dead Ends
    if not tool:
        # Check if there are similar tools or redirect to search
        search_hits = storage.search_tools(tool_name)
        if search_hits:
            suggestions = [h.get("path") for h in search_hits]
            return JSONResponse(
                status_code=404,
                content={
                    "type": "urn:ahp:problem:tool-not-found",
                    "title": "Tool Not Found",
                    "status": 404,
                    "detail": f"Tool '{canonical_path}' does not exist.",
                    "suggestions": suggestions
                },
                media_type="application/problem+json"
            )
        return RedirectResponse(f"/@search?q={tool_name}", status_code=302)

    cost_sat = float(tool.get("cost", "0"))
    unit = tool.get("unit", "sat")
    consumer_principal = auth.principal if auth else "ed25519:anonymous"
    provider_principal = tool.get("provider_principal", "ed25519:obol_gateway")

    # AHP §6: Aperture Principle & 402 Challenge
    has_paid = False
    if cost_sat <= 0:
        has_paid = True
    elif x_cashu or (authorization and "L402" in authorization):
        # Ecash proof or L402 token presented
        has_paid = True
    elif auth and auth.is_authenticated:
        # Settled against operator balance account
        has_paid = True

    if not has_paid:
        problem = AhpProblemDetails(
            type="urn:ahp:problem:payment-required",
            title="Payment Required",
            status=402,
            detail=f"Invocation of {canonical_path} requires {cost_sat} {unit}.",
            tool=canonical_path,
            amount=str(tool.get("cost", "0")),
            unit=unit,
            offers=[
                AhpPaymentOffer(rail="cashu", mints=["https://mint.nuts.services"]),
                AhpPaymentOffer(rail="l402", payreq="lnbc..."),
                AhpPaymentOffer(rail="balance")
            ]
        )
        return JSONResponse(
            status_code=402,
            content=problem.model_dump(),
            media_type="application/problem+json",
            headers={
                "WWW-Authenticate": f'Cashu mint="https://mint.nuts.services", amount="{cost_sat}", unit="{unit}"'
            }
        )

    # Execute tool (proxy or builtin handler)
    endpoint_url = tool.get("endpoint_url")
    result_data = None
    if endpoint_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    res = await client.get(endpoint_url, params=params)
                else:
                    res = await client.post(endpoint_url, json=params)
                result_data = res.json() if "application/json" in res.headers.get("content-type", "") else res.text
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error executing provider tool: {str(e)}")
    else:
        # Built-in or synthetic tool execution echo for registered agent tools
        result_data = {
            "status": "success",
            "tool": canonical_path,
            "params": params,
            "executed_at": int(time.time()),
            "message": f"Executed {tool.get('name')}"
        }

    # Generate AHP Receipt per Section 8
    req_canonical_bytes = json.dumps(params, sort_keys=True).encode()
    res_canonical_bytes = json.dumps(result_data, sort_keys=True).encode() if isinstance(result_data, (dict, list)) else str(result_data).encode()
    
    req_hash = f"sha256:{hashlib.sha256(req_canonical_bytes).hexdigest()}"
    res_hash = f"sha256:{hashlib.sha256(res_canonical_bytes).hexdigest()}"

    receipt = AhpReceipt(
        provider=provider_principal,
        consumer=consumer_principal,
        tool=canonical_path,
        request_hash=req_hash,
        response_hash=res_hash,
        amount=str(cost_sat),
        unit=unit,
        sig="mock_ed25519_sig_verified"
    )
    
    # Encode receipt in AHP-Receipt header
    receipt_b64 = base64.urlsafe_b64encode(json.dumps(receipt.model_dump()).encode()).decode()

    # Log to Operator Fiscal Ledger
    storage.record_ledger_entry(
        FiscalLedgerEntry(
            consumer_principal=consumer_principal,
            provider_principal=provider_principal,
            tool_path=canonical_path,
            amount=str(cost_sat),
            unit=unit,
            status="settled",
            receipt_id=receipt.id,
            notes=f"Hypercall {method} {canonical_path}"
        )
    )

    response_payload = result_data if isinstance(result_data, (dict, list)) else {"result": result_data}
    return JSONResponse(
        content=response_payload,
        headers={
            "AHP-Receipt": receipt_b64,
            "ETag": f'"{res_hash}"'
        }
    )
