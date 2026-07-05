"""Electronic Reporting (ER) configuration parser.

ER configs are the last unserved D365 F&O surface: no external REST API
(X++ ERObjectsFactory only), proprietary expression language, and binding
errors that surface only at runtime after deployment. This module parses
an exported ER configuration offline so bindings and expressions can be
validated *before* upload.

NOTE: built against the documented GER export structure (data model nodes,
format elements, bindings, formulas). Validate against a real sandbox
export before relying on it for production configs — real exports may
carry additional wrapper elements, which the parser tolerates by scanning
for the semantic elements it knows (`Node`, `Element`, `Binding`,
`Formula`) anywhere in the tree.
"""
from dataclasses import dataclass, field
from xml.etree import ElementTree


@dataclass
class ModelNode:
    """One node in the ER data model tree, e.g. model.Payment.Lines.Amount."""

    path: str
    node_type: str  # record | recordlist | string | real | int | date | enum...


@dataclass
class FormatElement:
    """One output element in the ER format with its model bindings/formulas."""

    name: str
    element_type: str
    bindings: list[str] = field(default_factory=list)  # model paths
    formulas: list[str] = field(default_factory=list)  # ER expressions


@dataclass
class ERConfig:
    name: str
    config_type: str
    model_nodes: list[ModelNode] = field(default_factory=list)
    format_elements: list[FormatElement] = field(default_factory=list)


def _local(tag: str) -> str:
    """Strip XML namespace: {ns}Node -> Node."""
    return tag.rsplit("}", 1)[-1]


def parse_er_config(xml_text: str) -> ERConfig:
    root = ElementTree.fromstring(xml_text)
    config = ERConfig(
        name=root.get("name", root.get("Name", "unnamed")),
        config_type=root.get("type", root.get("Type", "unknown")),
    )

    for el in root.iter():
        tag = _local(el.tag)
        if tag == "Node":
            path = el.get("path", "")
            if path:
                config.model_nodes.append(
                    ModelNode(path=path, node_type=el.get("type", "record"))
                )
        elif tag == "Element":
            fmt = FormatElement(
                name=el.get("name", ""), element_type=el.get("type", "")
            )
            for child in el:
                ctag = _local(child.tag)
                if ctag == "Binding":
                    path = child.get("path", "")
                    if path:
                        fmt.bindings.append(path)
                elif ctag == "Formula" and child.text:
                    fmt.formulas.append(child.text.strip())
            config.format_elements.append(fmt)

    return config
