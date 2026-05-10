import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..database import SessionLocal, TextbookDB
from ..config import settings
from ..state import app_state, load_integration_result, save_parsed_textbook

from ..services.parser import parse_pdf, parse_txt, parse_md, parse_docx

logger = logging.getLogger(__name__)
router = APIRouter()


def _derive_title(filename: str) -> str:
    stem = Path(filename or "untitled").stem.strip()
    return stem or "untitled"


def _next_book_id(db) -> str:
    max_index = 0
    for (book_id,) in db.query(TextbookDB.id).all():
        if not book_id.startswith("book_"):
            continue
        suffix = book_id.split("_", 1)[1]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return f"book_{max_index + 1:02d}"


def _build_storage_name(book_id: str, filename: str) -> str:
    suffix = Path(filename or "upload.bin").suffix.lower() or ".bin"
    return f"{book_id}{suffix}"


def _display_filename(book: TextbookDB) -> str:
    suffix = Path(book.filename or "").suffix
    return f"{book.title}{suffix}" if book.title else book.filename


def _parse_uploaded_book(book: TextbookDB):
    filepath = settings.textbook_dir / book.filename
    if not filepath.exists():
        raise HTTPException(400, "File not found on disk")

    ext = Path(book.filename).suffix.lower()
    display_filename = _display_filename(book)
    if ext == ".pdf":
        parsed = parse_pdf(str(filepath), book.id, display_filename)
    elif ext == ".txt":
        parsed = parse_txt(str(filepath), book.id, display_filename)
    elif ext in (".md", ".markdown"):
        parsed = parse_md(str(filepath), book.id, display_filename)
    elif ext == ".docx":
        parsed = parse_docx(str(filepath), book.id, display_filename)
    else:
        raise HTTPException(400, f"Unsupported format: {ext}")
    return parsed, ext.lstrip(".")


@router.post("/upload")
async def upload_textbooks(files: list[UploadFile] = File(...)):
    results = []
    db = SessionLocal()
    try:
        for upload in files:
            original_name = Path(upload.filename or "untitled").name
            title = _derive_title(original_name)
            book_id = _next_book_id(db)
            storage_name = _build_storage_name(book_id, original_name)
            dest = settings.textbook_dir / storage_name
            with open(dest, "wb") as out:
                shutil.copyfileobj(upload.file, out)

            db.add(TextbookDB(
                id=book_id,
                filename=storage_name,
                title=title,
                file_type=Path(storage_name).suffix.lstrip("."),
                status="uploaded",
            ))
            results.append({
                "book_id": book_id,
                "filename": original_name,
                "stored_filename": storage_name,
                "title": title,
                "status": "uploaded",
            })
        db.commit()
    finally:
        db.close()
    return results


@router.get("")
async def list_textbooks():
    db = SessionLocal()
    try:
        books = db.query(TextbookDB).all()
        return [{"id": b.id, "filename": b.filename, "display_name": _display_filename(b), "title": b.title,
                 "file_type": b.file_type or Path(b.filename).suffix.lstrip("."), "status": b.status,
                 "total_pages": b.total_pages, "total_chars": b.total_chars}
                for b in books]
    finally:
        db.close()


@router.get("/{book_id}")
async def get_textbook(book_id: str):
    parsed_path = settings.parsed_dir / f"{book_id}.json"
    if parsed_path.exists():
        return json.loads(parsed_path.read_text(encoding="utf-8"))
    raise HTTPException(404, "Textbook not parsed yet")


@router.post("/{book_id}/parse")
async def parse_textbook(book_id: str, force: bool = False):
    db = SessionLocal()
    try:
        book = db.query(TextbookDB).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(404, "Textbook not found")

        if book.status == "parsed" and not force:
            existing = settings.parsed_dir / f"{book_id}.json"
            if existing.exists():
                return {"status": "skipped", "book_id": book_id, "reason": "already parsed"}

        parsed, file_type = _parse_uploaded_book(book)

        book.status = "parsed"
        book.file_type = file_type
        book.total_pages = parsed.total_pages
        book.total_chars = parsed.total_chars
        db.commit()

        save_parsed_textbook(parsed, settings)

        return {"status": "parsed", "book_id": book_id, "chapters": len(parsed.chapters),
                "total_chars": parsed.total_chars}
    finally:
        db.close()


