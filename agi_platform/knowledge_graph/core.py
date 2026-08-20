from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class KnowledgeGraph:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    @staticmethod
    def _node_key(tenant_id: str, entity_id: str) -> str:
        return f"{tenant_id}:{entity_id}"

    def upsert_entity(self, entity_id: str, labels: list[str], properties: dict | None = None, tenant_id: str = "default") -> dict:
        node = {"id": entity_id, "tenant_id": tenant_id, "labels": labels, "properties": properties or {}, "updated_at": int(time.time())}
        self.nodes[self._node_key(tenant_id, entity_id)] = node
        return node

    def relate(self, source: str, target: str, relationship: str, properties: dict | None = None, tenant_id: str = "default") -> dict:
        if self._node_key(tenant_id, source) not in self.nodes or self._node_key(tenant_id, target) not in self.nodes:
            raise KeyError("both source and target nodes must exist for tenant")
        edge = {"tenant_id": tenant_id, "source": source, "target": target, "relationship": relationship, "properties": properties or {}, "created_at": int(time.time())}
        self.edges.append(edge)
        return edge

    def search(self, query: str, tenant_id: str = "default", max_results: int = 50) -> dict:
        lowered = query.lower()
        nodes = [
            node
            for node in self.nodes.values()
            if node.get("tenant_id") == tenant_id and (lowered in node["id"].lower() or any(lowered in label.lower() for label in node["labels"]))
        ][:max_results]
        node_ids = {node["id"] for node in nodes}
        relationships = [edge for edge in self.edges if edge.get("tenant_id") == tenant_id and (edge["source"] in node_ids or edge["target"] in node_ids)][:max_results]
        return {"query": query, "tenant_id": tenant_id, "nodes": nodes, "relationships": relationships}
