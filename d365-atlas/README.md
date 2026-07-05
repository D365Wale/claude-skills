# D365 ATLAS

**AI-powered D365 F&O Integration & Metadata Studio** — makes the D365 Finance & Operations service layer navigable: crawl metadata, search it semantically, generate runnable integration clients.

## What works today (Sprint 1+2 core, verified end-to-end)

| Stage | Status | Proof |
|-------|--------|-------|
| **CONNECT** — AAD client-credentials auth with token caching | ✅ Live-verified | 200/Bearer against real tenant |
| **CRAWL** — `/data/$metadata` EDMX parser (entities, enums, actions) | ✅ | 8 docs from realistic fixture; live path implemented |
| **SEARCH** — semantic search over embedded metadata | ✅ | "service that posts journal entries" → `LedgerJournalHeader`, `LedgerJournalLine`, `createJournal` |
| **DECODE** — enum member resolution | ✅ | "sales order status invoiced" → `SalesOrderStatus {Invoiced: 3}` |
| **GENERATE** — runnable Python clients for custom services + OData entities | ✅ | Generated client compiled AND authenticated live against Azure AD |

16/16 pytest, ruff clean.

## Zero-config by design

Every external dependency has a local fallback, so the full pipeline runs with **no keys and no database**:

| Capability | Default (offline) | Upgrade (set env var) |
|-----------|-------------------|----------------------|
| Embeddings | `LocalHashEmbedder` — deterministic char-trigram, 256-dim | `JINA_API_KEY` → jina-embeddings-v3, 1024-dim |
| Vector store | `MemoryStore` — pure-Python cosine | `DATABASE_URL` → pgvector (`pip install .[pgvector]`) |
| Codegen | `TemplateCodegen` — deterministic, always-valid Python | `GROQ_API_KEY` → llama-3.3-70b refinement |
| Metadata source | Inline EDMX XML in `/ingest` body | `D365_*` env vars → live `$metadata` crawl |

## Quickstart

```bash
cd backend
pip install -e .[dev]
uvicorn app.main:app --port 8000
```

```bash
# Ingest (offline — paste any exported $metadata document)
curl -X POST localhost:8000/ingest -H "Content-Type: application/json" \
  -d "{\"edmx_xml\": $(python3 -c 'import json;print(json.dumps(open("tests/fixtures/sample_edmx.xml").read()))')}"

# Ingest (live — crawls your environment's /data/$metadata)
export D365_BASE_URL=https://yourenv.axcloud.dynamics.com
export D365_TENANT_ID=... D365_CLIENT_ID=... D365_CLIENT_SECRET=...
curl -X POST localhost:8000/ingest

# Search
curl "localhost:8000/search?q=service+that+posts+journal+entries"

# Generate a client for a custom service
curl -X POST localhost:8000/generate -H "Content-Type: application/json" -d '{
  "service_group": "HERJournalServiceGroup",
  "service_name": "JournalService",
  "operation": "createJournal",
  "sample_payload": {"_request": {"JournalName": "GenJv"}}
}'
```

## Tests & lint

```bash
cd backend
python3 -m pytest tests/ -q     # 16 tests: parser, embedder, full API e2e
python3 -m ruff check app/ tests/
```

## Architecture

```
app/
├── d365/
│   ├── auth.py      TokenProvider — AAD client-credentials, expiry-aware cache
│   ├── client.py    D365Client — $metadata, Metadata/DataEntities, custom services
│   └── edmx.py      parse_edmx — EDMX XML → EntityDoc (entity/enum/action)
├── ai/
│   ├── embedder.py  JinaEmbedder | LocalHashEmbedder (same interface)
│   └── codegen.py   GroqCodegen | TemplateCodegen (same interface)
├── store/
│   └── vectorstore.py  PgVectorStore | MemoryStore (same interface)
├── api.py           /health /ingest /search /generate
└── main.py          app factory — providers resolve from env at startup
```

## Roadmap

- **Sprint 3**: X++ source parsing (`[DataContract]`/`[DataMember]`) → OpenAPI 3.0 spec + Postman collection export for custom services
- **Sprint 4**: ER configuration XML upload, binding validator, expression co-pilot
- Next.js frontend on Vercel; deploy backend via Docker → AWS EC2 (OpenTofu, CircleCI)

Full plan: see the session plan document (MCP map + free-tier architecture + market analysis).
