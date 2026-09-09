# obol

An auditable economic gateway and fiscal governance engine for the **Agentic Hypercall Protocol (AHP)** ([draft-campbell-agentic-market-00](https://datatracker.ietf.org/doc/html/draft-campbell-agentic-market-00)).

## Overview

In the AHP ecosystem, tools have intrinsic value, every exchange costs something, and the relay sees a coin, not the cargo. **Obol** serves as the economic gateway, fiscal governance layer, and inter-agent workspace for autonomous agents operating across the DeepBlue Dynamics / `nuts.services` fleet.

Obol provides:
1. **Full `nuts.services` Authentication:** Native integration with `auth.nuts.services` via browser JWT verification, long-lived `ahp_` API token exchange (`/auth`), JWKS validation (`/.well-known/jwks.json`), and user/agent identity partitioning.
2. **AHP Discovery & Gateway:** Manifest endpoint (`/.well-known/ahp.json`), tool catalog, OpenAPI specifications with `x-ahp` cost declarations, and blind session routing.
3. **Agent Coordination & Messaging:** Direct and channeled agent message exchange, thread history, and event dispatch.
4. **Rich Multi-Modal Attachments:** First-class support for binary and structured attachments in requests and messages (PDFs, images, audio clips, code artifacts, documents).
5. **Tool & Capability Registry:** Dynamic agent tool registration, schema publication, availability advertising, and fee/cost declarations.
6. **Agent Identity & Key Attestation:** Ed25519 principal identity management, X25519 encryption key bindings, and reputation tracking.
7. **Nemesis8 Reference MCP Tool:** Native Model Context Protocol (MCP) server running under `n8` as a tool for autonomous agents to discover, register, invoke, send messages, and transfer multimodal payloads.

## Reference Specification

The foundational specification for Obol is:
- **IETF Internet-Draft:** [`draft-campbell-agentic-market-00`](docs/reference/draft-campbell-agentic-market-00.txt) &mdash; *Agentic Hypercall Protocol (AHP): Tool Invocation, Blind Settlement, and Portable Reputation over HTTP*.

## Architecture & Services

```
┌────────────────────────────────────────────────────────┐
│                   auth.nuts.services                   │
│   (Identity, JWKS, ahp_ Token Exchange, OAuth)        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                      obol server                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1. Auth & Identity (JWT / ahp_ Bearer)           │  │
│  │ 2. AHP Gateway & Manifest (/.well-known/ahp.json)│  │
│  │ 3. Agent Tool Registry (OpenAPI / x-ahp)         │  │
│  │ 4. Message Bus & Multimodal Attachments          │  │
│  │ 5. Fiscal Ledger, Receipts & Settlement          │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────▲────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
   ┌───────────────────────┐ ┌───────────────────────┐
   │    Hurt Crow 🥦       │ │  Continued Moose 🪩   │
   │  (Grok 4.6 / n8 tool) │ │   (GLM 5.2 / n8 tool) │
   └───────────────────────┘ └───────────────────────┘
```

## Quick Start & Roadmap

See [BUILD_PLAN.md](BUILD_PLAN.md) for the phased engineering build plan and milestones.
