from fastapi import APIRouter, HTTPException
import json
from datetime import datetime

from ..state import app_state, load_integration_result, load_knowledge_graph, save_integration_result
from ..llm import llm_client
from ..config import settings

router = APIRouter()


def _ensure_kgs_loaded():
    """Load KGs from disk if not in memory."""
    if app_state["knowledge_graphs"]:
        return
    for graph_path in sorted(settings.graph_dir.glob("*.json")):
        load_knowledge_graph(graph_path.stem, settings)


def _parse_book_scope(books: str) -> list[str]:
    if not books:
        return []
    return [book_id.strip() for book_id in books.split(",") if book_id.strip()]


def _get_scoped_graphs(book_ids: list[str]):
    _ensure_kgs_loaded()
    if not book_ids:
        return dict(sorted(app_state["knowledge_graphs"].items()))

    scoped = {}
    for book_id in book_ids:
        kg = load_knowledge_graph(book_id, settings)
        if not kg:
            raise HTTPException(404, f"Knowledge graph not built: {book_id}")
        scoped[book_id] = kg
    return scoped


@router.post("/align")
async def run_alignment(books: str = ""):
    from ..services.aligner import align_cross_textbooks

    book_ids = _parse_book_scope(books)
    scoped_graphs = _get_scoped_graphs(book_ids)
    all_nodes = {bid: kg.nodes for bid, kg in scoped_graphs.items()}
    if len(all_nodes) < 2:
        raise HTTPException(400, "Need at least 2 textbooks with knowledge graphs")

    groups = await align_cross_textbooks(all_nodes, llm_client, settings.alignment_threshold)
    app_state["alignment_groups"] = groups
    app_state["alignment_scope"] = sorted(all_nodes.keys())
    return {
        "status": "aligned",
        "books": sorted(all_nodes.keys()),
        "groups": len(groups),
        "total_equivalent_nodes": sum(len(g) for g in groups),
    }


@router.post("/run")
async def run_integration(books: str = ""):
    from ..services.integrator import integrate_aligned_groups
    from ..services.aligner import align_cross_textbooks

    book_ids = _parse_book_scope(books)
    scoped_graphs = _get_scoped_graphs(book_ids)
    all_nodes = {bid: kg.nodes for bid, kg in scoped_graphs.items()}
    all_edges = []
    for kg in scoped_graphs.values():
        all_edges.extend(kg.edges)

    selected_books = sorted(all_nodes.keys())
    if not app_state.get("alignment_groups") or app_state.get("alignment_scope") != selected_books:
        groups = await align_cross_textbooks(all_nodes, llm_client, settings.alignment_threshold)
        app_state["alignment_groups"] = groups
        app_state["alignment_scope"] = selected_books
    else:
        groups = app_state["alignment_groups"]

    result = await integrate_aligned_groups(all_nodes, all_edges, groups, llm_client)
    result.book_ids = selected_books
    result.alignment_group_count = len(groups)
    result.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_integration_result(result, settings)

    return {
        "status": "integrated",
        "books": result.book_ids,
        "original_nodes": result.original_node_count,
        "integrated_nodes": result.integrated_node_count,
        "compression_ratio": f"{result.compression_ratio:.1%}",
        "decisions": len(result.decisions),
    }


@router.get("/decisions")
async def get_decisions():
    result = load_integration_result(settings)
    if not result:
        raise HTTPException(404, "Integration not run yet")
    return [d.model_dump() for d in result.decisions]


@router.get("/stats")
async def get_stats():
    result = load_integration_result(settings)
    if not result:
        raise HTTPException(404, "Integration not run yet")
    return {
        "book_ids": result.book_ids,
        "alignment_group_count": result.alignment_group_count,
        "built_at": result.built_at,
        "original_total_chars": result.original_total_chars,
        "integrated_total_chars": result.integrated_total_chars,
        "compression_ratio": result.compression_ratio,
        "original_node_count": result.original_node_count,
        "integrated_node_count": result.integrated_node_count,
        "merge_count": sum(1 for d in result.decisions if d.action == "merge"),
        "keep_count": sum(1 for d in result.decisions if d.action == "keep"),
        "remove_count": sum(1 for d in result.decisions if d.action == "remove"),
    }
