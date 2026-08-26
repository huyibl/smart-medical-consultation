# 智慧问诊 2.0（Smart Medical Consultation）

面向大众的**就医导诊 / 就诊准备 / 医学科普 / 急诊拦截**助手：先检索公开知识图谱与 FAQ，再生成可溯源、受规则约束的回答。

**不能替代执业医师。不做诊断、不开药、不调剂量。** 知识来自 OpenKG「面向家庭常见疾病的知识图谱」（东南大学，[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)），**不是某家医院的号源或诊疗依据**。

当前版本：**2.0.0**（LangGraph 分叉检索 + FastAPI SSE + Vue 对话页）。

---

## 项目定位

| | |
|---|---|
| 目标用户 | 有症状想知道挂哪科、就诊前准备什么、想看疾病 / 检查 / 药品的说明书级介绍 |
| 能做 | 建议科室、就诊准备、科普复述、药品通用说明、红旗症状拦截 |
| 不能做 | 确诊、处方、剂量方案、把化验单当诊断、急救操作指挥 |
| 检索原则 | 准确性优先；空检索则声明依据不足，禁止模型脑补 |
| 代码许可证 | [待补充]（图谱数据为 CC BY-SA 4.0，见 [docs/DATA_ATTRIBUTION.md](docs/DATA_ATTRIBUTION.md)） |

产品边界详见 [docs/PRD.md](docs/PRD.md)。

---

## 核心功能

- **急诊短路**：红旗 / 自伤走规则拦截，不检索、不生成诊疗建议。
- **意图分叉**：`triage` / `visit_prep` / `knowledge` / `medication_info` / `chitchat` / `refuse`；急诊与拒答不走检索。
- **导诊检索**：问句别名 + 图谱名词最长匹配 → 只读 Cypher（症状精确、疾病先精确后模糊）；向量命中不得污染实体链接。
- **科普 / 就诊准备**：图谱 + 过滤后的向量混合检索。
- **药品说明**：Cypher 查药名 + 向量查说明；开药 / 剂量仍拒答。
- **安全改写**：禁句、免责声明、急诊文案兜底。
- **对话页**：Vue 3 + Element Plus；同源托管；历史侧栏、来源可点开、意图 / 科室 / 耗时。
- **会话**：默认 SQLite（`data/sessions.db`），重启不丢；近 12 轮作上下文。

流水线（LangGraph）：

```text
emergency_gate → intent → 分叉检索
  ├─ triage        → retrieve_triage
  ├─ visit_prep / knowledge → retrieve_hybrid
  ├─ medication_info → retrieve_med
  └─ chitchat / refuse → 不检索
→ dept_or_med_or_knowledge → fuse_stream → safety_rewrite
```

---

## 技术栈

从 `requirements.txt`、`frontend/package.json` 提取（版本为下限）。

### 后端（Python 3.12，见 CI）

| 依赖 | 用途 |
|---|---|
| FastAPI ≥ 0.115、Uvicorn ≥ 0.32 | HTTP API、SSE、同源静态页 |
| LangGraph ≥ 0.2.50 | 多节点工作流 |
| neo4j ≥ 5.26 | 只读知识图谱 |
| chromadb ≥ 0.5.23 | 默认向量库 |
| numpy ≥ 1.26 | `VECTOR_BACKEND=faiss` 时的余弦检索（**不是** Facebook `faiss` 包） |
| dashscope ≥ 1.20 | 通义对话 / 嵌入（OpenAI 兼容口） |
| pydantic / pydantic-settings ≥ 2 | 配置与请求模型 |
| PyYAML、python-dotenv | YAML 与 `.env` |
| httpx ≥ 0.27 | HTTP 客户端 |
| pytest ≥ 8.3 | 单测 |

标准库 SQLite 持久化会话，无独立 ORM 依赖。

### 前端

| 依赖 | 用途 |
|---|---|
| Vue 3.5 | 对话 UI |
| Element Plus 2.8、@element-plus/icons-vue | 组件与图标 |
| Vite 6、@vitejs/plugin-vue 5 | 构建（开发依赖） |

