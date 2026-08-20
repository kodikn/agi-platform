from __future__ import annotations

from dataclasses import dataclass, field

from agi_platform.security import TenantContext


@dataclass
class KnowledgeGraph:
    nodes: dict[tuple[str, str], dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    def upsert_entity(self, entity_id: str, labels: list[str], properties: dict | None = None, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        node = {"id": entity_id, "tenant_id": context.tenant_id, "labels": labels, "properties": properties or {}}
        self.nodes[(context.tenant_id, entity_id)] = node
        return node

    def relate(self, source: str, target: str, relationship: str, properties: dict | None = None, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        if (context.tenant_id, source) not in self.nodes or (context.tenant_id, target) not in self.nodes:
            raise KeyError("both source and target nodes must exist for tenant")
        edge = {"tenant_id": context.tenant_id, "source": source, "target": target, "relationship": relationship, "properties": properties or {}}
        self.edges.append(edge)
        return edge

    def search(self, query: str, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        lowered = query.lower()
        nodes = [node for (tenant_id, _), node in self.nodes.items() if tenant_id == context.tenant_id and (lowered in node["id"].lower() or any(lowered in label.lower() for label in node["labels"]))]
        node_ids = {node["id"] for node in nodes}
        return {"query": query, "tenant_id": context.tenant_id, "nodes": nodes, "relationships": [edge for edge in self.edges if edge.get("tenant_id") == context.tenant_id and (edge["source"] in node_ids or edge["target"] in node_ids)]}
