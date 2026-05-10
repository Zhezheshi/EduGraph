import json, logging
from ..config import Settings
from ..llm import LLMClient, THINKING_CONFIG
from ..models import ChatMessage, ChatResponse, IntegrationResult
from ..prompts.dialogue import DIALOGUE_SYSTEM_PROMPT, build_dialogue_prompt

logger = logging.getLogger(__name__)


class DialogueService:
    def __init__(self, settings: Settings, llm: LLMClient):
        self.settings = settings
        self.llm = llm
        self.sessions: dict[str, list[ChatMessage]] = {}
        self.integration_result: IntegrationResult | None = None

    def set_integration_result(self, result: IntegrationResult):
        self.integration_result = result

    def _get_decisions_context(self):
        if not self.integration_result:
            return "尚未执行整合。"
        lines = []
        for d in self.integration_result.decisions[:20]:
            lines.append(f"- [{d.decision_id}] {d.action}: {d.reason} (置信度: {d.confidence:.1%})")
        return "\n".join(lines)

    async def chat(self, message: str, session_id: str = "default") -> ChatResponse:
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        history = self.sessions[session_id]
        decisions_ctx = self._get_decisions_context()

        try:
            raw = await self.llm.chat(
                messages=[
                    {"role": "system", "content": DIALOGUE_SYSTEM_PROMPT},
                    {"role": "user", "content": build_dialogue_prompt(
                        message, decisions_ctx,
                        [{"role": m.role, "content": m.content} for m in history])},
                ],
                json_mode=True,
                thinking=THINKING_CONFIG["dialogue"],
                max_tokens=1000,
            )
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(raw)
            reply_text = parsed.get("reply", raw)
            action = parsed.get("action")
            actions_taken = []

            if action and action != "null" and self.integration_result:
                target_id = parsed.get("target_decision_id", "")
                if action == "split":
                    actions_taken = self._handle_split(target_id)
                elif action == "restore":
                    actions_taken = self._handle_restore(target_id)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Dialogue parse error: {e}")
            reply_text = "抱歉，我无法理解您的请求。请换一种方式描述。"
            actions_taken = []

        history.append(ChatMessage(role="user", content=message))
        history.append(ChatMessage(role="assistant", content=reply_text))

        return ChatResponse(reply=reply_text, session_id=session_id, actions_taken=actions_taken)

    def _handle_split(self, decision_id):
        if not self.integration_result:
            return []
        for d in self.integration_result.decisions:
            if d.decision_id == decision_id and d.action == "merge":
                d.action = "keep"
                return [f"已撤销合并决策 {decision_id}，知识点已恢复为各自独立"]
        return []

    def _handle_restore(self, decision_id):
        if not self.integration_result:
            return []
        for d in self.integration_result.decisions:
            if d.decision_id == decision_id and d.action == "remove":
                d.action = "keep"
                return [f"已恢复决策 {decision_id} 中的知识点"]
        return []

    def get_history(self, session_id: str):
        return self.sessions.get(session_id, [])
