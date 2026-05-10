# Claude Handoff

Last session: 2026-05-10

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
2. 报告 Tab 只展示了 stats JSON，未渲染完整 Markdown 报告
3. 无章节列表展示（需要后端 `GET /api/kg/{book_id}/chapters`）
4. 中文教材标题在 DB 中存储为乱码（后端问题，非前端）
5. 无删除教材功能（需要后端 DELETE API）
6. 整合决策无 accept/reject 按钮（需要后端 API）

## 待 Codex 补充的后端 API

1. `GET /api/kg/{book_id}/chapters` — 列出已解析教材的章节列表
2. `DELETE /api/textbooks/{book_id}` — 删除教材（含清理文件）
3. `GET /api/integration/decisions/{id}` — 单条决策详情
4. `POST /api/integration/decisions/{id}/accept` — 接受决策
5. `POST /api/integration/decisions/{id}/reject` — 拒绝决策
6. `GET /api/kg/{book_id}/chapters/{chapter_id}` — 获取单章内容
