from fastapi import APIRouter, HTTPException
import json
from datetime import datetime

from ..state import (
    app_state,
    enrich_knowledge_graph_metadata,
    load_integration_result,
    load_knowledge_graph,
    load_parsed_textbook,
    save_knowledge_graph,
)
from ..config import settings
from ..models import KnowledgeGraph
from ..services.chapter_selection import select_chapters

router = APIRouter()


def _select_target_chapters(parsed, max_chapters: int, usable_only: bool = True):
    return select_chapters(parsed.chapters, max_chapters=max_chapters, usable_only=usable_only)


def _chapter_title_map(chapters):
    return {chapter.chapter_id: chapter.title for chapter in chapters}


async def run_kg_build(book_id: str, max_chapters: int = 0, force: bool = False, usable_only: bool = True):
    from ..services.extractor import extract_knowledge_graph
    from ..llm import llm_client

    parsed = load_parsed_textbook(book_id, settings)
    if not parsed:
        raise HTTPException(404, "Textbook not parsed")

    target_chapters = _select_target_chapters(parsed, max_chapters, usable_only=usable_only)
    target_chapter_ids = [chapter.chapter_id for chapter in target_chapters]
    existing_graph = load_knowledge_graph(book_id, settings)
    if existing_graph:
        enrich_knowledge_graph_metadata(existing_graph, parsed)

    build_status = "built"
    if existing_graph and not force:
        existing_ids = set(existing_graph.chapter_ids)
        missing_ids = [chapter_id for chapter_id in target_chapter_ids if chapter_id not in existing_ids]
        if not missing_ids and existing_graph.nodes:
            save_knowledge_graph(existing_graph, settings)
            return {
                "status": "skipped",
                "book_id": book_id,
                "nodes": len(existing_graph.nodes),
                "edges": len(existing_graph.edges),
                "chapters_processed": existing_graph.chapters_processed,
                "chapters_total": len(parsed.chapters),
            }
        if missing_ids:
            remaining_chapters = [chapter for chapter in target_chapters if chapter.chapter_id in missing_ids]
            incremental_graph = await extract_knowledge_graph(
                llm_client,
                book_id,
                parsed.title,
                remaining_chapters,
                node_counter_start=len(existing_graph.nodes),
            )
            kg = KnowledgeGraph(
                textbook_id=book_id,
                nodes=existing_graph.nodes + incremental_graph.nodes,
                edges=existing_graph.edges + incremental_graph.edges,
                chapters_processed=len(target_chapter_ids),
                chapters_total=len(parsed.chapters),
                chapter_ids=target_chapter_ids,
                chapter_titles=_chapter_title_map(target_chapters),
                max_chapters=max_chapters,
                usable_only=usable_only,
                built_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            )
            build_status = "resumed"
        else:
            kg = await extract_knowledge_graph(llm_client, book_id, parsed.title, target_chapters)
            kg.chapters_total = len(parsed.chapters)
            kg.chapter_ids = target_chapter_ids
            kg.chapter_titles = _chapter_title_map(target_chapters)
            kg.max_chapters = max_chapters
            kg.usable_only = usable_only
            kg.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    else:
        kg = await extract_knowledge_graph(llm_client, book_id, parsed.title, target_chapters)
        kg.chapters_total = len(parsed.chapters)
        kg.chapter_ids = target_chapter_ids
        kg.chapter_titles = _chapter_title_map(target_chapters)
        kg.max_chapters = max_chapters
        kg.usable_only = usable_only
        kg.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    save_knowledge_graph(kg, settings)

    return {
        "status": build_status,
        "book_id": book_id,
        "nodes": len(kg.nodes),
        "edges": len(kg.edges),
        "chapters_processed": kg.chapters_processed,
        "chapters_total": len(parsed.chapters),
    }


@router.post("/build/{book_id}")
async def build_kg(book_id: str, max_chapters: int = 0, force: bool = False, usable_only: bool = True):
    return await run_kg_build(book_id, max_chapters=max_chapters, force=force, usable_only=usable_only)


@router.get("/merged")
async def get_merged_kg():
    result = load_integration_result(settings)
    if not result:
        raise HTTPException(404, "Integration not run yet")
    return json.loads(result.integrated_graph.model_dump_json(ensure_ascii=False))


@router.get("/visualization")
async def get_visualization():
    result = load_integration_result(settings)
    if result:
        graph = result.integrated_graph
    else:
        all_nodes, all_edges = [], []
        if not app_state["knowledge_graphs"]:
            for graph_path in sorted(settings.graph_dir.glob("*.json")):
                load_knowledge_graph(graph_path.stem, settings)
        for book_id, kg in app_state["knowledge_graphs"].items():
            all_nodes.extend([n.model_dump() for n in kg.nodes])
            all_edges.extend([e.model_dump() for e in kg.edges])
        if not all_nodes:
            raise HTTPException(404, "No knowledge graphs built")
        graph_data = {"nodes": all_nodes, "edges": all_edges}
        return graph_data

    return json.loads(graph.model_dump_json(ensure_ascii=False))


@router.get("/{book_id}")
async def get_kg(book_id: str):
    kg = load_knowledge_graph(book_id, settings)
    if not kg:
        raise HTTPException(404, "Knowledge graph not built")
    return json.loads(kg.model_dump_json(ensure_ascii=False))


@router.get("/{book_id}/chapters")
async def get_kg_chapters(book_id: str):
    parsed = load_parsed_textbook(book_id, settings)
    if not parsed:
        raise HTTPException(404, "Textbook not parsed")

    kg = load_knowledge_graph(book_id, settings)
    selected_ids = set(kg.chapter_ids if kg else [])

    chapters = []
    for index, chapter in enumerate(parsed.chapters, start=1):
        chapters.append({
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "page_start": chapter.page_start,
            "page_end": chapter.page_end,
            "char_count": chapter.char_count,
            "sequence": index,
            "in_knowledge_graph": chapter.chapter_id in selected_ids,
            "is_processed": bool(kg and chapter.chapter_id in selected_ids),
        })

    return {
        "book_id": book_id,
        "total_chapters": len(parsed.chapters),
        "processed_chapters": len(selected_ids),
        "chapters": chapters,
    }
