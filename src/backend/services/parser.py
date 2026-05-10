import logging
import re
from pathlib import Path

import fitz

from ..models import Chapter, ParsedTextbook

logger = logging.getLogger(__name__)

CHAPTER_TOKEN = (
    r"(?:"
    r"\u7b2c[0-9\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u96f6\u3007]+"
    r"[\u7ae0\u7bc7\u7f16]"
    r"|Chapter\s+\d+"
    r")"
)
CHAPTER_LINE_RE = re.compile(rf"^\s*({CHAPTER_TOKEN})\s*[:：\-]?\s*(.*?)\s*$", re.IGNORECASE)
TOC_INLINE_RE = re.compile(
    rf"^\s*({CHAPTER_TOKEN})\s*[:：\-]?\s*(.+?)\s*(?:[.\u2026\u00b7\u22ef]{{2,}}|\s{{2,}})\s*(\d+)\s*$",
    re.IGNORECASE,
)
TOC_CHAPTER_ONLY_RE = re.compile(rf"^\s*({CHAPTER_TOKEN})\s*$", re.IGNORECASE)
PAGE_NUM_ONLY_RE = re.compile(r"^\s*(\d+)\s*$")
LEADING_INDEX_RE = re.compile(r"^\d+\s*[_\- ]+\s*")
ASCII_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TOC_MARKERS = ("\u76ee\u5f55", "contents")
SPECIAL_TITLES = (
    "\u7eea\u8bba",
    "\u5bfc\u8bba",
    "\u5f15\u8a00",
    "\u9644\u5f55",
)


def _sanitize(text: str) -> str:
    text = text or ""
    text = ASCII_CONTROL_RE.sub("", text)
    text = text.replace("\u3000", " ").replace("\ufeff", "")
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _sanitize_title(text: str) -> str:
    text = _sanitize(text)
    text = re.sub(r"[?\uff1f\ufffd]+$", "", text)
    text = re.sub(r"[.\u2026\u00b7\u22ef]+$", "", text)
    return text.strip()


def _strip_numeric_prefix(name: str) -> str:
    return LEADING_INDEX_RE.sub("", name).strip()


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    return _strip_numeric_prefix(_sanitize_title(stem)) or _sanitize_title(stem) or "Untitled"


def _build_title(token: str, suffix: str) -> str:
    token = _sanitize_title(token)
    suffix = _sanitize_title(suffix)
    return token if not suffix else f"{token} {suffix}"


def _chapter_key(title: str) -> str:
    match = CHAPTER_LINE_RE.match(_sanitize(title))
    if not match:
        return _sanitize(title).lower()
    return _sanitize(match.group(1)).lower()


def _looks_like_special_title(text: str) -> bool:
    return any(keyword in text for keyword in SPECIAL_TITLES)


def _looks_like_chapter_title(text: str) -> bool:
    clean = _sanitize_title(text)
    if not clean:
        return False
    if CHAPTER_LINE_RE.match(clean):
        return True
    return _looks_like_special_title(clean) and len(clean) <= 32


def _dedupe_entries(entries: list[tuple[str, int]], page_count: int) -> list[tuple[str, int]]:
    best_by_key: dict[str, tuple[str, int]] = {}

    for title, page in entries:
        title = _sanitize(title)
        title = _sanitize_title(title)
        if not title:
            continue
        page = max(1, min(int(page), page_count))
        key = _chapter_key(title)

        current = best_by_key.get(key)
        if not current:
            best_by_key[key] = (title, page)
            continue

        current_title, current_page = current
        current_match = CHAPTER_LINE_RE.match(current_title)
        new_match = CHAPTER_LINE_RE.match(title)
        current_suffix = _sanitize(current_match.group(2)) if current_match else ""
        new_suffix = _sanitize(new_match.group(2)) if new_match else ""
        current_score = (1 if current_suffix else 0, len(current_suffix), current_page)
        new_score = (1 if new_suffix else 0, len(new_suffix), page)
        if new_score > current_score:
            best_by_key[key] = (title, page)

    return sorted(best_by_key.values(), key=lambda item: (item[1], item[0]))


