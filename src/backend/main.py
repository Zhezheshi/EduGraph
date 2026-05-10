import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .llm import llm_client
from .routers import textbooks, knowledge_graph, integration, rag, chat, report, pipeline
from .state import restore_runtime_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")
    restore_runtime_state(settings)
    try:
        rag.get_rag_engine().load_from_disk()
    except Exception:
        logger.exception("Failed to restore RAG index from disk")
    yield


app = FastAPI(title="学科知识整合智能体", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(textbooks.router, prefix="/api/textbooks", tags=["textbooks"])
app.include_router(knowledge_graph.router, prefix="/api/kg", tags=["knowledge_graph"])
app.include_router(integration.router, prefix="/api/integration", tags=["integration"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "token_usage": llm_client.get_token_usage()}
