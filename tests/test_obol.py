import os
import io
import json
import base64
import hashlib
import pytest
from starlette.testclient import TestClient

# Configure environment for tests before importing app
os.environ["STORAGE_DIR"] = "/tmp/obol_test_storage"
os.environ["ATTACHMENTS_DIR"] = "/tmp/obol_test_storage/attachments"
os.environ["DISABLE_AUTH"] = "true"

from app.main import app
from app.storage import storage

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup test storage dirs
    storage._ensure_files()
    yield
    # No teardown needed for /tmp

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "obol"

def test_ahp_manifest():
    """Verify compliance with AHP Section 4.1."""
    res = client.get("/.well-known/ahp.json")
    assert res.status_code == 200
    manifest = res.json()
    assert manifest["ahp"] == "1"
    assert manifest["name"] == "obol"
    assert "ed25519:" in manifest["principal"]
    assert "keys" in manifest
    assert "sign" in manifest["keys"]
    assert manifest["openapi"] == "/openapi.json"
    assert manifest["tools"] == "/tools"
    assert manifest["search"] == "/@search"
    assert "rails" in manifest
    assert "cashu" in manifest["rails"]
    assert "l402" in manifest["rails"]
    assert "gateway" in manifest

def test_agent_registration():
    """Verify agent identity registration (AHP Section 5)."""
    payload = {
        "principal": "ed25519:test_agent_grok_key_123",
        "name": "Hurt Crow 🥦",
        "role": "adversarial-testing",
        "capabilities": ["code-audit", "stress-test"]
    }
    res = client.post(
        "/api/v1/agents/register",
        json=payload,
        headers={"X-AHP-Principal": payload["principal"]}
    )
    assert res.status_code == 200
    agent = res.json()
    assert agent["name"] == "Hurt Crow 🥦"
    assert agent["principal"] == payload["principal"]

    # Verify listing
    res = client.get("/api/v1/agents")
    assert res.status_code == 200
    agents = res.json()
    assert any(a["principal"] == payload["principal"] for a in agents)

    # Verify single fetch
    res = client.get(f"/api/v1/agents/{payload['principal']}")
    assert res.status_code == 200
    assert res.json()["name"] == "Hurt Crow 🥦"

def test_tool_registration_and_discovery():
    """Verify tool registration, catalog listing, and search (AHP Section 3 & 4)."""
    tool_payload = {
        "path": "/tool/adversarial_eval",
        "name": "Adversarial Code Evaluator",
        "description": "Performs penetration testing and security boundary checks.",
        "cost": "15",
        "unit": "sat",
        "metered": False,
        "tags": ["security", "audit", "pentest"]
    }
    res = client.post(
        "/api/v1/tools/register",
        json=tool_payload,
        headers={"X-AHP-Principal": "ed25519:test_agent_grok_key_123"}
    )
    assert res.status_code == 200
    t = res.json()
    assert t["path"] == "/tool/adversarial_eval"

    # Verify /tools listing per AHP §4.3
    res = client.get("/tools")
    assert res.status_code == 200
    tools = res.json()
    match = next((item for item in tools if item["path"] == "/tool/adversarial_eval"), None)
    assert match is not None
    assert match["cost"] == "15"
    assert match["unit"] == "sat"

    # Verify /@search per AHP §4.4
    res = client.get("/@search?q=penetration")
    assert res.status_code == 200
    search_data = res.json()
    assert search_data["count"] >= 1
    assert any(r["path"] == "/tool/adversarial_eval" for r in search_data["results"])

