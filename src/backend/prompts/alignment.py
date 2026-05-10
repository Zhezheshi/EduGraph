ALIGNMENT_SYSTEM_PROMPT = """你是医学知识对齐专家。判断以下两个来自不同教材的知识点是否描述同一概念。

判断标准：
- 名称不同但语义相同→same（如"白细胞"和"leukocyte"）
- 名称相似且定义核心内容一致→same
- 是上下位关系但不是同一概念→different（如"免疫细胞"和"T细胞"）
- 明显不同的概念→different

只输出JSON：{"judgment": "same或different", "confidence": 0.0到1.0, "reason": "一句话理由"}"""


def build_alignment_prompt(node_a, node_b):
    return f"""知识点A：
- 名称：{node_a['name']}
- 定义：{node_a['definition']}
- 来源：{node_a['textbook_id']} {node_a['chapter']}

知识点B：
- 名称：{node_b['name']}
- 定义：{node_b['definition']}
- 来源：{node_b['textbook_id']} {node_b['chapter']}"""
