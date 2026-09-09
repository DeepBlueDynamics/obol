import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from .config import settings
from .models import (
    AttachmentMetadata,
    MessageRecord,
    AgentIdentity,
    ToolRegistration,
    FiscalLedgerEntry
)

class ObolStorage:
    def __init__(self):
        self.storage_dir = settings.storage_dir
        self.attachments_dir = settings.attachments_dir
        
        self.agents_file = self.storage_dir / "agents.json"
        self.tools_file = self.storage_dir / "tools.json"
        self.messages_file = self.storage_dir / "messages.jsonl"
        self.attachments_meta_file = self.storage_dir / "attachments_meta.json"
        self.ledger_file = self.storage_dir / "ledger.jsonl"
        
        self._ensure_files()

    def _ensure_files(self):
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.agents_file.exists():
            self.agents_file.write_text("{}", encoding="utf-8")
        if not self.tools_file.exists():
            self.tools_file.write_text("{}", encoding="utf-8")
        if not self.messages_file.exists():
            self.messages_file.touch()
        if not self.attachments_meta_file.exists():
            self.attachments_meta_file.write_text("{}", encoding="utf-8")
        if not self.ledger_file.exists():
            self.ledger_file.touch()

    # --- Agent Registry ---

    def save_agent(self, agent: AgentIdentity) -> AgentIdentity:
        data = self._read_json(self.agents_file)
        data[agent.principal] = agent.model_dump()
        self._write_json(self.agents_file, data)
        return agent

    def get_agent(self, principal: str) -> Optional[AgentIdentity]:
        data = self._read_json(self.agents_file)
        raw = data.get(principal)
        if raw:
            return AgentIdentity(**raw)
        return None

    def list_agents(self) -> List[AgentIdentity]:
        data = self._read_json(self.agents_file)
        return [AgentIdentity(**v) for v in data.values()]

    # --- Tool Registry ---

    def save_tool(self, tool: ToolRegistration, provider_principal: str) -> ToolRegistration:
        data = self._read_json(self.tools_file)
        tool_dict = tool.model_dump()
        tool_dict["provider_principal"] = provider_principal
        data[tool.path] = tool_dict
        self._write_json(self.tools_file, data)
        return tool

    def get_tool(self, path: str) -> Optional[Dict[str, Any]]:
        data = self._read_json(self.tools_file)
        return data.get(path)

    def list_tools(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.tools_file)
        return list(data.values())

    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower().strip()
        results = []
        for tool in self.list_tools():
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            path = tool.get("path", "").lower()
            tags = [t.lower() for t in tool.get("tags", [])]
            if q in name or q in desc or q in path or any(q in t for t in tags):
                results.append(tool)
        return results

    # --- Attachments (Content Addressable Storage) ---

    def save_attachment(
        self,
        filename: str,
        content_bytes: bytes,
        content_type: str,
        uploader_principal: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AttachmentMetadata:
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        blob_path = self.attachments_dir / sha256
        blob_path.write_bytes(content_bytes)

        meta = AttachmentMetadata(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content_bytes),
            sha256_hash=sha256,
            uploader_principal=uploader_principal,
            download_url=f"/api/v1/attachments/{sha256}/download",
            metadata=metadata or {}
        )

        all_meta = self._read_json(self.attachments_meta_file)
        all_meta[meta.id] = meta.model_dump()
        # Also index by sha256 for CAS lookups
        all_meta[sha256] = meta.model_dump()
        self._write_json(self.attachments_meta_file, all_meta)

        return meta

    def get_attachment_metadata(self, key: str) -> Optional[AttachmentMetadata]:
        all_meta = self._read_json(self.attachments_meta_file)
        raw = all_meta.get(key)
        if raw:
            return AttachmentMetadata(**raw)
        return None

    def get_attachment_bytes(self, sha256_or_id: str) -> Optional[bytes]:
        meta = self.get_attachment_metadata(sha256_or_id)
        if meta:
            blob_path = self.attachments_dir / meta.sha256_hash
            if blob_path.exists():
                return blob_path.read_bytes()
        # Fallback: check if the key is directly the sha256 hash
        blob_path = self.attachments_dir / sha256_or_id
        if blob_path.exists():
            return blob_path.read_bytes()
        return None

    # --- Messages ---

    def save_message(self, message: MessageRecord) -> MessageRecord:
        with open(self.messages_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message.model_dump()) + "\n")
        return message

    def list_messages(
        self,
        recipient: Optional[str] = None,
        channel: Optional[str] = None,
        sender: Optional[str] = None,
        limit: int = 50
    ) -> List[MessageRecord]:
        messages = []
        if not self.messages_file.exists():
            return messages

        with open(self.messages_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    msg = MessageRecord(**record)
                    
                    # Filtering
                    if channel and msg.channel != channel:
                        continue
                    if sender and msg.sender_principal != sender:
                        continue
                    if recipient and recipient != "all":
                        if msg.recipient not in (recipient, "broadcast", "*", "all"):
                            continue
                            
                    messages.append(msg)
                except Exception:
                    continue

        messages.sort(key=lambda m: m.created_at, reverse=True)
        return messages[:limit]

    # --- Fiscal Ledger ---

    def record_ledger_entry(self, entry: FiscalLedgerEntry) -> FiscalLedgerEntry:
        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.model_dump()) + "\n")
        return entry

    def get_ledger_summary(self, principal: Optional[str] = None) -> Dict[str, Any]:
        total_spent = 0
        total_earned = 0
        transaction_count = 0
        
        if self.ledger_file.exists():
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        amt = float(entry.get("amount", 0))
                        c = entry.get("consumer_principal")
                        p = entry.get("provider_principal")
                        
                        if principal:
                            if c == principal:
                                total_spent += amt
                                transaction_count += 1
                            if p == principal:
                                total_earned += amt
                                transaction_count += 1
                        else:
                            total_spent += amt
                            transaction_count += 1
                    except Exception:
                        continue
                        
        return {
            "principal": principal or "all",
            "total_spent_sat": total_spent,
            "total_earned_sat": total_earned,
            "transaction_count": transaction_count
        }

    # --- Helpers ---

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _write_json(self, path: Path, data: Dict[str, Any]):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

storage = ObolStorage()