Node 最低版本：[待补充]（Vite 6 通常需要 Node 18+；前端未纳入 CI）。

### 数据与可选基础设施

| 组件 | 状态 |
|---|---|
| Neo4j 5.x | 运行时必需（本机已导入图谱时不要再起空库） |
| Redis / MySQL | `.env` 与 compose profile **已预留，会话代码未接线**，仍用 SQLite |
| LangSmith | 可选追踪；无 Key 则关闭 |

---

## 快速开始

本机已有 Neo4j 并导入 OpenKG 时，**不要**再 `docker compose up` 起空库（会占 7687）。

### 1. 环境

```bash
cd smart-medical-consultation
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：至少填写 `NEO4J_PASSWORD`。有 DashScope 则填 `DASHSCOPE_API_KEY` / `CHAT_API_KEY`。

无嵌入 Key 时自动走 `dummy` 向量，FAQ 别名仍能让「头疼」打到「头痛」。有 Key 后把 `EMBEDDING_PROVIDER` 设为 `dashscope` 或 `local`（BGE-M3）再重新 ingest。若维度从 64 换成 1024，入库会自动重建集合。

### 2. 数据层与问答 CLI

```bash
python main.py probe              # 头痛症状 + 导诊路径 + 边方向
python main.py ingest             # FAQ + 图谱文本入向量库（连不上库则仅 FAQ）
python main.py ingest --faq-only  # 只入库手写 FAQ
python main.py search 头疼        # 验收：命中含「头痛」的片段
python main.py ask 最近头疼该挂哪科
```

### 3. 对话页 + API

```bash
cd frontend
npm install
npm run build
cd ..
python main.py serve
```

浏览器打开 `http://127.0.0.1:8000/`。右上角设置里的 Key 默认 `dev-key`（对应 `API_KEYS`）。

开发前端：`cd frontend && npm run dev`（Vite 把 `/v1` 代理到 8000）。

### 4. 评测

```bash
python -m eval.gold               # 金标格式（53 条）
python -m eval.gate               # 急诊 / 拒答 / 禁句硬规则
python -m eval.retrieve           # 导诊科室 hit@1 / @3
python -m pytest -q
```

### 5. Docker（可选）

默认 compose **只起 API**，通过 `host.docker.internal` 连本机 Neo4j。

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Windows 可用 `scripts\compose-up.ps1`。需要**空库** Neo4j / Redis / MySQL 时加 `--profile neo4j` 等；空库会与本机已有 7687 冲突。

---

## API 文档

鉴权：请求头 `X-API-Key` 或 `Authorization: Bearer <key>`。无 Key → **401**；超限 → **429**。  
`GET /health`、`GET /docs`（OpenAPI）、`GET /redoc` **不要求** Key。

启动后也可打开 `http://127.0.0.1:8000/docs`。

### `GET /health`

```json
{"status": "ok", "service": "smc", "version": "2.0.0"}
```

### `POST /v1/chat`

`Content-Type: application/json`，响应 `text/event-stream`。

请求：

```json
{
  "query": "最近头痛头晕该挂哪科",
  "conversation_id": "可选，续聊时传入",
  "history": [{"role": "user", "content": "..."}]
}
```

`query` 长度 1–2000。`conversation_id` 非法 → **400**。

curl（Windows `cmd`）：

```bat
curl -N -H "X-API-Key: dev-key" -H "Content-Type: application/json" ^
  -d "{\"query\":\"最近头疼该挂哪科\"}" http://127.0.0.1:8000/v1/chat
```

SSE 每条 `data:` 为一行 JSON，`type` 仅下列值：

| type | 何时 | payload |
|---|---|---|
| `trace` | 节点开始 / 结束 | `{node, status, elapsed_ms?}` |
| `token` | 正文片段 | `{text}` |
| `sources` | 检索完成或结束前 | `{items: [{source_id, kind, title}]}` |
| `safety` | 安全层结论 | `{blocked, rule_ids, emergency}` |
| `done` | 结束 | `{intent, department_candidates, request_id, elapsed_ms, conversation_id}` |
| `error` | 失败 | `{code, message}` |

