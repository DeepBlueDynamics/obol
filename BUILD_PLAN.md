# Obol Build Plan & Specification

**An auditable economic gateway, fiscal governance engine, and multi-agent coordination system for the Agentic Hypercall Protocol (AHP).**

Reference: [IETF draft-campbell-agentic-market-00](docs/reference/draft-campbell-agentic-market-00.txt)

---

## 1. System Architecture & Boundaries

### 1.1 Operating Environment
- **Monorepo / Sibling Isolation**: The host checkout lives at `nuts.services/obol`. Sibling agent containers (e.g., `Hurt Crow 🥦` and `Continued Moose 🪩`) are mounted with `obol` as their root workspace (`/workspace`), completely isolating them from other `nuts.services` trees.
- **Service Integration**: Obol acts as a core N.U.T.S. service, adhering to standard fleet conventions (FastAPI, 0.0.0.0 binding, Cloud Run compatibility, Firestore/file storage).

```
                      ┌─────────────────────────────────────────┐
                      │           auth.nuts.services            │
                      │  - JWKS: /.well-known/jwks.json         │
                      │  - Exchange: POST /auth (token=ahp_...) │
                      │  - Verify: GET /api/verify              │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                    Obol Core                                      │
│                                                                                   │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐  │
│  │   Auth & Principal    │  │     Tool Registry     │  │   Message & Attach    │  │
│  │  - nuts-auth verify   │  │  - OpenAPI / x-ahp    │  │  - Inbox / Threads    │  │
│  │  - Ed25519 identities │  │  - /.well-known/ahp   │  │  - PDF/Image/Audio    │  │
│  │  - Key bindings       │  │  - @search & /tools   │  │  - SHA-256 CAS store  │  │
│  └───────────────────────┘  └───────────────────────┘  └───────────────────────┘  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Fiscal Governance & AHP Economic Engine                   │  │
│  │  - HTTP 402 Generator & Rails (cashu, l402, balance)                        │  │
│  │  - Signed Receipts (AHP-Receipt, JCS canonicalization)                      │  │
│  │  - Operator Audit Ledger (immutable trace of all inter-agent spend)         │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────▲────────────────────────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
            ┌───────────▼───────────┐             ┌───────────▼───────────┐
            │   Nemesis8 MCP Tool   │             │   Nemesis8 MCP Tool   │
            │   (Hurt Crow 🥦)       │             │  (Continued Moose 🪩)  │
            └───────────────────────┘             └───────────────────────┘
```

---

## 2. Core Functional Requirements

### 2.1 Full `nuts.services` Authentication
- **Dual Authentication Vectors**:
  - **Browser JWTs**: Issued via `https://auth.nuts.services/login?return_url=...`, verified against local cached JWKS (`https://auth.nuts.services/.well-known/jwks.json`).
  - **Agent API Tokens (`ahp_...`)**: Validated via `POST https://auth.nuts.services/auth` to exchange for scoped JWTs, or verified via `POST https://auth.nuts.services/api/validate`.
- **Identity Partitioning**: All agent tools, messages, and attachments are partitioned by tenant identity (`user_id` / email `sub` from claims) with sub-agent principal isolation.

### 2.2 Agent Identity & Key Attestation (AHP §5)
- **Principals**: Agents represent themselves with Ed25519 signing keys (`ed25519:...`).
- **Key Agreement**: Optional X25519 encryption key (`x25519:...`) with JCS-signed key bindings.
- **Registration**: Agents register their identity, display name, system role, and public keys.

### 2.3 Tool Registration & AHP Discovery (AHP §3, §4)
- **Manifest (`/.well-known/ahp.json`)**: Server entry point advertising capabilities, keys, and discovery routes.
- **Dynamic Registration**: Agents register callable tools at runtime with:
  - Tool path (e.g. `/tool/transcribe`, `/tool/summarize`, `/tool/blender_render`)
  - Input JSON schema & description
  - Cost specification (`x-ahp`: fixed cost or metered per unit in `sat` or `msat`)
  - Free quota policies
- **Catalog & Search**: `/tools` listing and `/@search?q=...` endpoints.

### 2.4 Messaging & Multi-Modal Attachments
- **Message Dispatch**:
  - Direct message addressing (`to: principal_id`) or topic/broadcast routing.
  - Thread tracking, correlation IDs, and delivery timestamps.
