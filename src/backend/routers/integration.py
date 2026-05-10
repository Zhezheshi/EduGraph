from fastapi import APIRouter, HTTPException
import json
from datetime import datetime

from ..state import app_state, load_integration_result, load_knowledge_graph, save_integration_result
from ..llm import llm_client
from ..config import settings

router = APIRouter()


def _get_result_or_404():
    result = load_integration_result(settings)
    if not result:
        raise HTTPException(404, "Integration not run yet")
    return result


def _find_decision_or_404(result, decision_id: str):
    for decision in result.decisions:
        if decision.decision_id == decision_id:
            return decision
    raise HTTPException(404, f"Decision not found: {decision_id}")


def _serialize_decision(result, decision):
    payload = decision.model_dump()
    source_textbooks = set()
    for node_id in decision.affected_nodes:
        if "_node_" in node_id:
            source_textbooks.add(node_id.split("_node_", 1)[0])

    if decision.result_node_id and decision.result_node_id in result.integrated_graph.source_mapping:
        for node_id in result.integrated_graph.source_mapping[decision.result_node_id]:
            if "_node_" in node_id:
                source_textbooks.add(node_id.split("_node_", 1)[0])

    payload["source_textbooks"] = sorted(source_textbooks)
    return payload


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


def _selected_chapter_map(scoped_graphs):
    return {book_id: list(kg.chapter_ids) for book_id, kg in scoped_graphs.items()}


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
    result.per_book_chapter_ids = _selected_chapter_map(scoped_graphs)
    result.max_chapters = max((kg.max_chapters for kg in scoped_graphs.values()), default=0)
    result.usable_only = all(kg.usable_only for kg in scoped_graphs.values()) if scoped_graphs else True
    result.alignment_group_count = len(groups)
    result.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_integration_result(result, settings)

    return {
        "status": "integrated",
        "books": result.book_ids,
        "per_book_chapter_ids": result.per_book_chapter_ids,
        "original_nodes": result.original_node_count,
        "integrated_nodes": result.integrated_node_count,
        "compression_ratio": f"{result.compression_ratio:.1%}",
        "decisions": len(result.decisions),
    }


@router.get("/decisions")
async def get_decisions():
    result = _get_result_or_404()
    return [_serialize_decision(result, decision) for decision in result.decisions]


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str):
    result = _get_result_or_404()
    decision = _find_decision_or_404(result, decision_id)
    return _serialize_decision(result, decision)


def _update_decision_status(decision_id: str, status: str):
    result = _get_result_or_404()
    decision = _find_decision_or_404(result, decision_id)
    decision.status = status
    result.built_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_integration_result(result, settings)
    return {
        "status": "updated",
        "decision": _serialize_decision(result, decision),
    }


@router.post("/decisions/{decision_id}/accept")
async def accept_decision(decision_id: str):
    return _update_decision_status(decision_id, "accepted")


@router.post("/decisions/{decision_id}/reject")
async def reject_decision(decision_id: str):
    return _update_decision_status(decision_id, "rejected")


@router.get("/stats")
async def get_stats():
    result = _get_result_or_404()
    return {
        "book_ids": result.book_ids,
        "per_book_chapter_ids": result.per_book_chapter_ids,
        "max_chapters": result.max_chapters,
        "usable_only": result.usable_only,
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
