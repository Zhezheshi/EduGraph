# Current Status

Last updated: 2026-05-10 by Claude (v4: full audit — real data from running backend)

## Data State

| Metric | Value |
|---|---|
| Registered textbooks | 7 |
| Parsed textbooks | 7 |
| KG built (partial) | 7 (all partial, 2-3 chapters each) |
| KG built (complete) | 0 |
| Integration | stale=True, 602 nodes, 12 decisions, compression 99.8% |
| RAG | stale=True, 210 chunks |
| Token usage | prompt=60137, completion=29867, total=90004 |

## Book-level Detail

| Book | Title | KG chapters | KG nodes | KG edges |
|---|---|---|---|---|
| book_01 | 局部解剖学 | 3/9 | 284 | 61 |
| book_02 | 组织学与胚胎学 | 2/28 | 68 | 19 |
| book_03 | 生理学 | 3/13 | 345 | 301 |
| book_04 | 医学微生物学 | 3/47 | 92 | 22 |
| book_05 | 病理学 | 2/20 | 113 | 112 |
| book_06 | 传染病学 | 2/12 | 594 | 28 |
| book_07 | 病理生理学 | 2/20 | 81 | 67 |

## Pipeline Status

| Stage | Status | Notes |
|---|---|---|
| Upload | OK | 7 books |
| Parse | OK | All 7 parsed |
| KG Build | Partial | 7 books, 2-3 chapters each |
| Integration | stale=True | 602 nodes, 12 decisions (LLM alignment slow, may timeout) |
| RAG Index | stale=True | 210 chunks (needs rebuild) |
| Teacher Chat | Untested | actions_taken 始终为空 |
| Report | OK | 5 real merge cases written |

## Frontend Status

| Feature | Status | Notes |
|---|---|---|
| 教材列表 + 删除 | OK | With confirmation modal |
| 章节覆盖视图 | OK | With progress bar |
| 知识图谱 ECharts | OK | Search + textbook filter |
| 整合 Sankey 图 | OK | Before/after comparison |
| 整合决策 accept/reject | OK | With source_textbooks |
| RAG 问答 + 引用 | OK | |
| 报告页 Markdown | OK | 5 real cases |
| 局部 Loading | OK | |
| npm run build | OK | Chunk size warning |

## Backend Changes This Session

- prompts/extraction.py: Added few-shot example (炎症)
- prompts/alignment.py: Added few-shot example (白细胞)
- services/rag_engine.py: Added docstrings + _search_hybrid method (RAG_HYBRID=1)
- services/aligner.py: Added docstring
- services/integrator.py: Added docstring
- services/extractor.py: Added docstring
- services/parser.py: Added parse_docx() for .docx files
- routers/textbooks.py: Added .docx format dispatch
- requirements.txt: Added python-docx==1.1.2
- tests/test_smoke.py: 7 tests, all passing

## Doc Changes This Session

- docs/Agent 架构说明.md: Added 6.5 量化决策依据 + 7.x 防幻觉策略
- report/整合报告.md: 5 real merge cases + teacher feedback test case
- README.md: Docker quick start + new API endpoints
- Docker files: Dockerfile, Dockerfile.frontend, docker-compose.yml, nginx.conf
- start.sh / start.bat scripts
