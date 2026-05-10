# Current Status

Last updated: 2026-05-10 by Claude

## Data State

| Metric | Value |
|---|---|
| Registered textbooks | 7 |
| Parsed textbooks | 7 |
| KG built (partial) | 7 (all partial, 2 chapters each) |
| KG built (complete) | 0 |
| Integration | 7 books, 1288→1275 nodes, 10 merge decisions |
| RAG | 7 books, 794 chunks, persisted on disk |
| Compression ratio | 99.7% (limited overlap with partial data) |

## Book-level Detail

| Book | Title | Chapters parsed | KG nodes | KG edges | KG chapters |
|---|---|---|---|---|---|
| book_01 | 局部解剖学 | 9 | 284 | 61 | 2/9 |
| book_02 | 组织学与胚胎学 | 28 | 68 | 19 | 2/28 |
| book_03 | 生理学 | 13 | 212 | 184 | 2/13 |
| book_04 | 医学微生物学 | 47 | 43 | 22 | 2/47 |
| book_05 | 病理学 | 20 | 113 | 112 | 2/20 |
| book_06 | 传染病学 | 12 | 594 | 28 | 2/12 |
| book_07 | 病理生理学 | 20 | 81 | 67 | 2/20 |

**Note**: book_01 元数据显示 3/9 chapters（实际数据为 2 章抽取结果，元数据 enrichment 可能多计了 1 个匹配的 chapter_id）。book_06 的 594 节点偏多，可能是章节内容过长或抽取粒度过细。

## Pipeline Status

| Stage | Status | Notes |
|---|---|---|
| Upload | OK | 7 books, system-assigned book_id |
| Parse | OK | All 7 parsed with new parser |
| KG Build | Partial 2ch | All 7 have 2 chapters |
| Integration | OK | 7 books, stale=False |
| RAG Index | OK | 7 books, 794 chunks, stale=False |
| Teacher Chat | Untested | Needs real integration data |
| Report | Needs update | Report has old 620-node data |

## Current Blockers

- Report needs update (still shows old 620-node data, now 1288→1275)
- book_06 594 nodes suspicious (likely over-extraction in chapter 2)
- Teacher chat not tested with current integration data

## Coordination Rules

1. Claude does NOT edit backend code
2. Codex does NOT edit frontend code
3. Both read this file before starting work
4. Update this file when you finish a session
5. If you discover a problem in the other person's domain, write it here instead of fixing it yourself
