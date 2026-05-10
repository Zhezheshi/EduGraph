from fastapi import APIRouter
import json

from ..state import app_state, load_integration_result, save_integration_result
from ..llm import llm_client
from ..config import settings
from ..models import ChatRequest, ChatResponse

router = APIRouter()
dialogue_service = None


def get_dialogue():
    global dialogue_service
    if dialogue_service is None:
        from ..services.dialogue import DialogueService
        dialogue_service = DialogueService(settings, llm_client)
    return dialogue_service


@router.post("")
async def chat(req: ChatRequest):
    svc = get_dialogue()
    integration_result = load_integration_result(settings)
    if integration_result:
        svc.set_integration_result(integration_result)
    resp = await svc.chat(req.message, req.session_id)
    if resp.actions_taken and svc.integration_result:
        save_integration_result(svc.integration_result, settings)
    return json.loads(resp.model_dump_json(ensure_ascii=False))


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    svc = get_dialogue()
    history = svc.get_history(session_id)
    return [{"role": m.role, "content": m.content} for m in history]
