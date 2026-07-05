import pathlib

from fastapi.testclient import TestClient

from app.d365.er import parse_er_config
from app.generate.er_report import validate_er_config
from app.main import create_app

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "sample_er_config.xml").read_text()


def test_parses_model_tree_and_format():
    config = parse_er_config(FIXTURE)
    assert config.name == "ISO20022 Credit Transfer"
    assert config.config_type == "Format"
    paths = {n.path for n in config.model_nodes}
    assert "model.Payment.Lines.Amount" in paths
    assert len(config.format_elements) == 6
    rmt = next(f for f in config.format_elements if f.name == "RmtInf")
    assert rmt.bindings == ["model.Payment.Lines.Reference"]
    assert rmt.formulas == ["TRIM(model.Payment.Lines.Reference)"]


def test_detects_broken_binding():
    findings = validate_er_config(parse_er_config(FIXTURE))
    broken = [f for f in findings if f.kind == "broken-binding"]
    assert len(broken) == 1
    assert broken[0].location == "CdtrNm"
    assert "model.Payment.Creditor.FullName" in broken[0].detail
    assert broken[0].severity == "error"


def test_detects_expression_defects():
    findings = validate_er_config(parse_er_config(FIXTURE))
    expr = [f for f in findings if f.kind == "expression"]
    details = " | ".join(f.detail for f in expr)
    assert "Unbalanced parentheses" in details
    assert "ROUNDX" in details  # unknown function
    assert all(f.location == "Amt" for f in expr)


def test_valid_bindings_produce_no_findings():
    findings = validate_er_config(parse_er_config(FIXTURE))
    flagged = {f.location for f in findings}
    assert "Ccy" not in flagged  # valid binding
    assert "MsgId" not in flagged  # valid formula (known fns, resolvable path)
    assert "RmtInf" not in flagged  # valid binding + formula


def test_api_roundtrip():
    client = TestClient(create_app())
    resp = client.post("/er/ingest", json={"er_xml": FIXTURE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_nodes"] == 9
    assert body["format_elements"] == 6

    report = client.get("/er/report").json()
    assert report["errors"] == 2  # broken binding + unbalanced paren
    assert report["warnings"] == 1  # ROUNDX unknown fn


def test_report_before_ingest_404():
    client = TestClient(create_app())
    assert client.get("/er/report").status_code == 404


def test_ingest_rejects_garbage():
    client = TestClient(create_app())
    assert client.post("/er/ingest", json={"er_xml": "not xml at all"}).status_code == 422
    assert (
        client.post("/er/ingest", json={"er_xml": "<Empty/>"}).status_code == 422
    )
