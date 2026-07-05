"""X++ source parser: extracts the service surface that D365 F&O never
publishes — [DataContractAttribute] classes and [SysEntryPointAttribute]
service operations — so external tooling can see what Visual Studio sees.

Regex + brace-matching over raw X++ source. No AOT or VS dependency.
"""
import re
from dataclasses import dataclass, field

_CLASS_RE = re.compile(
    r"\[\s*DataContractAttribute[^\]]*\]\s*(?:public\s+|final\s+)*class\s+(\w+)",
    re.IGNORECASE,
)
_MEMBER_RE = re.compile(
    r"\[\s*DataMemberAttribute\s*\(\s*'([^']+)'\s*\)\s*\]\s*"
    r"(?:public\s+)?(\w+)\s+parm\w+\s*\(",
    re.IGNORECASE,
)
_SERVICE_CLASS_RE = re.compile(r"(?:public\s+|final\s+)*class\s+(\w+)")
_ENTRYPOINT_RE = re.compile(
    r"\[\s*SysEntryPointAttribute[^\]]*\]\s*"
    r"(?:public\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)",
    re.IGNORECASE,
)

# X++ primitive/EDT base types -> JSON schema types. Unknown types (EDTs,
# contract classes) fall through: contracts become $refs, EDTs become strings.
_XPP_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "int64": "integer",
    "real": "number",
    "boolean": "boolean",
    "date": "string",
    "utcdatetime": "string",
    "guid": "string",
    "anytype": "object",
}


@dataclass
class ContractMember:
    name: str  # serialized name from DataMemberAttribute
    xpp_type: str


@dataclass
class DataContract:
    name: str
    members: list[ContractMember] = field(default_factory=list)


@dataclass
class ServiceOperation:
    name: str
    return_type: str
    parameters: list[ContractMember] = field(default_factory=list)


@dataclass
class ServiceClass:
    name: str
    operations: list[ServiceOperation] = field(default_factory=list)


def _class_body(source: str, class_start: int) -> str:
    """Return the brace-delimited body of the class declared at class_start."""
    open_brace = source.find("{", class_start)
    if open_brace == -1:
        return ""
    depth = 0
    for i in range(open_brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace : i + 1]
    return source[open_brace:]


def parse_xpp(source: str) -> tuple[list[DataContract], list[ServiceClass]]:
    contracts: list[DataContract] = []
    services: list[ServiceClass] = []

    for m in _CLASS_RE.finditer(source):
        body = _class_body(source, m.end())
        members = [
            ContractMember(name=mm.group(1), xpp_type=mm.group(2))
            for mm in _MEMBER_RE.finditer(body)
        ]
        contracts.append(DataContract(name=m.group(1), members=members))

    contract_names = {c.name for c in contracts}
    for m in _SERVICE_CLASS_RE.finditer(source):
        name = m.group(1)
        if name in contract_names:
            continue
        body = _class_body(source, m.end())
        ops = []
        for om in _ENTRYPOINT_RE.finditer(body):
            params = []
            for raw in om.group(3).split(","):
                parts = raw.split()
                if len(parts) >= 2:
                    params.append(
                        ContractMember(name=parts[1].lstrip("_"), xpp_type=parts[0])
                    )
            ops.append(
                ServiceOperation(name=om.group(2), return_type=om.group(1), parameters=params)
            )
        if ops:
            services.append(ServiceClass(name=name, operations=ops))

    return contracts, services


def xpp_type_to_schema(xpp_type: str, contract_names: set[str]) -> dict:
    if xpp_type in contract_names:
        return {"$ref": f"#/components/schemas/{xpp_type}"}
    return {"type": _XPP_TYPE_MAP.get(xpp_type.lower(), "string")}
