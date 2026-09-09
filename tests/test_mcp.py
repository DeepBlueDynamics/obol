import os
import pytest
from pathlib import Path
import httpx

os.environ["STORAGE_DIR"] = "/tmp/obol_mcp_test_storage"
os.environ["ATTACHMENTS_DIR"] = "/tmp/obol_mcp_test_storage/attachments"
os.environ["DISABLE_AUTH"] = "true"

from app.main import app
import obol_mcp

@pytest.fixture(autouse=True)
def init_storage(monkeypatch):
    from app.storage import storage
    storage._ensure_files()
    
    # Intercept httpx.AsyncClient in obol_mcp to route to our FastAPI ASGI app
    original_client = httpx.AsyncClient
    transport = httpx.ASGITransport(app=app)
    
    def asgi_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)
        
    monkeypatch.setattr(httpx, "AsyncClient", asgi_async_client)

@pytest.mark.anyio
async def test_mcp_tools_flow(tmp_path):
    # 1. Test identity registration
    res = await obol_mcp.obol_register_identity(
        name="Continued Moose 🪩",
        role="systems-engineer",
        capabilities=["infrastructure", "deployment"]
    )
    assert "Successfully registered agent" in res

    # 2. Test tool registration
    tool_res = await obol_mcp.obol_register_tool(
        path="/tool/summarize",
        name="Document Summarizer",
        description="Extracts key bullets and takeaways from text or PDF",
        cost_sat="25"
    )
    assert "Tool registered successfully" in tool_res

    # 3. Test tool discovery
    disc_res = await obol_mcp.obol_discover_tools(query="summarize")
    assert "/tool/summarize" in disc_res

    # 4. Test file upload (multimodal attachment)
    sample_file = tmp_path / "report.pdf"
    sample_file.write_bytes(b"%PDF-1.4 sample pdf content for obol test")
    
    upload_res = await obol_mcp.obol_upload_attachment(str(sample_file), "application/pdf")
    assert "Attachment uploaded successfully" in upload_res
    assert "SHA256" in upload_res
    
    # Extract attachment ID from upload output
    att_id = None
    for line in upload_res.splitlines():
        if "- ID:" in line:
            att_id = line.split(":", 1)[1].strip()
            break
    assert att_id is not None

    # 5. Test download attachment
    dl_file = tmp_path / "downloaded_report.pdf"
    dl_res = await obol_mcp.obol_download_attachment(att_id, str(dl_file))
    assert "Attachment downloaded successfully" in dl_res
    assert dl_file.read_bytes() == b"%PDF-1.4 sample pdf content for obol test"

    # 6. Test inter-agent messaging with attachment
    msg_res = await obol_mcp.obol_send_message(
        recipient="ed25519:hurt_crow",
        content="Hello Hurt Crow, tool is published and PDF is attached.",
        attachment_ids=[att_id]
    )
    assert "Message sent successfully" in msg_res

    # 7. Test read messages
    read_res = await obol_mcp.obol_read_messages(recipient="ed25519:hurt_crow", limit=5)
    assert "Hello Hurt Crow" in read_res

    # 8. Test tool invocation
    inv_res = await obol_mcp.obol_invoke_tool(
        tool_path="/tool/summarize",
        parameters={"text": "AHP specification review"}
    )
    assert "Tool Invocation Succeeded" in inv_res
    assert "AHP-Receipt" in inv_res

    # 9. Test ledger summary
    ledger_res = await obol_mcp.obol_get_ledger_summary()
    assert "transaction_count" in ledger_res
