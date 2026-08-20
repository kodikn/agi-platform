from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KnowledgeGraph:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    def upsert_entity(self, entity_id: str, labels: list[str], properties: dict | None = None) -> dict:
        node = {"id": entity_id, "labels": labels, "properties": properties or {}}
        self.nodes[entity_id] = node
        return node

    def relate(self, source: str, target: str, relationship: str, properties: dict | None = None) -> dict:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("both source and target nodes must exist")
        edge = {"source": source, "target": target, "relationship": relationship, "properties": properties or {}}
        self.edges.append(edge)
        return edge

    def search(self, query: str) -> dict:
        lowered = query.lower()
        nodes = [node for node in self.nodes.values() if lowered in node["id"].lower() or any(lowered in label.lower() for label in node["labels"])]
        return {"query": query, "nodes": nodes, "relationships": [edge for edge in self.edges if edge["source"] in {node["id"] for node in nodes} or edge["target"] in {node["id"] for node in nodes}]}
