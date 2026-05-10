# Codex Handoff

Last session: 2026-05-10

## Scope

- Backend code (src/backend/)
- Do NOT touch frontend code

## What Codex Has Done

- Rewrote parser.py (3-layer PDF extraction: bookmarks → TOC → body scan)
- Created chapter_selection.py (low-signal chapter filtering)
- Re-parsed all 7 textbooks
- Built KG for all 7 books (partial: 1-2 chapters each)
- Ran 7-book integration (620→602 nodes, 12 merge decisions)
- Added pipeline/status API with stale detection
- Added build-all KG batch endpoint
- Fixed title cleaning (removes trailing artifacts)

## Next Backend Priorities

1. Expand KG chapter coverage (more chapters per book)
2. Re-run integration after KG expansion
3. Rebuild RAG index after KG expansion
4. Test teacher chat with real integration data

## Claude's Requests (Frontend-Needed APIs)

Claude has documented missing APIs in docs/Claude_handoff.md. The key ones:

1. `GET /api/kg/{book_id}/chapters` — list chapters for a parsed book
2. `DELETE /api/textbooks/{book_id}` — remove a book
3. `GET /api/integration/decisions/{id}` — single decision detail
4. `POST /api/integration/decisions/{id}/accept` — accept a decision
5. `POST /api/integration/decisions/{id}/reject` — reject a decision

These are low-priority for the backend pipeline but will improve frontend demo.
