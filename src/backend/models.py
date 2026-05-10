from pydantic import BaseModel
from typing import Optional


class Chapter(BaseModel):
    chapter_id: str
    title: str
    page_start: int
    page_end: int
    content: str
    char_count: int


class ParsedTextbook(BaseModel):
    textbook_id: str
    filename: str
    title: str
    total_pages: int
    total_chars: int
    chapters: list[Chapter]
    format: str = "pdf"
    status: str = "completed"


class KnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str
    textbook_id: str
    chapter: str
    page: int
    frequency: int = 1
    importance: float = 0.8


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    relation_type: str
    description: str
    strength: float = 0.8


class KnowledgeGraph(BaseModel):
    textbook_id: str
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    chapters_processed: int = 0
    chapters_total: int = 0
    chapter_ids: list[str] = []
    chapter_titles: dict[str, str] = {}
    max_chapters: int = 0
    usable_only: bool = True
    built_at: Optional[str] = None


class IntegratedGraph(BaseModel):
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    source_mapping: dict[str, list[str]] = {}


class IntegrationDecision(BaseModel):
    decision_id: str
    action: str
    affected_nodes: list[str]
    result_node_id: Optional[str] = None
    reason: str
    confidence: float
    status: str = "pending"


class IntegrationResult(BaseModel):
    decisions: list[IntegrationDecision]
    integrated_graph: IntegratedGraph
    original_total_chars: int
    integrated_total_chars: int
    compression_ratio: float
    original_node_count: int
    integrated_node_count: int
    book_ids: list[str] = []
    per_book_chapter_ids: dict[str, list[str]] = {}
    max_chapters: int = 0
    usable_only: bool = True
    alignment_group_count: int = 0
    built_at: Optional[str] = None


class Chunk(BaseModel):
    chunk_id: str
    textbook_id: str
    textbook_name: str
    chapter: str
    page: int
    content: str


class QueryRequest(BaseModel):
    question: str


class Citation(BaseModel):
    textbook: str
    chapter: str
    page: int
    relevance_score: float
    chunk_preview: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    source_chunks: list[str]


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatMessage(BaseModel):
    role: str
    content: str


class IndexStatus(BaseModel):
    total_textbooks: int
    total_chunks: int
    indexed_textbooks: list[str] = []
    indexed_book_ids: list[str] = []
    per_book_chapter_ids: dict[str, list[str]] = {}
    max_chapters: int = 0
    usable_only: bool = True
    built_at: Optional[str] = None
    persisted: bool = False


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    actions_taken: list[str] = []
