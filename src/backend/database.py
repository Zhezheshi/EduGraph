from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from .config import settings

engine = create_engine(f"sqlite:///{settings.base_dir / 'edugraph.db'}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class TextbookDB(Base):
    __tablename__ = "textbooks"
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=False)
    file_type = Column(String, default="pdf")
    total_pages = Column(Integer, default=0)
    total_chars = Column(Integer, default=0)
    status = Column(String, default="uploaded")
    created_at = Column(DateTime, default=datetime.utcnow)


class ChapterDB(Base):
    __tablename__ = "chapters"
    id = Column(String, primary_key=True)
    textbook_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    page_start = Column(Integer)
    page_end = Column(Integer)
    content = Column(Text)
    char_count = Column(Integer, default=0)


class KnowledgeNodeDB(Base):
    __tablename__ = "knowledge_nodes"
    id = Column(String, primary_key=True)
    textbook_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    definition = Column(Text)
    category = Column(String)
    chapter = Column(String)
    page = Column(Integer)
    frequency = Column(Integer, default=1)
    importance = Column(Float, default=0.8)


class KnowledgeEdgeDB(Base):
    __tablename__ = "knowledge_edges"
    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    target = Column(String, nullable=False)
    relation_type = Column(String, nullable=False)
    description = Column(Text)
    strength = Column(Float, default=0.8)
    textbook_id = Column(String, nullable=False)


class IntegrationDecisionDB(Base):
    __tablename__ = "integration_decisions"
    id = Column(String, primary_key=True)
    action = Column(String, nullable=False)
    affected_nodes = Column(Text)
    result_node_id = Column(String, nullable=True)
    reason = Column(Text)
    confidence = Column(Float, default=0.8)
    status = Column(String, default="pending")


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, default="default")
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
