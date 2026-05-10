RAG_SYSTEM_PROMPT = """你是一个医学知识问答助手。你必须严格基于提供的参考内容来回答问题。

## 回答规则
1. 只使用提供的参考内容回答，不要使用你的先验知识
2. 每个陈述必须附带引用，格式为[教材名称, 章节, 第X页]
3. 如果参考内容不足以回答问题，明确说明"当前知识库中未找到完整的相关信息"
4. 回答要准确、有条理，适当使用列表和加粗
5. 如果多个教材对同一概念有不同描述，指出差异"""


def build_rag_prompt(question, chunks):
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"\n--- 参考内容{i+1}（来源：{chunk['textbook_name']}，{chunk['chapter']}，第{chunk['page']}页）---\n{chunk['content']}\n"
    return f"## 参考内容\n{context}\n## 问题\n{question}\n\n请基于以上参考内容回答问题，每个陈述附带引用。"""
