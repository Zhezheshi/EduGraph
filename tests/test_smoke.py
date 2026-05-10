import sys
import os
import unittest

# Ensure src is on the path so models can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

from models import (
    KnowledgeNode,
    KnowledgeEdge,
    KnowledgeGraph,
    Chunk,
    ParsedTextbook,
    Chapter,
)


class TestPydanticSerialization(unittest.TestCase):
    """Test that Pydantic models can be serialized and deserialized."""

    def test_knowledge_node_roundtrip(self):
        node = KnowledgeNode(
            id="n1",
            name="炎症",
            definition="机体对损伤因子的防御性反应",
            category="核心概念",
            textbook_id="book_01",
            chapter="第四章",
            page=78,
        )
        data = node.model_dump()
        restored = KnowledgeNode.model_validate(data)
        self.assertEqual(restored.id, "n1")
        self.assertEqual(restored.name, "炎症")
        self.assertEqual(restored.importance, 0.8)  # default value preserved

    def test_knowledge_graph_roundtrip(self):
        graph = KnowledgeGraph(
            textbook_id="book_01",
            nodes=[
                KnowledgeNode(
                    id="n1", name="A", definition="d", category="c",
                    textbook_id="book_01", chapter="ch1", page=1,
                )
            ],
            edges=[],
        )
        data = graph.model_dump()
        restored = KnowledgeGraph.model_validate(data)
        self.assertEqual(len(restored.nodes), 1)
        self.assertEqual(restored.nodes[0].name, "A")


class TestKnowledgeEdgeValidation(unittest.TestCase):
    """Test that KnowledgeEdge model validates correctly."""

    def test_valid_edge(self):
        edge = KnowledgeEdge(
            source="炎症",
            target="免疫应答",
            relation_type="applies_to",
            description="炎症过程涉及免疫应答",
        )
        self.assertEqual(edge.source, "炎症")
        self.assertEqual(edge.relation_type, "applies_to")
        self.assertAlmostEqual(edge.strength, 0.8)

    def test_edge_custom_strength(self):
        edge = KnowledgeEdge(
            source="A",
            target="B",
            relation_type="prerequisite",
            description="A 是 B 的前置知识",
            strength=0.95,
        )
        self.assertAlmostEqual(edge.strength, 0.95)

    def test_edge_to_dict(self):
        edge = KnowledgeEdge(
            source="X",
            target="Y",
            relation_type="contains",
            description="X 包含 Y",
        )
        d = edge.model_dump()
        self.assertIn("source", d)
        self.assertIn("target", d)
        self.assertIn("relation_type", d)
        self.assertEqual(d["relation_type"], "contains")


class TestChunkModel(unittest.TestCase):
    """Test that the Chunk model can be created with valid data."""

    def test_create_chunk(self):
        chunk = Chunk(
            chunk_id="c_001",
            textbook_id="book_03",
            textbook_name="病理学",
            chapter="第四章 炎症",
            page=78,
            content="炎症是机体对损伤因子的防御性反应。",
        )
        self.assertEqual(chunk.chunk_id, "c_001")
        self.assertEqual(chunk.textbook_name, "病理学")
        self.assertEqual(chunk.page, 78)

    def test_chunk_serialization(self):
        chunk = Chunk(
            chunk_id="c_002",
            textbook_id="book_05",
            textbook_name="生理学",
            chapter="第一章",
            page=1,
            content="test content",
        )
        data = chunk.model_dump()
        restored = Chunk.model_validate(data)
        self.assertEqual(restored.chunk_id, "c_002")
        self.assertEqual(restored.content, "test content")


if __name__ == "__main__":
    unittest.main()