@router.post("/parse-all")
async def parse_all_textbooks(force: bool = False, books: str = ""):
    results = []
    db = SessionLocal()
    try:
        selected_ids = [item.strip() for item in books.split(",") if item.strip()]
        query = db.query(TextbookDB)
        if selected_ids:
            query = query.filter(TextbookDB.id.in_(selected_ids))

        for book in query.order_by(TextbookDB.id).all():
            if book.status == "parsed" and not force:
                results.append({"book_id": book.id, "status": "skipped"})
                continue
            try:
                parsed, file_type = _parse_uploaded_book(book)
                book.status = "parsed"
                book.file_type = file_type
                book.total_pages = parsed.total_pages
                book.total_chars = parsed.total_chars

                save_parsed_textbook(parsed, settings)
                results.append({"book_id": book.id, "chapters": len(parsed.chapters), "status": "parsed"})
            except Exception as e:
                logger.error(f"Parse failed for {book.filename}: {e}")
                results.append({"book_id": book.id, "status": "failed", "error": str(e)})
        db.commit()
    finally:
        db.close()
    return results


def _delete_if_exists(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


def _invalidate_integration_if_needed(book_id: str) -> bool:
    result = load_integration_result(settings)
    if not result or book_id not in result.book_ids:
        return False

    result_path = settings.integrated_dir / "result.json"
    _delete_if_exists(result_path)
    app_state["integration_result"] = None
    app_state["alignment_groups"] = []
    app_state["alignment_scope"] = []
    return True


def _invalidate_rag_if_needed(book_id: str) -> bool:
    meta_path = settings.index_dir / "meta.json"
    chunks_path = settings.index_dir / "chunks.json"
    embeddings_path = settings.index_dir / "embeddings.npy"

    indexed_book_ids = set()
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            indexed_book_ids = set(meta.get("indexed_book_ids", []))
        except Exception:
            logger.exception("Failed to inspect RAG meta during textbook deletion")

    if not indexed_book_ids and chunks_path.exists():
        try:
            raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
            indexed_book_ids = {chunk.get("textbook_id") for chunk in raw_chunks if chunk.get("textbook_id")}
        except Exception:
            logger.exception("Failed to inspect RAG chunks during textbook deletion")

    if book_id not in indexed_book_ids:
        return False

    _delete_if_exists(meta_path)
    _delete_if_exists(chunks_path)
    _delete_if_exists(embeddings_path)

    try:
        from .rag import rag_engine

        if rag_engine is not None:
            rag_engine.embeddings_np = None
            rag_engine.chunks = []
            rag_engine.indexed_textbooks = []
            rag_engine.indexed_book_ids = []
            rag_engine.built_at = None
    except Exception:
        logger.exception("Failed to reset in-memory RAG engine during textbook deletion")

    return True


@router.delete("/{book_id}")
async def delete_textbook(book_id: str):
    db = SessionLocal()
    try:
        book = db.query(TextbookDB).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(404, "Textbook not found")

        storage_path = settings.textbook_dir / book.filename
        parsed_path = settings.parsed_dir / f"{book_id}.json"
        graph_path = settings.graph_dir / f"{book_id}.json"

        db.delete(book)
        db.commit()

        deleted_files = {
            "textbook": _delete_if_exists(storage_path),
            "parsed": _delete_if_exists(parsed_path),
            "graph": _delete_if_exists(graph_path),
        }

        app_state["parsed_textbooks"].pop(book_id, None)
        app_state["knowledge_graphs"].pop(book_id, None)

        integration_invalidated = _invalidate_integration_if_needed(book_id)
        rag_invalidated = _invalidate_rag_if_needed(book_id)

        return {
            "status": "deleted",
            "book_id": book_id,
            "deleted_files": deleted_files,
            "integration_invalidated": integration_invalidated,
            "rag_invalidated": rag_invalidated,
        }
    finally:
        db.close()
