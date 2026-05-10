# GLM Handoff Document

Generated: 2026-05-10

---

## 1. Last Stable State

- **Backend**: Running at `http://localhost:8000`, health check returns OK, token usage ~213K
- **Frontend**: Built (dist/ exists), dev server NOT currently running
- **Database**: SQLite at `src/backend/data/edugraph.db`, 7 textbooks registered and parsed

### Confirmed working APIs (actually called and got 200 OK):

| API | Status | Notes |
|-----|--------|-------|
| `GET /api/health` | OK | |
| `GET /api/textbooks` | OK | Returns 7 books, all `parsed` |
| `POST /api/kg/build/{book_id}?max_chapters=2` | OK | Tested for book_03, book_05, book_07 |
| `GET /api/kg/{book_id}` | OK | Loads from disk |
| `POST /api/integration/run` | OK | But takes 2-3 min, needs KG in memory first |
| `GET /api/integration/stats` | OK | Only if integration_result in memory |
| `GET /api/integration/decisions` | OK | Only if integration_result in memory |
| `POST /api/rag/index?max_chapters=2&books=book_03,book_05,book_07` | OK | 252 chunks indexed |
| `POST /api/rag/query` | OK | Returns answer + 5 citations with scores |
| `GET /api/rag/status` | OK | |
| `POST /api/chat` | Partial | Returns 200 but can't see integration result (memory issue) |

---

## 2. What Actually Ran Successfully

### 2.1 Textbook Registration: COMPLETE
- 7 textbooks registered directly in SQLite (bypassed upload API due to Chinese filename encoding)
- Book IDs: `book_01` through `book_07`
- Files exist at `src/backend/data/textbooks/*.pdf`

### 2.2 Textbook Parsing: COMPLETE
- All 7 parsed via `POST /api/textbooks/parse-all`

| Book ID | Title | Pages | Chars | Chapters |
|---------|-------|-------|-------|----------|
| book_01 | 局部解剖学 | 305 | 317,465 | 8 |
| book_02 | 组织学与胚胎学 | 319 | 294,728 | 56 |
| book_03 | 生理学 | 450 | 613,613 | 13 |
| book_04 | 医学微生物学 | 386 | 1,008,892 | 45 |
| book_05 | 病理学 | 418 | 524,647 | 20 |
| book_06 | 传染病学 | 398 | 1,051,973 | 10 |
| book_07 | 病理生理学 | 291 | 368,223 | 20 |

### 2.3 KG Construction: COMPLETE (first 2 chapters only)
- Only book_03, book_05, book_07 (3 books)
- Each limited to first 2 chapters via `?max_chapters=2`

| Book | Nodes | Edges |
|------|-------|-------|
| book_03 (生理学) | 220 | 180 |
| book_05 (病理学) | 113 | 112 |
| book_07 (病理生理学) | 81 | 67 |

### 2.4 Integration: COMPLETE (disk file exists)
- Result saved to `data/integrated/result.json`
- Original: 414 nodes -> Integrated: 401 nodes (compression 98.9%)
- 8 merge decisions, all confidence >= 0.80
- Merge examples: 自分泌, 稳态/Homeostasis, 病理生理学, 细胞损伤

### 2.5 RAG: COMPLETE (tested successfully)
- Index built with 252 chunks from 3 books (first 2 chapters each)
- Uses sklearn cosine_similarity (NOT FAISS - faiss-cpu not installed)
- Query "细胞膜的物质转运方式" returned 2022-char answer with 5 citations, top score 0.835
- Query "什么是炎症" returned answer with citations (correctly noted limited coverage in first 2 chapters)

### 2.6 Teacher Dialogue: PARTIAL
- API responds 200
- Successfully tested with simple messages
- **Problem**: After backend restart, `integration_result` is lost from memory. Chat says "尚未执行任何整合操作" because `_get_decisions_context()` returns empty string
- The `_handle_split` and `_handle_restore` logic is coded but never tested with actual integration data loaded

---

## 3. Data File Trust Assessment

### TRUSTED - Current valid results:

