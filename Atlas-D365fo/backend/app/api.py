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
from app.d365.er import parse_er_config
from app.d365.xpp import parse_xpp
from app.generate.er_report import validate_er_config
from app.generate.openapi import build_openapi
from app.generate.postman import build_postman_collection

router = APIRouter()


class IngestRequest(BaseModel):
    edmx_xml: str | None = None  # provide XML for offline ingestion


class XppIngestRequest(BaseModel):
    service_group: str
    sources: list[str]  # raw X++ file contents


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


@router.post("/xpp/ingest")
async def xpp_ingest(request: Request, body: XppIngestRequest) -> dict:
    """Parse X++ source files into the service surface D365 never publishes."""
    all_contracts, all_services = [], []
    for source in body.sources:
        contracts, services = parse_xpp(source)
        all_contracts.extend(contracts)
        all_services.extend(services)
    if not all_services:
        raise HTTPException(
            422, "No service operations found — expected [SysEntryPointAttribute] methods"
        )
    request.app.state.xpp = {
        "service_group": body.service_group,
        "contracts": all_contracts,
        "services": all_services,
    }
    return {
        "service_group": body.service_group,
        "services": {s.name: [o.name for o in s.operations] for s in all_services},
        "contracts": {c.name: [m.name for m in c.members] for c in all_contracts},
    }


@router.get("/xpp/openapi")
async def xpp_openapi(request: Request) -> dict:
    xpp = getattr(request.app.state, "xpp", None)
    if not xpp:
        raise HTTPException(404, "No X++ source ingested — run /xpp/ingest first")
    return build_openapi(xpp["service_group"], xpp["services"], xpp["contracts"])


@router.get("/xpp/postman")
async def xpp_postman(request: Request) -> dict:
    xpp = getattr(request.app.state, "xpp", None)
    if not xpp:
        raise HTTPException(404, "No X++ source ingested — run /xpp/ingest first")
    return build_postman_collection(xpp["service_group"], xpp["services"], xpp["contracts"])


class ERIngestRequest(BaseModel):
    er_xml: str


@router.post("/er/ingest")
async def er_ingest(request: Request, body: ERIngestRequest) -> dict:
    """Parse an exported ER configuration for offline validation."""
    try:
        config = parse_er_config(body.er_xml)
    except Exception as exc:  # noqa: BLE001 — surface any XML failure as 422
        raise HTTPException(422, f"Could not parse ER XML: {exc}") from exc
    if not config.model_nodes and not config.format_elements:
        raise HTTPException(422, "No ER model nodes or format elements found")
    request.app.state.er = config
    return {
        "name": config.name,
        "type": config.config_type,
        "model_nodes": len(config.model_nodes),
        "format_elements": len(config.format_elements),
    }


@router.get("/er/report")
async def er_report(request: Request) -> dict:
    config = getattr(request.app.state, "er", None)
    if config is None:
        raise HTTPException(404, "No ER config ingested — run /er/ingest first")
    findings = validate_er_config(config)
    return {
        "name": config.name,
        "model_paths": [n.path for n in config.model_nodes],
        "format_elements": [
            {
                "name": f.name,
                "type": f.element_type,
                "bindings": f.bindings,
                "formulas": f.formulas,
            }
            for f in config.format_elements
        ],
        "findings": [
            {
                "severity": f.severity,
                "kind": f.kind,
                "location": f.location,
                "detail": f.detail,
            }
            for f in findings
        ],
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
    }


def make_doc_index(docs: list[EntityDoc]) -> dict[str, EntityDoc]:
    return {d.name: d for d in docs}