def _extract_from_bookmarks(doc: fitz.Document) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for item in doc.get_toc():
        if len(item) < 3:
            continue
        _, raw_title, page = item[:3]
        title = _sanitize(raw_title)
        title = _sanitize_title(title)
        if not title:
            continue

        match = CHAPTER_LINE_RE.match(title)
        if match:
            entries.append((_build_title(match.group(1), match.group(2)), page))
        elif _looks_like_special_title(title):
            entries.append((title, page))
    return _dedupe_entries(entries, doc.page_count)


def _looks_like_toc_page(text: str) -> bool:
    lower = text.lower()
    if any(marker in lower for marker in TOC_MARKERS):
        return True
    short_lines = [line for line in text.splitlines() if 0 < len(line.strip()) <= 80]
    if len(short_lines) < 4:
        return False
    score = 0
    for line in short_lines:
        clean = _sanitize(line)
        if TOC_INLINE_RE.match(clean):
            score += 2
        elif TOC_CHAPTER_ONLY_RE.match(clean) or PAGE_NUM_ONLY_RE.match(clean):
            score += 1
        elif "..." in clean or "\u2026" in clean:
            score += 1
    return score >= 3


def _collect_toc_lines(doc: fitz.Document) -> list[str]:
    toc_pages: list[int] = []
    for page_index in range(min(doc.page_count, 30)):
        text = _sanitize(doc.load_page(page_index).get_text())
        if _looks_like_toc_page(text):
            toc_pages.append(page_index)
            for next_page in range(page_index + 1, min(page_index + 6, doc.page_count)):
                next_text = _sanitize(doc.load_page(next_page).get_text())
                if _looks_like_toc_page(next_text):
                    toc_pages.append(next_page)
                else:
                    break
            break

    lines: list[str] = []
    for page_index in dict.fromkeys(toc_pages):
        text = _sanitize(doc.load_page(page_index).get_text())
        lines.extend([_sanitize(line) for line in text.splitlines() if _sanitize(line)])
    return lines


def _extract_from_toc_lines(doc: fitz.Document) -> list[tuple[str, int]]:
    lines = _collect_toc_lines(doc)
    if not lines:
        return []

    entries: list[tuple[str, int]] = []
    pending_token = ""
    pending_suffix = ""

    for line in lines:
        if any(marker in line.lower() for marker in TOC_MARKERS):
            continue

        inline = TOC_INLINE_RE.match(line)
        if inline:
            entries.append((_build_title(inline.group(1), inline.group(2)), int(inline.group(3))))
            pending_token = ""
            pending_suffix = ""
            continue

        if pending_token:
            page_only = PAGE_NUM_ONLY_RE.match(line)
            if page_only:
                entries.append((_build_title(pending_token, pending_suffix), int(page_only.group(1))))
                pending_token = ""
                pending_suffix = ""
                continue

            if not TOC_CHAPTER_ONLY_RE.match(line) and len(line) <= 80:
                pending_suffix = _sanitize(f"{pending_suffix} {line}")
                continue

            pending_token = ""
            pending_suffix = ""

        chapter_only = TOC_CHAPTER_ONLY_RE.match(line)
        if chapter_only:
            pending_token = chapter_only.group(1)
            pending_suffix = ""
            continue

        chapter_line = CHAPTER_LINE_RE.match(line)
        if chapter_line:
            suffix = chapter_line.group(2)
            page_match = PAGE_NUM_ONLY_RE.search(suffix)
            if page_match and len(suffix.strip()) > len(page_match.group(1)):
                title = _sanitize_title(suffix[:page_match.start()])
                entries.append((_build_title(chapter_line.group(1), title), int(page_match.group(1))))
            else:
                pending_token = chapter_line.group(1)
                pending_suffix = suffix

    return _dedupe_entries(entries, doc.page_count)


def _extract_from_body(doc: fitz.Document) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        text = _sanitize(page.get_text())
        lines = [_sanitize(line) for line in text.splitlines() if _sanitize(line)]
        for line in lines[:10]:
            if line.isdigit():
                continue
            match = CHAPTER_LINE_RE.match(line)
            if match:
                entries.append((_build_title(match.group(1), match.group(2)), page_index + 1))
                break
            if _looks_like_special_title(line) and len(line) <= 32:
                entries.append((line, page_index + 1))
                break
    return _dedupe_entries(entries, doc.page_count)


