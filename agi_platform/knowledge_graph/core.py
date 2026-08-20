from __future__ import annotations

from dataclasses import dataclass, field

from agi_platform.security import TenantContext


@dataclass
class KnowledgeGraph:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    def upsert_entity(
        self,
        context: TenantContext | None,
        entity_id: str,
        labels: list[str],
        properties: dict | None = None,
    ) -> dict:
        if context is None:
            raise PermissionError("tenant context required")
        node = {
            "id": entity_id,
            "tenant_id": context.tenant_id,
            "labels": labels,
            "properties": properties or {},
        }
        self.nodes[f"{context.tenant_id}:{entity_id}"] = node
        return node

    def relate(
        self,
        context: TenantContext | None,
        source: str,
        target: str,
        relationship: str,
        properties: dict | None = None,
    ) -> dict:
        if context is None:
            raise PermissionError("tenant context required")
        skey = f"{context.tenant_id}:{source}"
        tkey = f"{context.tenant_id}:{target}"
        if skey not in self.nodes or tkey not in self.nodes:
            raise KeyError("both source and target nodes must exist in tenant")
        edge = {
            "tenant_id": context.tenant_id,
            "source": source,
            "target": target,
            "relationship": relationship,
            "properties": properties or {},
        }
        self.edges.append(edge)
        return edge

    def search(self, context: TenantContext | None, query: str) -> dict:
        if context is None:
            raise PermissionError("tenant context required")
        lowered = query.lower()
        nodes = [
            node
            for node in self.nodes.values()
            if node.get("tenant_id") == context.tenant_id
            and (
                lowered in node["id"].lower()
                or any(lowered in label.lower() for label in node["labels"])
            )
        ]
        node_ids = {node["id"] for node in nodes}
        return {
            "query": query,
            "nodes": nodes,
            "relationships": [
                edge
                for edge in self.edges
                if edge.get("tenant_id") == context.tenant_id
                and (edge["source"] in node_ids or edge["target"] in node_ids)
            ],
        }
