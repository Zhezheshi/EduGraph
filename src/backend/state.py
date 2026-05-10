import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .config import Settings
from .models import IntegrationResult, KnowledgeGraph, ParsedTextbook

logger = logging.getLogger(__name__)

app_state = {
    "parsed_textbooks": {},
    "knowledge_graphs": {},
    "integration_result": None,
    "alignment_groups": [],
    "alignment_scope": [],
}

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_model(path: Path, model_cls: type[ModelT]) -> ModelT | None:
    if not path.exists():
        return None
    try:
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load %s", path)
        return None


def load_parsed_textbook(book_id: str, settings: Settings) -> ParsedTextbook | None:
    cached = app_state["parsed_textbooks"].get(book_id)
    if cached:
        return cached

    parsed = _load_model(settings.parsed_dir / f"{book_id}.json", ParsedTextbook)
    if parsed:
        app_state["parsed_textbooks"][book_id] = parsed
    return parsed


def save_parsed_textbook(parsed: ParsedTextbook, settings: Settings) -> None:
    path = settings.parsed_dir / f"{parsed.textbook_id}.json"
    path.write_text(parsed.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    app_state["parsed_textbooks"][parsed.textbook_id] = parsed


def load_knowledge_graph(book_id: str, settings: Settings) -> KnowledgeGraph | None:
    cached = app_state["knowledge_graphs"].get(book_id)
    if cached:
        return cached

    graph_path = settings.graph_dir / f"{book_id}.json"
    graph = _load_model(graph_path, KnowledgeGraph)
    if graph:
        parsed = load_parsed_textbook(book_id, settings)
        enrich_knowledge_graph_metadata(graph, parsed)
        if not graph.built_at and graph_path.exists():
            graph.built_at = datetime.fromtimestamp(
                graph_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
        app_state["knowledge_graphs"][book_id] = graph
    return graph


def save_knowledge_graph(graph: KnowledgeGraph, settings: Settings) -> None:
    parsed = load_parsed_textbook(graph.textbook_id, settings)
    enrich_knowledge_graph_metadata(graph, parsed)
    path = settings.graph_dir / f"{graph.textbook_id}.json"
    path.write_text(graph.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    app_state["knowledge_graphs"][graph.textbook_id] = graph


def load_integration_result(settings: Settings) -> IntegrationResult | None:
    cached = app_state.get("integration_result")
    if cached:
        return cached

    result_path = settings.integrated_dir / "result.json"
    result = _load_model(result_path, IntegrationResult)
    if result:
        enrich_integration_result_metadata(result)
        if not result.built_at and result_path.exists():
            result.built_at = datetime.fromtimestamp(
                result_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
        app_state["integration_result"] = result
    return result


def save_integration_result(result: IntegrationResult, settings: Settings) -> None:
    enrich_integration_result_metadata(result)
    path = settings.integrated_dir / "result.json"
    path.write_text(result.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    app_state["integration_result"] = result


def enrich_knowledge_graph_metadata(graph: KnowledgeGraph, parsed: ParsedTextbook | None = None) -> KnowledgeGraph:
    if parsed:
        if not graph.chapters_total:
            graph.chapters_total = len(parsed.chapters)
        if not graph.chapter_ids:
            chapter_ids = []
            seen_titles = {node.chapter for node in graph.nodes}
            for chapter in parsed.chapters:
                if chapter.title in seen_titles:
                    chapter_ids.append(chapter.chapter_id)
            graph.chapter_ids = chapter_ids
        if not graph.chapters_processed:
            graph.chapters_processed = len(graph.chapter_ids)
    else:
        graph.chapters_processed = graph.chapters_processed or len(graph.chapter_ids)
    return graph


def enrich_integration_result_metadata(result: IntegrationResult) -> IntegrationResult:
    if not result.book_ids:
        book_ids = set()
        for node in result.integrated_graph.nodes:
            if node.textbook_id and node.textbook_id != "integrated":
                book_ids.add(node.textbook_id)
        for source_nodes in result.integrated_graph.source_mapping.values():
            for node_id in source_nodes:
                if "_node_" in node_id:
                    book_ids.add(node_id.split("_node_", 1)[0])
        result.book_ids = sorted(book_ids)
    result.alignment_group_count = result.alignment_group_count or len(result.decisions)
    return result


def restore_runtime_state(settings: Settings) -> None:
    app_state["parsed_textbooks"].clear()
    app_state["knowledge_graphs"].clear()
    app_state["integration_result"] = None
    app_state["alignment_groups"] = []
    app_state["alignment_scope"] = []

    for parsed_path in sorted(settings.parsed_dir.glob("*.json")):
        parsed = _load_model(parsed_path, ParsedTextbook)
        if parsed:
            app_state["parsed_textbooks"][parsed_path.stem] = parsed

    for graph_path in sorted(settings.graph_dir.glob("*.json")):
        graph = _load_model(graph_path, KnowledgeGraph)
        if graph:
            enrich_knowledge_graph_metadata(graph, app_state["parsed_textbooks"].get(graph_path.stem))
            if not graph.built_at:
                graph.built_at = datetime.fromtimestamp(
                    graph_path.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat(timespec="seconds").replace("+00:00", "Z")
            app_state["knowledge_graphs"][graph_path.stem] = graph

    result_path = settings.integrated_dir / "result.json"
    result = _load_model(result_path, IntegrationResult)
    if result:
        enrich_integration_result_metadata(result)
        if not result.built_at and result_path.exists():
            result.built_at = datetime.fromtimestamp(
                result_path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
        app_state["integration_result"] = result

    logger.info(
        "Runtime state restored: parsed=%d, graphs=%d, integration=%s",
        len(app_state["parsed_textbooks"]),
        len(app_state["knowledge_graphs"]),
        "yes" if app_state["integration_result"] else "no",
    )