当前实现会先推 `trace/started`，**整段 `ask()` 算完后再推 token**（不是逐 token 生成）。

### `GET /v1/conversations?limit=50`

```json
{"items": [{"conversation_id": "...", "updated_at": "...", "preview": "..."}]}
```

### `GET /v1/conversations/{conversation_id}`

```json
{
  "conversation_id": "...",
  "messages": [
    {
      "role": "user|assistant",
      "content": "...",
      "request_id": "...",
      "intent": "...",
      "sources": [],
      "department_candidates": [],
      "elapsed_ms": 0
    }
  ]
}
```

会话不存在 → **404**。

字段约定以 [docs/CONTRACTS.md](docs/CONTRACTS.md) 为准。

---

## 配置说明

复制 `.env.example` 为 `.env`。改键重启进程即生效，不必改业务代码。**不要提交 `.env`。**

| 键 | 含义 |
|---|---|
| `CHAT_BASE_URL` / `CHAT_API_KEY` / `CHAT_MODEL` | 主问答（默认 DashScope 兼容口 + `qwen-plus`） |
| `EXTRACT_BASE_URL` / `EXTRACT_API_KEY` / `EXTRACT_MODEL` | 离线抽取，**配置已预留，在线路径未接线** |
| `DASHSCOPE_API_KEY` / `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | 嵌入：`dashscope` \| `local` \| `dummy` |
| `LOCAL_EMBEDDING_MODEL` | 本地嵌入，默认 `BAAI/bge-m3` |
| `VECTOR_BACKEND` | `chroma`（默认）或 `faiss`（numpy 实现） |
| `CHROMA_PERSIST_DIR` / `CHROMA_COLLECTION_NAME` | Chroma 路径与集合名 |
| `INGEST_DISEASE_LIMIT` | ingest 时疾病文本条数上限 |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | 图谱只读连接 |
| `API_KEYS` | 逗号分隔多个 Key |
| `RATE_LIMIT_PER_MINUTE` | 默认 60 |
| `API_HOST` / `API_PORT` | 默认 `127.0.0.1:8000` |
| `SQLITE_PATH` / `HISTORY_MAX_TURNS` | 会话库与上下文轮数 |
| `REDIS_URL` / `MYSQL_DSN` | 会话升级用，**可空，未接线** |
| `LOG_LEVEL` / `LOG_JSON` | 文本或 JSON 审计日志 |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | 可选追踪 |

图谱只读。写 Cypher 会被客户端拒绝。中文 Label：`疾病` `症状` `二级科室` `药物` …；属性键是 **`名称` 不是 `name`**。对照 [docs/KG_SCHEMA.md](docs/KG_SCHEMA.md)。

---

## 仓库结构（节选）

```text
main.py                 CLI 入口
src/smc/                工作流、检索、API、会话
config/                 意图、图谱 schema、安全规则
frontend/               Vue 对话页
data/faq/               手写 FAQ 与别名
docs/                   PRD / 契约 / 安全 / 署名
eval/                   金标与门禁
deploy/                 Dockerfile、compose
```

`data/indexes/`、`frontend/dist/`、`.env` 已 gitignore，需本地生成。

---

## 文档索引

| 文件 | 内容 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 能答 / 必拒 |
| [docs/SAFETY_POLICY.md](docs/SAFETY_POLICY.md) | 急诊与禁句 |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | 意图、SSE、配置键 |
| [docs/KG_SCHEMA.md](docs/KG_SCHEMA.md) | Neo4j 实测 Label / 关系 |
| [docs/DATA_ATTRIBUTION.md](docs/DATA_ATTRIBUTION.md) | OpenKG 署名 |
| [eval/gold_v0.json](eval/gold_v0.json) | 53 条金标 |
| [eval/README.md](eval/README.md) | 评测命令 |

CI（`.github/workflows/eval.yml`）：金标格式、硬规则门禁、pytest、FAQ ingest + 导诊召回下限。
