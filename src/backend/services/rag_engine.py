import json
import logging
import os
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import Settings
from ..llm import LLMClient, THINKING_CONFIG
from ..models import Chunk, Citation, IndexStatus, ParsedTextbook, QueryResponse
from ..prompts.rag_qa import RAG_SYSTEM_PROMPT, build_rag_prompt

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, settings: Settings, llm: LLMClient):
        self.settings = settings
        self.llm = llm
        self.embeddings_np: np.ndarray | None = None
        self.chunks: list[Chunk] = []
        self.indexed_textbooks: list[str] = []
        self.indexed_book_ids: list[str] = []
        self.per_book_chapter_ids: dict[str, list[str]] = {}
        self.max_chapters: int = 0
        self.usable_only: bool = True
        self.built_at: str | None = None
        self.embeddings_path = self.settings.index_dir / "embeddings.npy"
        self.chunks_path = self.settings.index_dir / "chunks.json"
        self.meta_path = self.settings.index_dir / "meta.json"

    def _chunk_textbook(self, textbook: ParsedTextbook) -> list[Chunk]:
        chunks = []
        chunk_size, overlap = self.settings.chunk_size, self.settings.chunk_overlap
        for chapter in textbook.chapters:
            content = chapter.content
            start, idx = 0, 0
            while start < len(content):
                piece = content[start:start + chunk_size]
                est_page = chapter.page_start + int(
                    (start / max(len(content), 1)) * max(chapter.page_end - chapter.page_start, 1)
                )
                chunks.append(Chunk(
                    chunk_id=f"{textbook.textbook_id}_{chapter.chapter_id}_p{idx}",
                    textbook_id=textbook.textbook_id,
                    textbook_name=textbook.title,
                    chapter=chapter.title,
                    page=est_page,
                    content=piece,
                ))
                start += chunk_size - overlap
                idx += 1
        return chunks

    def _persist_index(self) -> None:
        if self.embeddings_np is None or not self.chunks:
            return

        np.save(self.embeddings_path, self.embeddings_np)
        self.chunks_path.write_text(
            json.dumps([chunk.model_dump() for chunk in self.chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.meta_path.write_text(
            json.dumps(
                {
                    "indexed_textbooks": self.indexed_textbooks,
                    "indexed_book_ids": self.indexed_book_ids,
                    "per_book_chapter_ids": self.per_book_chapter_ids,
                    "max_chapters": self.max_chapters,
                    "usable_only": self.usable_only,
                    "built_at": self.built_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_from_disk(self) -> IndexStatus:
        if not self.embeddings_path.exists() or not self.chunks_path.exists():
            logger.info("No persisted RAG index found on disk")
            return self._status()

        self.embeddings_np = np.load(self.embeddings_path).astype(np.float32)
        raw_chunks = json.loads(self.chunks_path.read_text(encoding="utf-8"))
        self.chunks = [Chunk.model_validate(item) for item in raw_chunks]

        if self.meta_path.exists():
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            self.indexed_textbooks = meta.get("indexed_textbooks", [])
            self.indexed_book_ids = meta.get("indexed_book_ids", [])
            self.per_book_chapter_ids = meta.get("per_book_chapter_ids", {})
            self.max_chapters = meta.get("max_chapters", 0)
            self.usable_only = meta.get("usable_only", True)
            self.built_at = meta.get("built_at")
        else:
            self.indexed_textbooks = sorted({chunk.textbook_name for chunk in self.chunks})
            self.built_at = None

        if not self.indexed_textbooks:
            self.indexed_textbooks = sorted({chunk.textbook_name for chunk in self.chunks})
        if not self.indexed_book_ids:
            self.indexed_book_ids = sorted({chunk.textbook_id for chunk in self.chunks})
        if not self.built_at and self.embeddings_path.exists():
            self.built_at = datetime.fromtimestamp(
                self.embeddings_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(timespec="seconds").replace("+00:00", "Z")

        if self.embeddings_np.shape[0] != len(self.chunks):
            logger.warning(
                "Persisted RAG index mismatch: embeddings=%d, chunks=%d",
                self.embeddings_np.shape[0],
                len(self.chunks),
            )
            self.embeddings_np = None
            self.chunks = []
            self.indexed_textbooks = []
            self.indexed_book_ids = []
            self.built_at = None
            return self._status()

        logger.info(
            "Restored RAG index: textbooks=%d, chunks=%d",
            len(self.indexed_textbooks),
            len(self.chunks),
        )
        return self._status()

    async def build_index(self, textbooks: list[ParsedTextbook]) -> IndexStatus:
        """将多本教材分块并生成向量嵌入，构建用于语义检索的RAG索引，同时持久化到磁盘。"""
        self.chunks = []
        self.indexed_textbooks = []
        self.indexed_book_ids = []
        self.per_book_chapter_ids = {}
        for textbook in textbooks:
            self.chunks.extend(self._chunk_textbook(textbook))
            self.indexed_textbooks.append(textbook.title)
            self.indexed_book_ids.append(textbook.textbook_id)
            self.per_book_chapter_ids[textbook.textbook_id] = [chapter.chapter_id for chapter in textbook.chapters]

        if not self.chunks:
            self.embeddings_np = None
            self.built_at = None
            return IndexStatus(total_textbooks=0, total_chunks=0, indexed_textbooks=[], indexed_book_ids=[])

        logger.info("Embedding %d chunks...", len(self.chunks))
        texts = [chunk.content for chunk in self.chunks]
        all_embeddings = []
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await self.llm.embed(batch)
            all_embeddings.extend(embeddings)

        self.embeddings_np = np.array(all_embeddings, dtype=np.float32)
        norms = np.linalg.norm(self.embeddings_np, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.embeddings_np = self.embeddings_np / norms
        self.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        logger.info("Index built: %d chunks, dim=%d", len(self.chunks), self.embeddings_np.shape[1])
        self._persist_index()
        return self._status()

    def _search(self, query_vec: np.ndarray, top_k: int):
        query_vec = query_vec / max(np.linalg.norm(query_vec), 1e-10)
        similarities = cosine_similarity(query_vec, self.embeddings_np)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return similarities[top_indices], top_indices

    def _search_hybrid(self, query_vec: np.ndarray, query_text: str, top_k: int):
        """混合检索：结合向量相似度（0.7权重）与TF-IDF余弦相似度（0.3权重）。"""
        # 向量检索部分
        query_vec = query_vec / max(np.linalg.norm(query_vec), 1e-10)
        vec_scores = cosine_similarity(query_vec, self.embeddings_np)[0]

        # TF-IDF检索部分
        corpus = [chunk.content for chunk in self.chunks]
        try:
            tfidf = TfidfVectorizer()
            tfidf_matrix = tfidf.fit_transform(corpus)
            query_tfidf = tfidf.transform([query_text])
            tfidf_scores = cosine_similarity(query_tfidf, tfidf_matrix).toarray()[0]
        except Exception:
            tfidf_scores = np.zeros(len(self.chunks))

        # 加权融合
        combined_scores = 0.7 * vec_scores + 0.3 * tfidf_scores
        top_indices = np.argsort(combined_scores)[::-1][:top_k]
        return combined_scores[top_indices], top_indices

    async def query(self, question: str) -> QueryResponse:
        """根据用户问题在已构建的向量索引中检索相关文本块，调用LLM生成回答并返回引用来源。"""
        if self.embeddings_np is None and self.chunks_path.exists():
            self.load_from_disk()

        if self.embeddings_np is None:
            return QueryResponse(answer="索引尚未构建，请先建立索引。", citations=[], source_chunks=[])

        query_embedding = await self.llm.embed([question])
        query_vector = np.array(query_embedding, dtype=np.float32)
        top_k = min(self.settings.rag_top_k, len(self.chunks))

        use_hybrid = os.environ.get("RAG_HYBRID", "0").strip() in ("1", "true", "True")
        if use_hybrid:
            scores, indices = self._search_hybrid(query_vector, question, top_k)
        else:
            scores, indices = self._search(query_vector, top_k)

        retrieved = []
        for score, idx in zip(scores, indices):
            if 0 <= idx < len(self.chunks):
                chunk = self.chunks[idx]
                retrieved.append({
                    "textbook_name": chunk.textbook_name,
                    "chapter": chunk.chapter,
                    "page": chunk.page,
                    "content": chunk.content,
                    "score": float(score),
                })

        if not retrieved:
            return QueryResponse(answer="当前知识库中未找到相关信息。", citations=[], source_chunks=[])

        answer_text = await self.llm.chat(
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": build_rag_prompt(question, retrieved)},
            ],
            thinking=THINKING_CONFIG["rag_qa"],
            max_tokens=2000,
        )

        citations = [
            Citation(
                textbook=item["textbook_name"],
                chapter=item["chapter"],
                page=item["page"],
                relevance_score=item["score"],
                chunk_preview=item["content"][:100],
            )
            for item in retrieved
        ]

        return QueryResponse(
            answer=answer_text,
            citations=citations,
            source_chunks=[item["content"] for item in retrieved],
        )

    def _status(self) -> IndexStatus:
        return IndexStatus(
            total_textbooks=len(self.indexed_textbooks),
            total_chunks=len(self.chunks),
            indexed_textbooks=self.indexed_textbooks,
            indexed_book_ids=self.indexed_book_ids,
            per_book_chapter_ids=self.per_book_chapter_ids,
            max_chapters=self.max_chapters,
            usable_only=self.usable_only,
            built_at=self.built_at,
            persisted=self.embeddings_path.exists() and self.chunks_path.exists(),
        )

    def get_status(self) -> IndexStatus:
        if self.embeddings_np is None and self.chunks_path.exists():
            self.load_from_disk()
        return self._status()
