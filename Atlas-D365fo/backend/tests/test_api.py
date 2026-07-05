"""End-to-end API tests: ingest -> search -> generate, all offline."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def ingested(client, sample_edmx):
    resp = client.post("/ingest", json={"edmx_xml": sample_edmx})
    assert resp.status_code == 200
    assert resp.json()["ingested"] == 8  # 5 entities + 2 enums + 1 action
    return client


def test_health_reports_providers(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["embedder"] == "LocalHashEmbedder"
    assert body["store"] == "MemoryStore"


def test_ingest_requires_xml_or_d365_config(client, monkeypatch):
    for var in ("D365_BASE_URL", "D365_TENANT_ID", "D365_CLIENT_ID", "D365_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    resp = client.post("/ingest", json={})
    assert resp.status_code == 400


def test_search_finds_journal_entity(ingested):
    body = ingested.get("/search", params={"q": "journal entries posting"}).json()
    top_names = [r["name"] for r in body["results"][:3]]
    assert any("Journal" in name for name in top_names), f"got {top_names}"


def test_search_finds_customer_entity(ingested):
    body = ingested.get("/search", params={"q": "customer account credit limit"}).json()
    assert any("Customer" in r["name"] for r in body["results"][:3])


def test_search_surfaces_enum_members(ingested):
    body = ingested.get("/search", params={"q": "sales order status values"}).json()
    enum_hits = [r for r in body["results"] if r["kind"] == "enum"]
    assert enum_hits and enum_hits[0]["members"]["Invoiced"] == 3


def test_generate_service_client_compiles(ingested):
    resp = ingested.post(
        "/generate",
        json={
            "service_group": "HERJournalServiceGroup",
            "service_name": "JournalService",
            "operation": "createJournal",
            "sample_payload": {"_request": {"JournalName": "GenJv"}},
        },
    )
    assert resp.status_code == 200
    code = resp.json()["code"]
    compile(code, "generated_client.py", "exec")  # must be valid Python
    assert "/api/services/HERJournalServiceGroup/JournalService/createJournal" in code
    assert "Retry-After" in code  # throttling handled


def test_generate_entity_client_compiles(ingested):
    resp = ingested.post("/generate", json={"entity_name": "CustomerV3"})
    assert resp.status_code == 200
    code = resp.json()["code"]
    compile(code, "generated_client.py", "exec")
    assert "/data/CustomersV3" in code


def test_generate_unknown_entity_404(ingested):
    assert ingested.post("/generate", json={"entity_name": "Nope"}).status_code == 404


def test_generate_instruction_without_groq_key_422(ingested):
    resp = ingested.post(
        "/generate", json={"entity_name": "CustomerV3", "instruction": "add retries"}
    )
    assert resp.status_code == 422
