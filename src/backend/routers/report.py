from fastapi import APIRouter, HTTPException

from ..state import load_integration_result
from ..config import settings

router = APIRouter()


@router.get("")
async def get_report():
    result = load_integration_result(settings)
    if not result:
        raise HTTPException(404, "Integration not run yet")

    stats = {
        "original_total_chars": result.original_total_chars,
        "integrated_total_chars": result.integrated_total_chars,
        "compression_ratio": f"{result.compression_ratio:.1%}",
        "original_node_count": result.original_node_count,
        "integrated_node_count": result.integrated_node_count,
        "total_decisions": len(result.decisions),
        "merge_count": sum(1 for d in result.decisions if d.action == "merge"),
        "keep_count": sum(1 for d in result.decisions if d.action == "keep"),
        "remove_count": sum(1 for d in result.decisions if d.action == "remove"),
    }

    key_cases = []
    for d in result.decisions[:5]:
        key_cases.append({
            "decision_id": d.decision_id,
            "action": d.action,
            "reason": d.reason,
            "confidence": d.confidence,
            "affected_nodes": d.affected_nodes[:3],
        })

    return {"stats": stats, "key_cases": key_cases}
