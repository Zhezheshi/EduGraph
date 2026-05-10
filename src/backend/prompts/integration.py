INTEGRATION_SYSTEM_PROMPT = """你是医学知识整合专家。对于被判定为重复的知识点组，做出整合决策。

决策类型：
- merge: 合并为一个知识点（多本教材描述同一概念）
- keep: 各自保留（虽然相似但角度不同）
- remove: 删除其中一个（内容完全冗余）

输出JSON格式：
{"action": "merge或keep或remove", "merged_name": "合并后的名称", "merged_definition": "合并后的定义（取最完整的描述）", "reason": "整合理由", "confidence": 0.0到1.0, "preferred_source": "保留哪个教材的版本（教材ID）"}"""


def build_integration_prompt(nodes):
    nodes_text = ""
    for i, n in enumerate(nodes):
        nodes_text += f"\n知识点{i+1}（来源：{n['textbook_id']}，{n['chapter']}，第{n['page']}页）：\n  名称：{n['name']}\n  定义：{n['definition']}\n"
    return f"以下{len(nodes)}个知识点被判定为语义相同或高度相似，请做出整合决策：{nodes_text}"