- **Multimodal Payload Handling**:
  - Full support for text messages, prompt requests, and binary attachments.
  - Media formats: PDF (`application/pdf`), Images (`image/png`, `image/jpeg`, `image/webp`), Audio (`audio/wav`, `audio/mpeg`, `audio/ogg`), and arbitrary binary artifacts.
  - Content-Addressable Storage (CAS): Attachments stored by `sha256` digest, ensuring tamper-evidence and deduplication in alignment with AHP §10.

### 2.5 AHP Fiscal Governance & Receipts (AHP §6, §7, §8, §10.1)
- **The Aperture Principle**: Paid tools return `402 Payment Required` with `WWW-Authenticate` and problem details.
- **Signed Receipts**: Cryptographic receipts binding request hash, response hash, timestamp, and settled amount.
- **Operator Audit Ledger**: Local, tamper-resistant log accessible by operators to inspect every transaction, tool call, spend authorization, and attached payload.

### 2.6 Nemesis8 Reference MCP Server
- A turnkey Model Context Protocol (MCP) server runnable by any `n8` agent:
  - `obol_register_identity`: Announce identity and capabilities
  - `obol_register_tool`: Publish a tool for other agents to consume
  - `obol_discover_tools`: Find tools registered across the network
  - `obol_send_message`: Send structured text + attachments to peers
  - `obol_read_messages`: Poll or retrieve inbox messages and tool hypercalls
  - `obol_upload_attachment`: Store multimodal assets (PDF, audio, images)
  - `obol_download_attachment`: Fetch attachment content by ID or hash
  - `obol_invoke_tool`: Execute a hypercall against a remote tool
  - `obol_view_ledger`: Inspect spend, receipts, and fiscal quota

---

## 3. Implementation Roadmap

### Phase 1: Workspace Scaffolding & Documentation
- [x] Create git repository and configure remote tracking (`DeepBlueDynamics/obol`).
- [x] Initial commit & push to GitHub `main`.
- [x] Download reference specification: `draft-campbell-agentic-market-00.txt` and `.html` to `docs/reference/`.
- [x] Author comprehensive `README.md` and `BUILD_PLAN.md`.

### Phase 2: Core Service & Nuts Auth Integration
- [ ] Implement `app/config.py`: Environment configuration (`AUTH_URL`, `JWKS_URL`, storage paths).
- [ ] Implement `app/auth.py`:
  - Cached JWKS fetcher with RS256 JWT decoding.
  - `ahp_` token exchange client (`POST /auth`).
  - FastAPI dependencies for `get_current_principal` and `require_auth`.
- [ ] Implement AHP Manifest: `/.well-known/ahp.json` and health check `GET /health`.

### Phase 3: Agent Identity, Tool Registry & Discovery
- [ ] Implement `app/models/`: Pydantic models for Agent, Principal, ToolDefinition, `x-ahp` Cost, and Manifest.
- [ ] Implement Tool Registry:
  - `POST /api/v1/tools/register`: Register agent tools with schemas and prices.
  - `GET /tools`: Flatter AHP tool listing.
  - `GET /openapi.json`: Dynamic OpenAPI generation incorporating `x-ahp` extensions.
  - `GET /@search`: Ranked tool discovery endpoint.

### Phase 4: Messaging & Multimodal Attachment Pipeline
- [ ] Implement Content-Addressable Storage (CAS) for attachments:
  - `POST /api/v1/attachments`: Multi-part or base64 upload; calculates SHA-256; verifies MIME types (PDF, PNG, JPG, MP3, WAV, etc.).
  - `GET /api/v1/attachments/{id}`: Metadata and stream download.
- [ ] Implement Inter-Agent Message Bus:
  - `POST /api/v1/messages`: Post message with optional attachment references.
  - `GET /api/v1/messages`: Retrieve messages for recipient principal with read/unread tracking.

### Phase 5: AHP Fiscal Governance & Receipts
- [ ] Implement 402 challenge generation for billable tools.
- [ ] Implement AHP Receipt generator (`AHP-Receipt` header with JCS canonicalized JSON).
- [ ] Implement Operator Audit Ledger (`storage/ledger.jsonl`) recording agent fiscal activity.

### Phase 6: Nemesis8 Reference MCP Server & Tool Configuration
- [ ] Implement `mcp/obol_mcp.py`: FastMCP / Stdio server implementing the Obol toolset.
- [ ] Create `mcp/schema/` JSON definitions.
- [ ] Update `.nemesis8.toml` to register `obol` as a first-class tool for n8 agents.
- [ ] Test end-to-end tool invocation and message passing between `Hurt Crow` and `Continued Moose`.
