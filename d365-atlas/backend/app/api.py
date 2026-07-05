"""ATLAS HTTP API.

POST /ingest    — crawl D365 $metadata (live) or accept EDMX XML in the body
                  (offline), parse, embed, store.
GET  /search    — semantic search over ingested entities/enums/actions.
POST /generate  — produce a runnable Python client for a search hit or a
                  named custom service. Optional Groq refinement.
GET  /health    — liveness + doc count + active providers.
"""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.d365.auth import TokenProvider
from app.d365.client import D365Client
from app.d365.edmx import EntityDoc, parse_edmx

router = APIRouter()


class IngestRequest(BaseModel):
    edmx_xml: str | None = None  # provide XML for offline ingestion


class GenerateRequest(BaseModel):
    # Either reference an ingested entity by name...
    entity_name: str | None = None
    # ...or spell out a custom service target.
    service_group: str | None = None
    service_name: str | None = None
    operation: str | None = None
    sample_payload: dict | None = None
    # Optional natural-language refinement (needs GROQ_API_KEY).
    instruction: str | None = None


@router.get("/health")
async def health(request: Request) -> dict:
    state = request.app.state
    return {
        "status": "ok",
        "documents": await state.store.count(),
        "embedder": type(state.embedder).__name__,
        "store": type(state.store).__name__,
        "groq_enabled": state.groq is not None,
        "d365_configured": state.settings.d365_configured,
    }


@router.post("/ingest")
async def ingest(request: Request, body: IngestRequest | None = None) -> dict:
    state = request.app.state
    body = body or IngestRequest()
    if body.edmx_xml:
        xml_text = body.edmx_xml
        source = "inline"
    elif state.settings.d365_configured:
        settings = state.settings
        client = D365Client(
            settings.d365_base_url,
            TokenProvider(
                settings.d365_tenant_id,
                settings.d365_client_id,
                settings.d365_client_secret,
                settings.d365_base_url,
            ),
        )
        xml_text = await client.fetch_metadata_xml()
        source = "live"
    else:
        raise HTTPException(
            400, "Provide edmx_xml in the body or set D365_* environment variables"
        )

    docs = parse_edmx(xml_text)
    if not docs:
        raise HTTPException(422, "No entities found in EDMX document")

    texts = [d.to_text() for d in docs]
    vectors = await state.embedder.embed(texts, task="retrieval.passage")
    for doc, vec in zip(docs, vectors, strict=True):
        await state.store.upsert(
            f"{doc.kind}:{doc.name}",
            vec,
            {
                "name": doc.name,
                "kind": doc.kind,
                "entity_set": doc.entity_set,
                "keys": doc.keys,
                "fields": doc.fields,
                "members": doc.members,
            },
        )
    state.docs_by_name = {d.name: d for d in docs}
    return {"ingested": len(docs), "source": source}


@router.get("/search")
async def search(request: Request, q: str = Query(min_length=1), top_k: int = 5) -> dict:
    state = request.app.state
    vec = (await state.embedder.embed([q], task="retrieval.query"))[0]
    hits = await state.store.search(vec, top_k=top_k)
    return {
        "query": q,
        "results": [
            {
                "name": h.payload["name"],
                "kind": h.payload["kind"],
                "entity_set": h.payload.get("entity_set", ""),
                "score": round(h.score, 4),
                "keys": h.payload.get("keys", []),
                "field_count": len(h.payload.get("fields", [])),
                "members": h.payload.get("members", {}),
            }
            for h in hits
        ],
    }


@router.post("/generate")
async def generate(request: Request, body: GenerateRequest) -> dict:
    state = request.app.state
    if body.service_group and body.service_name and body.operation:
        code = state.codegen.generate_service_client(
            body.service_group, body.service_name, body.operation, body.sample_payload
        )
        target = f"{body.service_group}/{body.service_name}/{body.operation}"
    elif body.entity_name:
        doc = state.docs_by_name.get(body.entity_name)
        if doc is None:
            raise HTTPException(404, f"Entity '{body.entity_name}' not ingested — run /ingest")
        if doc.kind == "enum":
            raise HTTPException(422, "Enums decode values; generate clients for entities")
        code = state.codegen.generate_entity_client(doc)
        target = doc.name
    else:
        raise HTTPException(400, "Provide entity_name or service_group+service_name+operation")

    refined = False
    if body.instruction:
        if state.groq is None:
            raise HTTPException(422, "instruction requires GROQ_API_KEY")
        code = await state.groq.refine(code, body.instruction)
        refined = True

    return {"target": target, "refined": refined, "code": code}


def make_doc_index(docs: list[EntityDoc]) -> dict[str, EntityDoc]:
    return {d.name: d for d in docs}
