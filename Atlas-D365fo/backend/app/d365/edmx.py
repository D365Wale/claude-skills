"""EDMX ($metadata) parser: OData v4 XML -> searchable entity documents.

Stdlib ElementTree only. Handles the three metadata shapes that matter for
integration work: EntityType (fields + keys), EnumType (member decoding —
the "SalesOrderStatus: 1=Backorder" problem), and Action/Function imports.
"""
from dataclasses import dataclass, field
from xml.etree import ElementTree

EDM_NS = "{http://docs.oasis-open.org/odata/ns/edm}"


@dataclass
class EntityDoc:
    """One searchable unit: an entity, enum, or service action."""

    name: str
    kind: str  # "entity" | "enum" | "action"
    fields: list[dict] = field(default_factory=list)  # {name, type, nullable}
    keys: list[str] = field(default_factory=list)
    members: dict[str, int] = field(default_factory=dict)  # enum name -> value
    entity_set: str = ""  # OData collection name, e.g. CustomersV3

    def to_text(self) -> str:
        """Flatten to text for embedding."""
        parts = [f"{self.kind} {self.name}"]
        if self.entity_set:
            parts.append(f"entity set {self.entity_set}")
        if self.keys:
            parts.append("keys: " + ", ".join(self.keys))
        if self.fields:
            parts.append("fields: " + ", ".join(f["name"] for f in self.fields))
        if self.members:
            parts.append("values: " + ", ".join(self.members))
        return ". ".join(parts)


def parse_edmx(xml_text: str) -> list[EntityDoc]:
    root = ElementTree.fromstring(xml_text)
    docs: list[EntityDoc] = []
    entity_sets: dict[str, str] = {}  # EntityType name -> EntitySet name

    for es in root.iter(f"{EDM_NS}EntitySet"):
        # EntityType attr is namespace-qualified, e.g. Microsoft.Dynamics.DataEntities.Customer
        type_name = es.get("EntityType", "").rsplit(".", 1)[-1]
        entity_sets[type_name] = es.get("Name", "")

    for et in root.iter(f"{EDM_NS}EntityType"):
        name = et.get("Name", "")
        keys = [
            ref.get("Name", "")
            for key_el in et.findall(f"{EDM_NS}Key")
            for ref in key_el.findall(f"{EDM_NS}PropertyRef")
        ]
        fields = [
            {
                "name": p.get("Name", ""),
                "type": p.get("Type", ""),
                "nullable": p.get("Nullable", "true") != "false",
            }
            for p in et.findall(f"{EDM_NS}Property")
        ]
        docs.append(
            EntityDoc(
                name=name,
                kind="entity",
                fields=fields,
                keys=keys,
                entity_set=entity_sets.get(name, ""),
            )
        )

    for en in root.iter(f"{EDM_NS}EnumType"):
        members = {
            m.get("Name", ""): int(m.get("Value", "0"))
            for m in en.findall(f"{EDM_NS}Member")
        }
        docs.append(EntityDoc(name=en.get("Name", ""), kind="enum", members=members))

    for action in root.iter(f"{EDM_NS}Action"):
        params = [
            {"name": p.get("Name", ""), "type": p.get("Type", ""), "nullable": True}
            for p in action.findall(f"{EDM_NS}Parameter")
        ]
        docs.append(EntityDoc(name=action.get("Name", ""), kind="action", fields=params))

    return docs
