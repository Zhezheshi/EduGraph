from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import SessionLocal, TextbookDB
from ..state import load_integration_result, load_knowledge_graph, load_parsed_textbook
from ..services.chapter_selection import select_chapters
from .knowledge_graph import run_kg_build
from .rag import get_rag_engine

router = APIRouter()


def _parse_book_scope(books: str) -> list[str]:
    if not books:
        return []
    return [book_id.strip() for book_id in books.split(",") if book_id.strip()]


def _list_registered_books():
    db = SessionLocal()
    try:
        return db.query(TextbookDB).order_by(TextbookDB.id).all()
    finally:
        db.close()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None


def _chapter_scope_matches(known: dict[str, list[str]] | None, current: dict[str, list[str]]) -> bool:
    if not known:
        return False
    normalized_known = {book_id: list(chapter_ids) for book_id, chapter_ids in known.items()}
    return normalized_known == current
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


@router.get("/status")
async def get_pipeline_status():
    books = _list_registered_books()
    integration = load_integration_result(settings)
    rag_status = get_rag_engine().get_status()

    integration_books = set(integration.book_ids if integration else [])
    rag_books = set(rag_status.indexed_book_ids)
    integration_time = _parse_timestamp(integration.built_at) if integration else None
    rag_time = _parse_timestamp(rag_status.built_at)
    textbook_statuses = []
    current_graph_scope = {}

    for book in books:
        parsed = load_parsed_textbook(book.id, settings)
        kg = load_knowledge_graph(book.id, settings)
        if kg:
            current_graph_scope[book.id] = list(kg.chapter_ids)

        textbook_statuses.append({
            "book_id": book.id,
            "title": book.title,
            "filename": book.filename,
            "db_status": book.status,
            "parsed": {
                "exists": parsed is not None,
                "chapters": len(parsed.chapters) if parsed else 0,
                "total_pages": parsed.total_pages if parsed else book.total_pages,
                "total_chars": parsed.total_chars if parsed else book.total_chars,
            },
            "knowledge_graph": {
                "exists": kg is not None,
                "nodes": len(kg.nodes) if kg else 0,
                "edges": len(kg.edges) if kg else 0,
                "chapters_processed": kg.chapters_processed if kg else 0,
                "chapters_total": kg.chapters_total if kg else (len(parsed.chapters) if parsed else 0),
                "chapter_ids": kg.chapter_ids if kg else [],
                "built_at": kg.built_at if kg else None,
                "is_complete": bool(kg and kg.chapters_total and kg.chapters_processed >= kg.chapters_total),
            },
            "included_in_latest_integration": book.id in integration_books,
            "included_in_latest_rag_index": book.id in rag_books,
        })

    integration_stale = False
    if integration:
        expected_scope = {book_id: current_graph_scope.get(book_id, []) for book_id in integration.book_ids}
        if not _chapter_scope_matches(integration.per_book_chapter_ids, expected_scope):
            integration_stale = True
        elif integration_time:
            for item in textbook_statuses:
                if item["book_id"] not in integration_books:
                    continue
                graph_time = _parse_timestamp(item["knowledge_graph"]["built_at"])
                if graph_time and graph_time > integration_time:
                    integration_stale = True
                    break

    rag_stale = False
    current_rag_scope = {}
    for book in books:
        parsed = load_parsed_textbook(book.id, settings)
        if not parsed or book.id not in rag_books:
            continue
        selected = select_chapters(
            parsed.chapters,
            max_chapters=rag_status.max_chapters,
            usable_only=rag_status.usable_only,
        )
        current_rag_scope[book.id] = [chapter.chapter_id for chapter in selected]

    if rag_books:
        if not _chapter_scope_matches(rag_status.per_book_chapter_ids, current_rag_scope):
            rag_stale = True
        elif rag_time:
            for item in textbook_statuses:
                if item["book_id"] not in rag_books:
                    continue
                parsed_path = settings.parsed_dir / f"{item['book_id']}.json"
                if parsed_path.exists():
                    parsed_time = datetime.fromtimestamp(parsed_path.stat().st_mtime, tz=timezone.utc)
                    if parsed_time > rag_time:
                        rag_stale = True
                        break

    return {
        "summary": {
            "registered_books": len(books),
            "parsed_books": sum(1 for item in textbook_statuses if item["parsed"]["exists"]),
            "graph_books": sum(1 for item in textbook_statuses if item["knowledge_graph"]["exists"]),
            "complete_graph_books": sum(1 for item in textbook_statuses if item["knowledge_graph"]["is_complete"]),
            "partial_graph_books": sum(
                1
                for item in textbook_statuses
                if item["knowledge_graph"]["exists"] and not item["knowledge_graph"]["is_complete"]
            ),
            "integration_books": len(integration_books),
            "rag_books": len(rag_books),
        },
        "integration": (
            {
                "exists": True,
                "book_ids": integration.book_ids,
                "original_node_count": integration.original_node_count,
                "integrated_node_count": integration.integrated_node_count,
                "compression_ratio": integration.compression_ratio,
                "decisions": len(integration.decisions),
                "alignment_group_count": integration.alignment_group_count,
                "built_at": integration.built_at,
                "stale": integration_stale,
            }
            if integration
            else {"exists": False}
        ),
        "rag": {**rag_status.model_dump(), "stale": rag_stale},
        "textbooks": textbook_statuses,
    }


@router.post("/kg/build-all")
async def build_all_knowledge_graphs(
    books: str = "",
    max_chapters: int = 0,
    force: bool = False,
    usable_only: bool = True,
):
    registered_books = _list_registered_books()
    selected_ids = _parse_book_scope(books) or [book.id for book in registered_books]

    results = []
    for book_id in selected_ids:
        parsed = load_parsed_textbook(book_id, settings)
        if not parsed:
            results.append({"status": "missing_parsed", "book_id": book_id})
            continue

        try:
            result = await run_kg_build(
                book_id,
                max_chapters=max_chapters,
                force=force,
                usable_only=usable_only,
            )
            results.append(result)
        except HTTPException as exc:
            results.append({"status": "failed", "book_id": book_id, "error": exc.detail})
        except Exception as exc:
            results.append({"status": "failed", "book_id": book_id, "error": str(exc)})

    return {
        "status": "completed",
        "requested_books": selected_ids,
        "max_chapters": max_chapters,
        "force": force,
        "usable_only": usable_only,
        "built": sum(1 for item in results if item["status"] == "built"),
        "resumed": sum(1 for item in results if item["status"] == "resumed"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "failed": sum(1 for item in results if item["status"] not in {"built", "resumed", "skipped"}),
        "results": results,
    }
