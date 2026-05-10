import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import or_

from ..database import SessionLocal, TextbookDB
from ..config import settings
from ..state import save_parsed_textbook

from ..services.parser import parse_pdf, parse_txt, parse_md

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