def _extract_chapter_entries(doc: fitz.Document) -> list[tuple[str, int]]:
    for extractor in (_extract_from_bookmarks, _extract_from_toc_lines, _extract_from_body):
        entries = extractor(doc)
        if len(entries) >= 2:
            return entries
    return [("全文", 1)]


def _clean_page_text(page_text: str) -> str:
    lines = []
    for raw_line in _sanitize(page_text).splitlines():
        line = raw_line.strip()
        if len(line) <= 1:
            continue
        if line.isdigit():
            continue
        lines.append(line)
    return "\n".join(lines)


def parse_pdf(filepath: str, textbook_id: str, filename: str) -> ParsedTextbook:
    doc = fitz.open(filepath)
    try:
        chapter_entries = _extract_chapter_entries(doc)
        chapters: list[Chapter] = []

        for index, (title, start_page) in enumerate(chapter_entries):
            next_page = chapter_entries[index + 1][1] if index + 1 < len(chapter_entries) else doc.page_count + 1
            end_page = max(start_page, min(next_page - 1, doc.page_count))

            content_parts = []
            for page_number in range(start_page - 1, end_page):
                content_parts.append(_clean_page_text(doc.load_page(page_number).get_text()))

            content = "\n".join(part for part in content_parts if part).strip()
            if len(content) < 50:
                continue

            chapters.append(Chapter(
                chapter_id=f"ch_{len(chapters) + 1:02d}",
                title=_sanitize_title(title),
                page_start=start_page,
                page_end=end_page,
                content=content,
                char_count=len(content),
            ))

        if not chapters:
            full_text = "\n".join(_clean_page_text(doc.load_page(i).get_text()) for i in range(doc.page_count)).strip()
            chapters = [Chapter(
                chapter_id="ch_01",
                title="全文",
                page_start=1,
                page_end=doc.page_count,
                content=full_text,
                char_count=len(full_text),
            )]

        total_chars = sum(chapter.char_count for chapter in chapters)
        return ParsedTextbook(
            textbook_id=textbook_id,
            filename=filename,
            title=_title_from_filename(filename),
            total_pages=doc.page_count,
            total_chars=total_chars,
            chapters=chapters,
        )
    finally:
        doc.close()


def parse_txt(filepath: str, textbook_id: str, filename: str) -> ParsedTextbook:
    content = Path(filepath).read_text(encoding="utf-8")
    lines = content.splitlines()
    chapters: list[Chapter] = []
    buffer: list[str] = []
    current_title = "全文"

    def flush() -> None:
        nonlocal buffer, current_title
        chapter_content = "\n".join(buffer).strip()
        if not chapter_content:
            return
        chapters.append(Chapter(
            chapter_id=f"ch_{len(chapters) + 1:02d}",
            title=current_title,
            page_start=1,
            page_end=1,
            content=chapter_content,
            char_count=len(chapter_content),
        ))
        buffer = []

    for line in lines:
        clean = _sanitize(line)
        match = CHAPTER_LINE_RE.match(clean)
        if match:
            flush()
            current_title = _build_title(match.group(1), match.group(2))
            continue
        if clean.startswith("#"):
            flush()
            current_title = clean.lstrip("#").strip() or current_title
            continue
        buffer.append(line)

    flush()
    if not chapters:
        chapters = [Chapter(
            chapter_id="ch_01",
            title="全文",
            page_start=1,
            page_end=1,
            content=content,
            char_count=len(content),
        )]

    return ParsedTextbook(
        textbook_id=textbook_id,
        filename=filename,
        title=_title_from_filename(filename),
        total_pages=1,
        total_chars=len(content),
        chapters=chapters,
        format="txt",
    )


def parse_md(filepath: str, textbook_id: str, filename: str) -> ParsedTextbook:
    return parse_txt(filepath, textbook_id, filename)
