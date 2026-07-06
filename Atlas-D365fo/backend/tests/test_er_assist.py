import pathlib

import pytest
from fastapi.testclient import TestClient

from app.ai.embedder import LocalHashEmbedder
from app.d365.er import parse_er_config
from app.generate.er_assist import search_formulas, suggest_bindings, suggest_fixes
from app.generate.er_report import validate_er_config
from app.main import create_app

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "sample_er_config.xml").read_text()


def _config():
    return parse_er_config(FIXTURE)


def test_broken_binding_gets_closest_path_suggestion():
    config = _config()
    enriched = suggest_fixes(validate_er_config(config), config)
    broken = next(f for f in enriched if f["kind"] == "broken-binding")
    # FullName -> closest real path is Creditor.Name
    assert "model.Payment.Creditor.Name" in broken["suggestion"]


def test_unknown_function_gets_closest_fn_suggestion():
    config = _config()
    enriched = suggest_fixes(validate_er_config(config), config)
    unknown = next(f for f in enriched if "Unknown ER function" in f["detail"])
    assert "ROUND(...)" in unknown["suggestion"]


def test_unbalanced_paren_gets_actionable_suggestion():
    config = _config()
    enriched = suggest_fixes(validate_er_config(config), config)
    paren = next(f for f in enriched if "Unbalanced parentheses" in f["detail"])
    assert "closing parenthesis" in paren["suggestion"]


@pytest.mark.asyncio
async def test_suggest_bindings_ranks_relevant_path_first():
    ranked = await suggest_bindings("creditor account number", _config(), LocalHashEmbedder())
    assert ranked[0]["path"] == "model.Payment.Creditor.AccountNumber"


@pytest.mark.asyncio
async def test_search_formulas_finds_date_pattern():
    ranked = await search_formulas("format a date", LocalHashEmbedder())
    assert "DATEFORMAT" in ranked[0]["pattern"]


def test_report_includes_suggestions_and_new_endpoints():
    client = TestClient(create_app())
    assert client.post("/er/ingest", json={"er_xml": FIXTURE}).status_code == 200

    report = client.get("/er/report").json()
    assert any(f["suggestion"] for f in report["findings"])

    suggest = client.get("/er/suggest", params={"field": "creditor account number"}).json()
    assert suggest["suggestions"][0]["path"] == "model.Payment.Creditor.AccountNumber"

    formulas = client.get("/er/formulas", params={"q": "sum line amounts"}).json()
    assert any("SUM" in p["pattern"] for p in formulas["patterns"])


def test_suggest_before_ingest_404():
    client = TestClient(create_app())
    assert client.get("/er/suggest", params={"field": "x"}).status_code == 404