| File | Status | Details |
|------|--------|---------|
| `data/parsed/book_01.json` through `book_07.json` | VALID | All 7 parsed, complete textbooks |
| `data/graphs/book_03.json` | VALID | 220 nodes, 180 edges, first 2 chapters |
| `data/graphs/book_05.json` | VALID | 113 nodes, 112 edges, first 2 chapters |
| `data/graphs/book_07.json` | VALID | 81 nodes, 67 edges, first 2 chapters |
| `data/integrated/result.json` | VALID | 401 integrated nodes, 8 decisions |

### NOT TRUSTED / MISSING:

| File | Status |
|------|--------|
| `data/graphs/book_01.json` | MISSING - KG never built for this book |
| `data/graphs/book_02.json` | MISSING |
| `data/graphs/book_04.json` | MISSING |
| `data/graphs/book_06.json` | MISSING |
| RAG index | MEMORY ONLY - lost on restart, needs rebuild each time |

---

## 4. Files Modified (complete list)

### Backend source files (all created/modified in this session):

```
src/backend/config.py
src/backend/llm.py
src/backend/main.py
src/backend/models.py
src/backend/state.py
src/backend/database.py
src/backend/services/parser.py
src/backend/services/extractor.py
src/backend/services/aligner.py
src/backend/services/integrator.py
src/backend/services/rag_engine.py
src/backend/services/dialogue.py
src/backend/routers/textbooks.py
src/backend/routers/knowledge_graph.py
src/backend/routers/integration.py
src/backend/routers/rag.py
src/backend/routers/chat.py
src/backend/routers/report.py
src/backend/prompts/extraction.py
src/backend/prompts/alignment.py
src/backend/prompts/integration.py
src/backend/prompts/rag_qa.py
src/backend/prompts/dialogue.py
```

### Frontend source files:

```
src/frontend/src/App.jsx
src/frontend/src/App.css
src/frontend/src/api/client.js
src/frontend/vite.config.js
```

### Config:

```
.env                          # API key and settings
requirements.txt              # Python dependencies
```

---

## 5. Unfixed Problems

### Critical (blocks demo):

1. **No disk restore on startup** - `app_state` (knowledge_graphs, integration_result, RAG index) is memory-only. After restart, must rerun the entire pipeline.
   - Was NOT attempted. The `_ensure_kgs_loaded()` function was added to `integration.py` but only loads KGs from disk, not the integration result.
   - **Fix needed**: Add startup lifecycle in `main.py` that loads `data/graphs/*.json` into `app_state["knowledge_graphs"]` and `data/integrated/result.json` into `app_state["integration_result"]`.

2. **RAG is fully memory-only** - No disk persistence at all. FAISS index or sklearn embeddings are rebuilt from scratch every time.
   - **Fix needed**: Save `embeddings_np` and `chunks` to disk (numpy file + JSON), load on startup.

3. **Embedding API batch size limit = 10** - DashScope embedding API rejects batches > 10.
   - **Fixed** in aligner.py and rag_engine.py (changed batch_size from 20 to 10).
   - But `integrator.py` may also call embed - need to verify.

### Medium (affects quality):

4. **Compression ratio only ~1%** - With only first 2 chapters, there's very little cross-textbook overlap. Full book extraction would produce more merges.
   - Expected behavior with limited data.

5. **Chinese filenames garbled via curl** - `curl -F "files=@中文.pdf"` corrupts filenames.
   - Workaround: Register books directly in SQLite, bypass upload API.
   - Frontend upload via browser works fine (FormData handles encoding correctly).

6. **TOC parsing for books 01, 06** - These have no PDF bookmarks. Custom multi-line TOC parser was added but only tested lightly.

### Low (cosmetic):

7. **Chapter titles contain `??` artifacts** - e.g. "第一章　绪论??" - These are from the PDF extraction encoding.
8. **Thinking mode + JSON mode conflict** - `enable_thinking=True` + `response_format=json` on qwen3.6-flash causes JSON parse failures. Fixed by disabling thinking for dialogue, but alignment and integration still use thinking=True which works because they use `chat_json()` not raw chat.

### Half-done changes:

