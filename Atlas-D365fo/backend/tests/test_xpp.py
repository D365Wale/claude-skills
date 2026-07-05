import pathlib

from app.d365.xpp import parse_xpp
from app.generate.openapi import build_openapi
from app.generate.postman import build_postman_collection

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "HERJournalService.xpp").read_text()


def test_parses_contracts_with_members():
    contracts, _ = parse_xpp(FIXTURE)
    by_name = {c.name: c for c in contracts}
    assert set(by_name) == {
        "HERJournalLineContract",
        "HERJournalRequestContract",
        "HERJournalResponseContract",
    }
    req = by_name["HERJournalRequestContract"]
    assert [m.name for m in req.members] == [
        "JournalName",
        "Description",
        "JournalType",
        "PostingLayer",
    ]
    resp = by_name["HERJournalResponseContract"]
    assert {m.name: m.xpp_type for m in resp.members} == {
        "JournalNum": "str",
        "Success": "boolean",
    }


def test_parses_service_operations():
    _, services = parse_xpp(FIXTURE)
    assert len(services) == 1
    svc = services[0]
    assert svc.name == "HERJournalService"
    ops = {o.name: o for o in svc.operations}
    assert set(ops) == {"createJournal", "getJournalStatus"}
    assert ops["createJournal"].return_type == "HERJournalResponseContract"
    assert ops["createJournal"].parameters[0].name == "request"
    assert ops["createJournal"].parameters[0].xpp_type == "HERJournalRequestContract"


def test_openapi_spec_shape():
    contracts, services = parse_xpp(FIXTURE)
    spec = build_openapi("HERJournalServiceGroup", services, contracts)
    assert spec["openapi"] == "3.0.3"
    path = "/api/services/HERJournalServiceGroup/HERJournalService/createJournal"
    assert path in spec["paths"]
    post = spec["paths"][path]["post"]
    # request param is a contract -> $ref into components
    req_schema = post["requestBody"]["content"]["application/json"]["schema"]
    assert req_schema["properties"]["request"] == {
        "$ref": "#/components/schemas/HERJournalRequestContract"
    }
    # contract schemas materialized with correct JSON types
    resp_schema = spec["components"]["schemas"]["HERJournalResponseContract"]
    assert resp_schema["properties"]["Success"] == {"type": "boolean"}
    assert "429" in post["responses"]


def test_postman_collection_shape():
    contracts, services = parse_xpp(FIXTURE)
    col = build_postman_collection("HERJournalServiceGroup", services, contracts)
    names = [item["name"] for item in col["item"]]
    assert names[0] == "Get Token"
    assert "HERJournalService.createJournal" in names
    # collection-level bearer auth, secret only referenced via variables
    assert col["auth"]["bearer"][0]["value"] == "{{access_token}}"
    assert all(v["value"] == "" for v in col["variable"])
    # sample body expands nested contract members
    create = next(i for i in col["item"] if i["name"] == "HERJournalService.createJournal")
    assert '"JournalName"' in create["request"]["body"]["raw"]


def test_api_endpoints_roundtrip(client=None):
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    resp = client.post(
        "/xpp/ingest",
        json={"service_group": "HERJournalServiceGroup", "sources": [FIXTURE]},
    )
    assert resp.status_code == 200
    assert resp.json()["services"] == {
        "HERJournalService": ["createJournal", "getJournalStatus"]
    }
    assert client.get("/xpp/openapi").status_code == 200
    postman = client.get("/xpp/postman").json()
    assert postman["info"]["schema"].endswith("v2.1.0/collection.json")


def test_xpp_ingest_rejects_sources_without_services():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    resp = client.post(
        "/xpp/ingest", json={"service_group": "G", "sources": ["class Foo {}"]}
    )
    assert resp.status_code == 422
