import re

from ..models import Chapter

LOW_SIGNAL_TITLES = (
    "\u76ee\u5f55",
    "contents",
    "\u7d22\u5f15",
    "index",
    "\u9644\u5f55",
    "\u524d\u8a00",
    "\u51fa\u7248\u8bf4\u660e",
    "\u7f16\u8005\u8bf4\u660e",
)


def is_low_signal_chapter(chapter: Chapter) -> bool:
    title = (chapter.title or "").strip().lower()
    if any(keyword in title for keyword in LOW_SIGNAL_TITLES):
        return True

    sample = (chapter.content or "")[:1200]
    dotted_leaders = sample.count("...") + sample.count("\u2026") + sample.count("\u00b7")
    short_numeric_lines = 0
    for line in sample.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if re.search(r"\d+\s*$", clean) and len(clean) <= 40:
            short_numeric_lines += 1
    return dotted_leaders >= 6 and short_numeric_lines >= 5


def select_chapters(chapters: list[Chapter], max_chapters: int = 0, usable_only: bool = True) -> list[Chapter]:
    selected = chapters
    if usable_only:
        filtered = [chapter for chapter in chapters if not is_low_signal_chapter(chapter)]
        if filtered:
            selected = filtered

    if max_chapters > 0:
        selected = selected[:max_chapters]
    return selected
