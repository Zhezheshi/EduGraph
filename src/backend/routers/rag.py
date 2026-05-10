from fastapi import APIRouter, HTTPException
import json

from ..state import app_state
from ..llm import llm_client
from ..config import settings
from ..models import QueryRequest, QueryResponse
from ..services.chapter_selection import select_chapters

router = APIRouter()
rag_engine = None


def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        from ..services.rag_engine import RAGEngine
        rag_engine = RAGEngine(settings, llm_client)
    return rag_engine


@router.post("/index")
async def build_index(max_chapters: int = 0, books: str = "", usable_only: bool = True):
    engine = get_rag_engine()
    textbooks = []
    engine.max_chapters = max_chapters
    engine.usable_only = usable_only
    # Determine which books to index
    target_ids = books.split(",") if books else []
    for p in sorted(settings.parsed_dir.glob("*.json")):
        from ..models import ParsedTextbook
        tb = ParsedTextbook.model_validate_json(p.read_text(encoding="utf-8"))
        if target_ids and p.stem not in target_ids:
            continue
        tb.chapters = select_chapters(tb.chapters, max_chapters=max_chapters, usable_only=usable_only)
        textbooks.append(tb)
    if not textbooks:
        raise HTTPException(400, "No parsed textbooks found")
    status = await engine.build_index(textbooks)
    return status.model_dump()


@router.post("/query")
async def query_rag(req: QueryRequest):
    engine = get_rag_engine()
    resp = await engine.query(req.question)
    return json.loads(resp.model_dump_json(ensure_ascii=False))


@router.get("/status")
async def rag_status():
    engine = get_rag_engine()
    return engine.get_status().model_dump()
