# Claude Handoff

Last session: 2026-05-10 (v3: demo polish — decision sources, chapter progress bar, card styling)

## Scope

- Frontend code (src/frontend/)
- Documentation (docs/, report/, README.md)
- Do NOT touch backend code

## This Session Completed

### Frontend (App.jsx 重写)

- 用 Ant Design 组件替换原生 HTML（Card, Tabs, List, Tag, Spin, Statistic 等）
- 用 ECharts 力导向图替换 DOM 节点网格（支持缩放、拖拽、点击节点查看详情）
- 添加 pipeline 状态面板（底部显示解析/建图/整合/RAG 状态）
- 添加"批量构建图谱"按钮（调用 `/api/pipeline/kg/build-all`）
- 整合面板改为 Statistic 卡片展示压缩比/节点数/决策数
- RAG 问答添加 citation 卡片展示
- Loading 改为 Spin 组件 + 半透明遮罩
- API client 全面重写，统一错误处理
- 补了章节覆盖视图（选教材显示章节列表、页码、字数、KG 状态）
- 报告页升级为 Markdown 摘要 + 统计卡片
- 局部 Loading 替代全屏遮罩
- 整合决策 accept/reject 按钮
- 教材列表删除按钮

### 文档

- 创建 README.md（项目简介、启动方式、API 接口、项目结构）
- 填充真实数据到 report/整合报告.md
- 创建 docs/current_status.md（事实快照）
- 创建 docs/Codex_handoff.md（后端交接文档）
- 创建 docs/Claude_handoff.md（本文件）

### 构建

- `npm run build` 通过，无编译错误

## 当前前端状态

- `src/frontend/src/App.jsx` — 单文件，使用 Ant Design + ECharts
- `src/frontend/src/api/client.js` — 完整 API 客户端
- `src/frontend/src/App.css` — 简化后样式
- `dist/` — 已重新编译

## 前端仍存在的问题

1. 图谱节点过多时 ECharts force 布局可能变慢（>500 节点时需考虑虚拟化）
2. chunk size 警告（不影响运行）
3. 中文教材标题在 DB 中存储为乱码（后端问题，非前端）
4. 整合 stale=True 会持续影响章节列表和决策展示的准确性（等后端修 KG 章节范围一致性）
5. 决策详情目前是列表堆文本，未来可做抽屉式详情页
6. 删除教材前缺确认弹窗
7. 图谱大节点数时无默认筛选/分层显示

## 待 Codex 补充的后端 API

1. ~~`GET /api/kg/{book_id}/chapters`~~ — **已完成** (2026-05-10)
2. ~~`DELETE /api/textbooks/{book_id}`~~ — **已完成** (2026-05-10)
3. ~~`GET /api/integration/decisions/{id}`~~ — **已完成** (2026-05-10)
4. ~~`POST /api/integration/decisions/{id}/accept`~~ — **已完成** (2026-05-10)
5. ~~`POST /api/integration/decisions/{id}/reject`~~ — **已完成** (2026-05-10)
6. `GET /api/kg/{book_id}/chapters/{chapter_id}` — 获取单章内容（未实现）
