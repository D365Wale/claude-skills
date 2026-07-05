# Atlas — D365 F&O Integration & Metadata Studio

**Atlas** makes the Microsoft Dynamics 365 Finance & Operations service layer navigable:
crawl metadata, search it semantically, and generate runnable integration clients,
OpenAPI specs, and Postman collections — none of which D365 provides out of the box.

> Standalone extraction of the `d365-atlas` project. Self-contained: backend + frontend
> + Docker + CI + deploy config. Runs fully offline (no API keys, no database) via local
> fallbacks; set env vars to upgrade to Jina / Groq / pgvector.

## Quick start (local, offline)

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --port 8000

# Frontend (separate terminal)
cd frontend
npm install
ATLAS_API_URL=http://127.0.0.1:8000 npm run dev
# open http://localhost:3000
```

Or the whole stack in containers:

```bash
docker compose up
```

## What works (verified end-to-end)

| Stage | Description |
|-------|-------------|
| **CONNECT** | Azure AD client-credentials auth with token caching (live-verified against real tenant) |
| **CRAWL** | `/data/$metadata` EDMX parser → entities, enums, service actions |
| **SEARCH** | Semantic search over embedded metadata (Jina v3 or local fallback) |
| **DECODE** | Enum member resolution (`SalesOrderStatus: 1=Backorder, 3=Invoiced`) |
| **GENERATE** | Runnable Python clients for custom services + OData entities |
| **X++ PARSE** | `[DataContractAttribute]` / `[SysEntryPointAttribute]` extraction from raw X++ |
| **OPENAPI** | OpenAPI 3.0 spec generation for custom services |
| **POSTMAN** | Collection v2.1 export with Get-Token + bearer-auth pattern |

## Architecture

```
Next.js (Vercel)  ──►  FastAPI (Docker / EC2)  ──►  PostgreSQL + pgvector
                        ├── LangGraph-ready pipeline
                        ├── Jina embeddings   (fallback: local hash embedder)
                        ├── Groq codegen      (fallback: deterministic templates)
                        └── D365 OAuth client (client-credentials)
```

Every external dependency has a zero-config local fallback, so the full pipeline runs
with no keys and no database.

## Layout

```
Atlas-D365fo/
├── backend/          FastAPI app + pytest suite (22 tests)
├── frontend/         Next.js 15 UI (search + X++ catalog)
├── Dockerfile        Backend container
├── docker-compose.yml  Full local stack
├── .circleci/        CI: ruff + pytest + build + docker
├── deploy/           OpenTofu skeleton (AWS)
├── PUSH_AND_DEPLOY.md  One-command push + deploy runbook
└── EVIDENCE.md       Test + screenshot evidence log
```

## Deploy

See [PUSH_AND_DEPLOY.md](PUSH_AND_DEPLOY.md) for exact commands: push to your own
GitHub repo, deploy the frontend to Vercel, and run the backend via Docker or AWS.

## License

MIT — see [LICENSE](LICENSE).
