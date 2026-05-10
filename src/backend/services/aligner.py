import logging
import numpy as np
from ..llm import LLMClient, THINKING_CONFIG
from ..models import KnowledgeNode
from ..prompts.alignment import ALIGNMENT_SYSTEM_PROMPT, build_alignment_prompt

logger = logging.getLogger(__name__)


async def align_cross_textbooks(all_nodes: dict[str, list[KnowledgeNode]], llm: LLMClient, threshold=0.85):
    flat = []
    for book_id, nodes in all_nodes.items():
        for n in nodes:
            flat.append(n)

    if len(flat) < 2:
        return []

    texts = [f"{n.name} {n.definition}" for n in flat]
    logger.info(f"Embedding {len(texts)} nodes for alignment...")

    embeddings = []
    batch_size = 10
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        emb = await llm.embed(batch)
        embeddings.extend(emb)

    embeddings = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    sim_matrix = embeddings @ embeddings.T

    candidate_pairs = []
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i].textbook_id != flat[j].textbook_id and sim_matrix[i][j] >= threshold:
                candidate_pairs.append((i, j, float(sim_matrix[i][j])))

    candidate_pairs.sort(key=lambda x: x[2], reverse=True)
    logger.info(f"Pass 1: {len(candidate_pairs)} candidate pairs above {threshold}")

    confirmed = {}
    group_id = 0

    for i, j, score in candidate_pairs[:200]:
        gi, gj = confirmed.get(i), confirmed.get(j)
        if gi is not None and gi == gj:
            continue

        try:
            node_a = {"name": flat[i].name, "definition": flat[i].definition,
                       "textbook_id": flat[i].textbook_id, "chapter": flat[i].chapter}
            node_b = {"name": flat[j].name, "definition": flat[j].definition,
                       "textbook_id": flat[j].textbook_id, "chapter": flat[j].chapter}

            result = await llm.chat_json(
                ALIGNMENT_SYSTEM_PROMPT,
                build_alignment_prompt(node_a, node_b),
                thinking=THINKING_CONFIG["alignment"],
            )

            if result.get("judgment") == "same" and result.get("confidence", 0) >= 0.7:
                if gi is not None and gj is not None:
                    for k, v in list(confirmed.items()):
                        if v == gj:
                            confirmed[k] = gi
                elif gi is not None:
                    confirmed[j] = gi
                elif gj is not None:
                    confirmed[i] = gj
                else:
                    confirmed[i] = group_id
                    confirmed[j] = group_id
                    group_id += 1
        except Exception as e:
            logger.error(f"LLM alignment failed: {e}")

    groups_dict = {}
    for idx, gid in confirmed.items():
        groups_dict.setdefault(gid, []).append(flat[idx].id)

    return list(groups_dict.values())
