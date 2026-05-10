import logging
from ..llm import LLMClient, THINKING_CONFIG
from ..models import KnowledgeNode, KnowledgeEdge, KnowledgeGraph, Chapter
from ..prompts.extraction import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_prompt

logger = logging.getLogger(__name__)

MAX_CHARS_PER_CALL = 3000


async def extract_knowledge_graph(
    llm: LLMClient,
    textbook_id: str,
    textbook_name: str,
    chapters: list[Chapter],
    node_counter_start: int = 0,
):
    all_nodes, all_edges = [], []
    node_counter = node_counter_start

    for chapter in chapters:
        content = chapter.content
        segments = [content[i:i+MAX_CHARS_PER_CALL] for i in range(0, len(content), MAX_CHARS_PER_CALL)]

        for seg_idx, segment in enumerate(segments):
            if len(segment.strip()) < 100:
                continue

            node_counter_start = node_counter
            user_prompt = build_extraction_user_prompt(
                textbook_name, chapter.title, chapter.page_start + seg_idx, segment
            )

            try:
                result = await llm.chat_json(
                    EXTRACTION_SYSTEM_PROMPT, user_prompt,
                    thinking=THINKING_CONFIG["extraction"], max_tokens=4000,
                )

                for n in result.get("nodes", []):
                    node_counter += 1
                    all_nodes.append(KnowledgeNode(
                        id=f"{textbook_id}_node_{node_counter:04d}",
                        name=n.get("name", ""),
                        definition=n.get("definition", ""),
                        category=n.get("category", "核心概念"),
                        textbook_id=textbook_id,
                        chapter=chapter.title,
                        page=chapter.page_start + seg_idx,
                    ))

                local_nodes = all_nodes[node_counter_start:]
                for e in result.get("edges", []):
                    src_id = _find_node_id(local_nodes, e.get("source", ""))
                    tgt_id = _find_node_id(local_nodes, e.get("target", ""))
                    if src_id and tgt_id:
                        all_edges.append(KnowledgeEdge(
                            source=src_id, target=tgt_id,
                            relation_type=e.get("relation_type", "parallel"),
                            description=e.get("description", ""),
                            strength=e.get("strength", 0.8),
                        ))
            except Exception as ex:
                logger.error(f"Extraction failed for {chapter.title} seg {seg_idx}: {ex}")
                continue

    logger.info(f"Extracted {len(all_nodes)} nodes, {len(all_edges)} edges for {textbook_id}")
    return KnowledgeGraph(
        textbook_id=textbook_id,
        nodes=all_nodes,
        edges=all_edges,
        chapters_processed=len(chapters),
        chapter_ids=[chapter.chapter_id for chapter in chapters],
    )


def _find_node_id(nodes, name):
    for n in nodes:
        if n.name == name or name in n.name or n.name in name:
            return n.id
    return None