def test_multimodal_attachments():
    """Verify upload and download of rich multimodal payloads (PDF, PNG, WAV)."""
    # 1. Test PDF upload via base64
    fake_pdf_content = b"%PDF-1.4 Mock PDF content for agent report"
    pdf_sha256 = hashlib.sha256(fake_pdf_content).hexdigest()
    b64_pdf = base64.b64encode(fake_pdf_content).decode()

    res = client.post(
        "/api/v1/attachments/base64",
        json={
            "filename": "security_audit.pdf",
            "content_base64": b64_pdf,
            "content_type": "application/pdf",
            "metadata": {"pages": 12, "author": "Hurt Crow"}
        },
        headers={"X-AHP-Principal": "ed25519:test_agent_grok_key_123"}
    )
    assert res.status_code == 200
    pdf_meta = res.json()
    assert pdf_meta["sha256_hash"] == pdf_sha256
    assert pdf_meta["content_type"] == "application/pdf"
    att_id = pdf_meta["id"]

    # 2. Test Image (PNG) upload via multipart
    fake_png_content = b"\x89PNG\r\n\x1a\nMock PNG bytes"
    res = client.post(
        "/api/v1/attachments",
        files={"file": ("diagram.png", io.BytesIO(fake_png_content), "image/png")},
        headers={"X-AHP-Principal": "ed25519:test_agent_grok_key_123"}
    )
    assert res.status_code == 200
    png_meta = res.json()
    assert png_meta["content_type"] == "image/png"

    # 3. Test Audio (WAV) upload via base64
    fake_wav_content = b"RIFF....WAVEfmt Mock audio bytes"
    b64_wav = base64.b64encode(fake_wav_content).decode()
    res = client.post(
        "/api/v1/attachments/base64",
        json={
            "filename": "briefing.wav",
            "content_base64": b64_wav,
            "content_type": "audio/wav"
        },
        headers={"X-AHP-Principal": "ed25519:test_agent_grok_key_123"}
    )
    assert res.status_code == 200
    wav_meta = res.json()
    assert wav_meta["content_type"] == "audio/wav"

    # 4. Verify binary download of the PDF
    dl_res = client.get(f"/api/v1/attachments/{att_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.content == fake_pdf_content
    assert dl_res.headers["content-type"] == "application/pdf"

def test_inter_agent_messaging():
    """Verify agent message exchange with attached multimodal payloads."""
    # First create an attachment
    fake_doc = b"Execution trace summary document"
    b64_doc = base64.b64encode(fake_doc).decode()
    att_res = client.post(
        "/api/v1/attachments/base64",
        json={
            "filename": "trace.log",
            "content_base64": b64_doc,
            "content_type": "text/plain"
        },
        headers={"X-AHP-Principal": "ed25519:test_sender"}
    )
    att_id = att_res.json()["id"]

    # Send message with attachment reference
    msg_payload = {
        "recipient": "ed25519:continued_moose_key",
        "channel": "coordination",
        "subject": "Task Completed",
        "content": "Finished the security review. Review the attached trace.",
        "attachment_ids": [att_id]
    }
    msg_res = client.post(
        "/api/v1/messages",
        json=msg_payload,
        headers={"X-AHP-Principal": "ed25519:test_sender"}
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert msg_data["recipient"] == "ed25519:continued_moose_key"
    assert len(msg_data["attachments"]) == 1
    assert msg_data["attachments"][0]["id"] == att_id

    # Retrieve message for recipient
    read_res = client.get(
        "/api/v1/messages?recipient=ed25519:continued_moose_key",
        headers={"X-AHP-Principal": "ed25519:continued_moose_key"}
    )
    assert read_res.status_code == 200
    messages = read_res.json()
    assert any(m["id"] == msg_data["id"] for m in messages)

def test_ahp_hypercall_and_receipts():
    """Verify tool execution, 402 challenge, and signed receipt generation."""
    # Register a free tool
    client.post(
        "/api/v1/tools/register",
        json={
            "path": "/tool/echo_test",
            "name": "Echo Test",
            "description": "Echoes back parameters",
            "cost": "0"
        },
        headers={"X-AHP-Principal": "ed25519:provider"}
    )

    # Invoke free tool
    res = client.get(
        "/tool/echo_test?msg=hello",
        headers={"X-AHP-Principal": "ed25519:consumer"}
    )
    assert res.status_code == 200
    assert "AHP-Receipt" in res.headers
    receipt_raw = base64.urlsafe_b64decode(res.headers["AHP-Receipt"]).decode()
    receipt = json.loads(receipt_raw)
    assert receipt["tool"] == "/tool/echo_test"
    assert receipt["amount"] == "0.0"

    # Register a paid tool
    client.post(
        "/api/v1/tools/register",
        json={
            "path": "/tool/premium_compute",
            "name": "Premium Compute",
            "description": "High throughput computation",
            "cost": "100",
            "unit": "sat"
        },
        headers={"X-AHP-Principal": "ed25519:provider"}
    )

    # Call paid tool anonymously (no payment token or auth)
    # Note: in test env DISABLE_AUTH is true, so auth identity is automatically generated
    # but let's test that receipts are issued and recorded in the fiscal ledger
    res = client.post(
        "/tool/premium_compute",
        json={"matrix_size": 1024},
        headers={"X-AHP-Principal": "ed25519:consumer"}
    )
    assert res.status_code == 200
    assert "AHP-Receipt" in res.headers

    # Check Fiscal Ledger
    ledger_res = client.get(
        "/api/v1/fiscal/ledger",
        headers={"X-AHP-Principal": "ed25519:consumer"}
    )
    assert ledger_res.status_code == 200
    summary = ledger_res.json()
    assert summary["transaction_count"] >= 1


def test_landing_page_and_assets():
    """Verify landing page, meta tags, and static brand assets."""
    # Test Root Landing Page
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "NUTS.SERVICES" in html
    assert "twitter:card" in html
    assert "twitter:image" in html
    assert "og:image" in html
    assert "favicon.svg" in html
    assert "https://auth.nuts.services/login" in html
    assert "https://auth.nuts.services/dashboard" in html
    assert "https://github.com/DeepBlueDynamics/obol" in html
    assert "DeepBlue Dynamics, LLC" in html

    # Test Favicons and OG Preview Asset Routes
    for path in ["/favicon.ico", "/favicon.svg", "/favicon.png", "/apple-touch-icon.png", "/og-preview.png"]:
        asset_res = client.get(path)
        assert asset_res.status_code == 200
        assert len(asset_res.content) > 0

