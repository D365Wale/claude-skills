"""ER Assist — the co-pilot layer on top of the Sprint 4 validators.

Detection says WHAT is broken; this module says WHAT TO DO:
- suggest_fixes: attach a concrete suggestion to each finding (closest known
  function for typos, closest model path for broken bindings).
- suggest_bindings: natural-language field -> ranked model paths, using the
  same embedder that powers metadata search (Jina or local fallback).
- FORMULA_LIBRARY + search_formulas: common GER expression patterns,
  searchable by intent ("format a date", "sum lines").
"""
import difflib

from app.d365.er import ERConfig
from app.generate.er_report import KNOWN_ER_FUNCTIONS, Finding

_UNKNOWN_FN_PREFIX = "Unknown ER function '"


def suggest_fixes(findings: list[Finding], config: ERConfig) -> list[dict]:
    """Return findings as dicts with a `suggestion` attached where one exists."""
    model_paths = [n.path for n in config.model_nodes]
    out = []
    for f in findings:
        suggestion = ""
        if f.kind == "broken-binding":
            # detail format: "... references '<path>' — not in data model ..."
            path = f.detail.split("'")[1] if "'" in f.detail else ""
            close = difflib.get_close_matches(path, model_paths, n=1, cutoff=0.6)
            if close:
                suggestion = f"Did you mean '{close[0]}'?"
        elif f.kind == "expression" and _UNKNOWN_FN_PREFIX in f.detail:
            func = f.detail.split("'")[1]
            close = difflib.get_close_matches(func, sorted(KNOWN_ER_FUNCTIONS), n=1, cutoff=0.6)
            if close:
                suggestion = f"Did you mean {close[0]}(...)?"
        elif "Unbalanced parentheses" in f.detail:
            suggestion = "Add the missing closing parenthesis at the end of the formula."
        elif "Unbalanced quotes" in f.detail:
            suggestion = 'Close the open string literal with a matching ".'
        out.append(
            {
                "severity": f.severity,
                "kind": f.kind,
                "location": f.location,
                "detail": f.detail,
                "suggestion": suggestion,
            }
        )
    return out


async def suggest_bindings(query: str, config: ERConfig, embedder, top_k: int = 5) -> list[dict]:
    """Rank model paths against a natural-language field description.

    Embeds 'path segments + type' per node so 'creditor account' matches
    model.Payment.Creditor.AccountNumber via the same trigram/Jina space
    used for entity search.
    """
    nodes = config.model_nodes
    if not nodes:
        return []
    texts = [f"{n.path.replace('.', ' ')} {n.node_type}" for n in nodes]
    doc_vecs = await embedder.embed(texts, task="retrieval.passage")
    q_vec = (await embedder.embed([query], task="retrieval.query"))[0]

    def cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    scored = sorted(
        (
            {"path": n.path, "type": n.node_type, "score": round(cos(q_vec, v), 4)}
            for n, v in zip(nodes, doc_vecs, strict=True)
        ),
        key=lambda r: r["score"],
        reverse=True,
    )
    return scored[:top_k]


FORMULA_LIBRARY = [
    {
        "intent": "format a date as yyyy-MM-dd",
        "pattern": 'DATEFORMAT(model.Path.To.Date, "yyyy-MM-dd")',
    },
    {
        "intent": "sum amounts across a record list",
        "pattern": "SUM(model.Path.To.Lines.Amount)",
    },
    {
        "intent": "count records in a list",
        "pattern": "COUNT(model.Path.To.Lines)",
    },
    {
        "intent": "filter a record list by condition",
        "pattern": "FILTER(model.Path.To.Lines, model.Path.To.Lines.IsActive)",
    },
    {
        "intent": "first record or null when list empty",
        "pattern": "FIRSTORNULL(model.Path.To.Lines)",
    },
    {
        "intent": "join text values with separator",
        "pattern": 'CONCATENATE(model.A, "-", model.B)',
    },
    {
        "intent": "conditional value if else",
        "pattern": 'IF(model.Path.Amount > 0, "CRDT", "DBIT")',
    },
    {
        "intent": "round a number to 2 decimals",
        "pattern": "ROUND(model.Path.Amount, 2)",
    },
    {
        "intent": "pad account number with leading zeros",
        "pattern": 'PADLEFT(model.Path.AccountNumber, 10, "0")',
    },
    {
        "intent": "uppercase trimmed text",
        "pattern": "UPPER(TRIM(model.Path.Name))",
    },
]


async def search_formulas(query: str, embedder, top_k: int = 3) -> list[dict]:
    texts = [f["intent"] + " " + f["pattern"] for f in FORMULA_LIBRARY]
    doc_vecs = await embedder.embed(texts, task="retrieval.passage")
    q_vec = (await embedder.embed([query], task="retrieval.query"))[0]

    def cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    ranked = sorted(
        (
            {**entry, "score": round(cos(q_vec, v), 4)}
            for entry, v in zip(FORMULA_LIBRARY, doc_vecs, strict=True)
        ),
        key=lambda r: r["score"],
        reverse=True,
    )
    return ranked[:top_k]
