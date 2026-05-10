# EduGraph Agent

多教材知识整合智能体 — 基于 GraphRAG 的教材知识图谱构建、跨教材去重、RAG 引用问答与教师反馈工作台。

## 项目简介

EduGraph Agent 面向多本医学教材的知识整合场景。系统从教材 PDF 中自动抽取知识点和关系、构建知识图谱、跨教材识别重复和互补知识点、生成整合决策，并提供基于原文 chunk 的带引用 RAG 问答。

**技术栈**：React + Vite + Ant Design + ECharts | FastAPI + SQLAlchemy + SQLite | DashScope qwen3.6-flash + text-embedding-v3

## 快速启动

### Docker 一键部署（推荐）

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
docker-compose up -d
```

前端访问 `http://localhost:3000`，后端 API `http://localhost:8000`。

### 手动启动

### 环境要求

- Python 3.13+
- Node.js 24+
- 阿里百炼 DashScope API Key

### 安装依赖

```bash
# 后端
pip install -r requirements.txt

# 前端
cd src/frontend
npm install
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

### 启动服务

```bash
# 方式一：脚本启动（推荐）
chmod +x start.sh
./start.sh

# 方式二：手动启动
# 后端
cd src
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 前端（新终端）
cd src/frontend
npm run dev
```

前端默认运行在 `http://localhost:3000`，自动代理 `/api` 到后端 8000 端口。

## 功能模块

| 模块 | 说明 |
|---|---|
| 教材上传与解析 | 支持 PDF / Markdown / TXT，PyMuPDF 解析 + TOC 书签识别 |
| 知识点抽取 | LLM 逐章节抽取知识点和关系，输出结构化 JSON |
| 知识图谱可视化 | ECharts 力导向图，支持缩放、拖拽、点击节点查看详情 |
| 跨教材整合 | embedding 召回 + LLM 复核，生成 merge / keep / remove 决策 |
| RAG 引用问答 | 基于原文 chunk 的检索增强问答，每个回答附带教材/章节/页码引用 |
| 教师反馈 | 自然语言修改整合决策（恢复/拆分/合并） |
| 整合报告 | 自动生成整合统计、典型案例和教学完整性说明 |

## API 接口

### 教材管理
- `POST /api/textbooks/upload` — 上传教材文件
- `GET /api/textbooks` — 列表
- `POST /api/textbooks/{id}/parse` — 解析单本
- `POST /api/textbooks/parse-all` — 解析全部
- `DELETE /api/textbooks/{id}` — 删除教材

### 知识图谱
- `POST /api/kg/build/{book_id}` — 构建单本图谱
- `GET /api/kg/{book_id}` — 获取单本图谱
- `GET /api/kg/{book_id}/chapters` — 章节覆盖列表
- `GET /api/kg/merged` — 获取整合图谱

### 跨教材整合
- `POST /api/integration/run` — 执行整合
- `GET /api/integration/decisions` — 决策列表
- `GET /api/integration/decisions/{id}` — 决策详情
- `POST /api/integration/decisions/{id}/accept` — 接受决策
- `POST /api/integration/decisions/{id}/reject` — 驳回决策
- `GET /api/integration/stats` — 统计数据

### RAG 问答
- `POST /api/rag/index` — 构建索引
- `POST /api/rag/query` — 查询问答
- `GET /api/rag/status` — 索引状态

### 教师对话
- `POST /api/chat` — 发送消息
- `GET /api/chat/history/{session_id}` — 对话历史

### 报告
- `GET /api/report` — 获取整合报告

### Pipeline
- `GET /api/pipeline/status` — 全局状态（含 stale 检测）
- `POST /api/pipeline/kg/build-all` — 批量构建图谱

## 项目结构

```
src/
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 配置管理
│   ├── models.py        # Pydantic 数据模型
│   ├── database.py      # SQLAlchemy 数据库
│   ├── state.py         # 运行时状态管理
│   ├── llm.py           # LLM / Embedding 封装
│   ├── routers/         # API 路由
│   ├── services/        # 业务逻辑
│   └── prompts/         # LLM Prompt 模板
├── frontend/
│   └── src/
│       ├── App.jsx      # 主页面（图表谱+功能面板）
│       └── api/client.js # API 客户端
docs/                    # 文档
report/                  # 整合报告
textbooks/               # 教材 PDF（不提交 Git）
```

## 文档

- [docs/需求分析.md](docs/需求分析.md) — 需求分解与验收标准
- [docs/系统设计.md](docs/系统设计.md) — 架构设计与 API 接口
- [docs/Agent 架构说明.md](docs/Agent%20架构说明.md) — Agent 架构与设计决策
- [docs/演示脚本.md](docs/演示脚本.md) — 演示流程与备用路径
- [docs/current_status.md](docs/current_status.md) — 当前状态快照
- [report/整合报告.md](report/整合报告.md) — 整合结果报告
