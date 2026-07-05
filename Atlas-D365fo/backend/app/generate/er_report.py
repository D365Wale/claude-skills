"""ER configuration validators: catch at design time what D365 only
surfaces at runtime.

1. Binding check — every format Binding path (and every model path referenced
   inside a Formula) must resolve against the config's data model tree.
2. Expression lint — paren/quote balance + unknown-function detection against
   the documented GER function set.
"""
import re
from dataclasses import dataclass

from app.d365.er import ERConfig

# Documented GER expression functions (subset that covers the common surface).
KNOWN_ER_FUNCTIONS = {
    "FILTER", "WHERE", "FIRST", "FIRSTORNULL", "ALLITEMS", "ALLITEMSQUERY",
    "CONCATENATE", "DATEFORMAT", "DATETIMEFORMAT", "NUMBERFORMAT", "FORMAT",
    "SUM", "COUNT", "AVERAGE", "MIN", "MAX", "ROUND", "ROUNDDOWN", "ROUNDUP",
    "IF", "CASE", "AND", "OR", "NOT", "CONTAINS", "REPLACE", "TRANSLATE",
    "LEFT", "RIGHT", "MID", "TRIM", "LEN", "UPPER", "LOWER", "TEXT", "VALUE",
    "PADLEFT", "SPLIT", "INDEX", "ISEMPTY", "NULLDATE", "NULLDATETIME",
    "SESSIONNOW", "SESSIONTODAY", "GETENUMVALUEBYNAME", "LISTJOIN",
}

_FUNC_RE = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\s*\(")
_MODEL_PATH_RE = re.compile(r"\bmodel(?:\.\w+)+")


@dataclass
class Finding:
    severity: str  # error | warning
    kind: str  # broken-binding | expression
    location: str  # format element name
    detail: str


def validate_er_config(config: ERConfig) -> list[Finding]:
    findings: list[Finding] = []
    model_paths = {n.path for n in config.model_nodes}

    def check_path(path: str, element: str, source: str) -> None:
        if path not in model_paths:
            findings.append(
                Finding(
                    severity="error",
                    kind="broken-binding",
                    location=element,
                    detail=f"{source} references '{path}' — not in data model "
                    f"({len(model_paths)} known paths)",
                )
            )

    for fmt in config.format_elements:
        for path in fmt.bindings:
            check_path(path, fmt.name, "Binding")

        for formula in fmt.formulas:
            for path in _MODEL_PATH_RE.findall(formula):
                check_path(path, fmt.name, "Formula")

            if formula.count("(") != formula.count(")"):
                findings.append(
                    Finding(
                        severity="error",
                        kind="expression",
                        location=fmt.name,
                        detail=f"Unbalanced parentheses in: {formula[:80]}",
                    )
                )
            if formula.count('"') % 2 != 0:
                findings.append(
                    Finding(
                        severity="error",
                        kind="expression",
                        location=fmt.name,
                        detail=f"Unbalanced quotes in: {formula[:80]}",
                    )
                )
            for func in _FUNC_RE.findall(formula):
                if func not in KNOWN_ER_FUNCTIONS:
                    findings.append(
                        Finding(
                            severity="warning",
                            kind="expression",
                            location=fmt.name,
                            detail=f"Unknown ER function '{func}' in: {formula[:80]}",
                        )
                    )

    return findings