9. `integration.py` has `_ensure_kgs_loaded()` but it only loads KG files, not the integration result.
10. `rag_engine.py` was fully rewritten to use sklearn (FAISS dependency removed) - this change is complete.

---

## 6. Reproduction Commands

### Start backend:
```bash
cd d:/project/Hack_quick/src
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Start frontend:
```bash
cd d:/project/Hack_quick/src/frontend
npm run dev
# Runs on http://localhost:3000, proxies /api to localhost:8000
```

### Register textbooks (after restart, do this first):
```bash
python -c "
import sqlite3
conn = sqlite3.connect('d:/project/Hack_quick/src/backend/data/edugraph.db')
for i, (fn, title) in enumerate([
    ('01_局部解剖学.pdf','01_局部解剖学'), ('02_组织学与胚胎学.pdf','02_组织学与胚胎学'),
    ('03_生理学.pdf','03_生理学'), ('04_医学微生物学.pdf','04_医学微生物学'),
    ('05_病理学.pdf','05_病理学'), ('06_传染病学.pdf','06_传染病学'),
    ('07_病理生理学.pdf','07_病理生理学')]):
    conn.execute('INSERT OR REPLACE INTO textbooks VALUES (?,?,?,?,0,0)',
        (f'book_{i+1:02d}', fn, title, 'uploaded'))
conn.commit(); conn.close()
"
```

### Parse all textbooks:
```bash
curl -s -X POST http://localhost:8000/api/textbooks/parse-all | python -m json.tool
```

### Build KG (per book, first 2 chapters):
```bash
curl -s -X POST "http://localhost:8000/api/kg/build/book_03?max_chapters=2"
curl -s -X POST "http://localhost:8000/api/kg/build/book_05?max_chapters=2"
curl -s -X POST "http://localhost:8000/api/kg/build/book_07?max_chapters=2"
```

### Run integration:
```bash
curl -s -X POST http://localhost:8000/api/integration/run
# Takes 2-3 minutes
```

### Build RAG index:
```bash
curl -s -X POST "http://localhost:8000/api/rag/index?max_chapters=2&books=book_03,book_05,book_07"
```

### Query RAG:
```bash
python -c "
import requests
resp = requests.post('http://localhost:8000/api/rag/query', json={'question': '细胞膜的物质转运方式有哪些？'})
print(resp.json()['answer'][:200])
"
```

### Test chat:
```bash
python -c "
import requests
resp = requests.post('http://localhost:8000/api/chat', json={'message': '请介绍整合结果'})
print(resp.json()['reply'])
"
```

---

## 7. Recommended Demo Order

**Most stable path** (do these in order, don't skip):

1. Start backend + frontend
2. Show `GET /api/textbooks` - 7 books parsed
3. Show `GET /api/kg/book_03` - knowledge graph with 220 nodes
4. Run `POST /api/integration/run` - wait 2-3 min
5. Show `GET /api/integration/stats` + `GET /api/integration/decisions`
6. Run `POST /api/rag/index?max_chapters=2&books=book_03,book_05,book_07` - wait 1 min
7. Query RAG with "细胞膜的物质转运方式有哪些？"
8. Try chat with "请介绍整合结果"

**Do NOT do these (will fail or waste time):**
- Do NOT try to build KG for all 7 books (too slow, burns API quota)
- Do NOT try to upload via curl (Chinese filename encoding broken)
- Do NOT restart the backend mid-demo (lose all in-memory state)
- Do NOT expect teacher dialogue to modify decisions (never tested with real data)

**If backend crashes/restarts**, you must rerun steps 3-7 above. There is no auto-restore from disk.

---

## Key Tech Notes

- **LLM**: qwen3.6-flash via DashScope API, free tier, key in `.env`
- **Embedding**: text-embedding-v3 (DashScope), batch size max 10
- **FAISS**: NOT installed, using sklearn cosine_similarity instead
- **Token budget**: ~213K used out of 1M free quota. Enough for ~4 more full pipeline runs.
- **Backend CWD must be `src/`**: `cd d:/project/Hack_quick/src && python -m uvicorn backend.main:app ...`
