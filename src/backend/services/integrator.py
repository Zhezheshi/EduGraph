import logging
from ..llm import LLMClient, THINKING_CONFIG
from ..models import KnowledgeNode, KnowledgeEdge, IntegratedGraph
from ..models import IntegrationDecision, IntegrationResult
from ..prompts.integration import INTEGRATION_SYSTEM_PROMPT, build_integration_prompt

logger = logging.getLogger(__name__)


async def integrate_aligned_groups(all_nodes, all_edges, alignment_groups, llm: LLMClient):
    node_lookup = {}
    for nodes in all_nodes.values():
        for n in nodes:
            node_lookup[n.id] = n

    decisions = []
    merged_nodes = []
    kept_node_ids = set()
    removed_node_ids = set()
    source_mapping = {}

    original_total = sum(len(n.definition) for n in node_lookup.values())
    integrated_total = 0

    for group in alignment_groups:
        if len(group) < 2:
            continue
        group_nodes = [node_lookup[nid] for nid in group if nid in node_lookup]
        if not group_nodes:
            continue

        try:
            nodes_data = [{"name": n.name, "definition": n.definition,
                          "textbook_id": n.textbook_id, "chapter": n.chapter, "page": n.page}
                         for n in group_nodes]

            result = await llm.chat_json(
                INTEGRATION_SYSTEM_PROMPT,
                build_integration_prompt(nodes_data),
                thinking=THINKING_CONFIG["integration"],
            )

            action = result.get("action", "merge")
            if action == "merge":
                pref_id = result.get("preferred_source", group_nodes[0].textbook_id)
                pref_node = next((n for n in group_nodes if n.textbook_id == pref_id), group_nodes[0])
                merged_id = f"merged_{len(decisions)+1:04d}"
                merged_node = KnowledgeNode(
                    id=merged_id,
                    name=result.get("merged_name", group_nodes[0].name),
                    definition=result.get("merged_definition", group_nodes[0].definition),
                    category=group_nodes[0].category,
                    textbook_id="integrated",
                    chapter=pref_node.chapter,
                    page=pref_node.page,
                    frequency=len(group_nodes),
                )
                merged_nodes.append(merged_node)
                source_mapping[merged_id] = group
                integrated_total += len(merged_node.definition)

                decisions.append(IntegrationDecision(
                    decision_id=f"merge_{len(decisions)+1:04d}",
                    action="merge", affected_nodes=group,
                    result_node_id=merged_id,
                    reason=result.get("reason", ""),
                    confidence=result.get("confidence", 0.8),
                ))
            elif action == "remove":
                kept_node_ids.add(group[0])
                removed_node_ids.update(group[1:])
                integrated_total += len(node_lookup[group[0]].definition)
                decisions.append(IntegrationDecision(
                    decision_id=f"remove_{len(decisions)+1:04d}",
                    action="remove", affected_nodes=group,
                    reason=result.get("reason", ""),
                    confidence=result.get("confidence", 0.7),
                ))
            else:
                for nid in group:
                    kept_node_ids.add(nid)
                integrated_total += sum(len(node_lookup[nid].definition) for nid in group)
                decisions.append(IntegrationDecision(
                    decision_id=f"keep_{len(decisions)+1:04d}",
                    action="keep", affected_nodes=group,
                    reason=result.get("reason", ""),
                    confidence=result.get("confidence", 0.8),
                ))
        except Exception as e:
            logger.error(f"Integration decision failed: {e}")
            merged_nodes.append(group_nodes[0])
            integrated_total += len(group_nodes[0].definition)

    aligned_set = set(nid for g in alignment_groups for nid in g)
    for nid, node in node_lookup.items():
        if nid not in aligned_set and nid not in removed_node_ids:
            merged_nodes.append(node)
            integrated_total += len(node.definition)

    for nid in kept_node_ids:
        if nid in node_lookup and node_lookup[nid] not in merged_nodes:
            merged_nodes.append(node_lookup[nid])

    id_remap = {}
    for nid in removed_node_ids:
        for group in alignment_groups:
            if nid in group:
                for other in group:
                    if other != nid and other not in removed_node_ids:
                        id_remap[nid] = other
                        break

    new_edges = []
    seen_edges = set()
    for edge in all_edges:
        src = id_remap.get(edge.source, edge.source)
        tgt = id_remap.get(edge.target, edge.target)
        key = (src, tgt, edge.relation_type)
        if src != tgt and key not in seen_edges:
            seen_edges.add(key)
            new_edges.append(KnowledgeEdge(
                source=src, target=tgt,
                relation_type=edge.relation_type,
                description=edge.description,
                strength=edge.strength,
            ))

    compression = integrated_total / max(original_total, 1)

    return IntegrationResult(
        decisions=decisions,
        integrated_graph=IntegratedGraph(nodes=merged_nodes, edges=new_edges, source_mapping=source_mapping),
        original_total_chars=original_total,
        integrated_total_chars=integrated_total,
        compression_ratio=compression,
        original_node_count=len(node_lookup),
        integrated_node_count=len(merged_nodes),
    )
