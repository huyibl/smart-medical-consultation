# 工程契约 v0

状态：**P0 冻结**。智能体、API、前端、评测必须遵守本节字段名。改字段先改本文。

## 1. 意图枚举

与 [config/intents.yaml](../config/intents.yaml) 保持一致。

| id | 说明 | 是否必须检索 | 默认声明 |
|---|---|---|---|
| `emergency` | 红旗/自伤，规则短路 | 否 | 急诊文案 |
| `triage` | 导诊 | 是 | 是 |
| `visit_prep` | 就诊准备 | 是 | 是 |
| `knowledge` | 医学科普（疾病/检查） | 是（混合检索） | 是 |
| `medication_info` | 药品说明书（非处方） | 是（Cypher 药 + 向量说明） | 是 + 遵医嘱 |
| `chitchat` | 闲聊 | 否 | 短声明 |
| `refuse` | 拒答（诊断/处方/剂量/检查单当诊断） | 否 | 是 |

路由顺序：**急诊规则 → 拒答规则 → 闲聊规则 →（模糊才）LLM 分类**。  
导诊：别名链接 + 模板 Cypher（症状→科室），向量不参与科室排名。检索为空则依据不足，禁止 LLM 脑补。

## 2. 金标条目

文件：[eval/gold_v0.json](../eval/gold_v0.json)  
校验：`python -m eval.gold`

每条必填：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | `g001` 形式，唯一 |
| `query` | string | 用户原话 |
| `intent` | string | 上一节枚举之一 |
| `expect_dept_or_refuse` | string | 科室名，或 `refuse` / `emergency_referral` / `chitchat` |
| `must_cite` | bool | 上线后是否必须带来源 |
| `emergency` | bool | 是否必须走急诊拦截 |

选填：`alt_depts`、`aliases`、`must_disclaimer`、`must_contain`、`banned_phrases`、`notes`、`tags`。

`emergency=true` 时：`intent` 必须是 `emergency`，`expect_dept_or_refuse` 必须是 `emergency_referral`。

## 3. Agent 状态（LangGraph）

实现时使用下列键（可增不可改义）：

```text
request_id: str
query: str
messages: list[{role, content}]
intent: str | None
emergency: bool
entities: {symptoms: [], diseases: [], drugs: []}
retrieval: {vector: [], graph: []}
sources: list[{source_id, kind, title, snippet}]
department_candidates: list[str]
generator_output: str
safety: {blocked: bool, rewritten: bool, rule_ids: []}
answer: str
trace: list[{node, started_ms, elapsed_ms, input_preview, output_preview}]
```

节点顺序（板块二）：

`emergency_gate` → `intent` → 按意图分叉检索 → `fuse_stream` → `safety_rewrite`

- 导诊：`retrieve_triage`（实体链接 + Cypher）
- 就诊准备 / 科普：`retrieve_hybrid`
- 药品说明：`retrieve_med`
- 闲聊 / 拒答：不检索
- 急诊：直接 `safety_rewrite`

## 4. SSE 事件（`POST /v1/chat`）

`Content-Type: text/event-stream`。每条 `data:` 为一行 JSON，`type` 如下：

| type | 何时 | payload |
|---|---|---|
| `trace` | 节点开始/结束 | `{node, status, elapsed_ms?}` |
| `token` | 流式正文 | `{text}` |
| `sources` | 检索完成或结束前 | `{items: [{source_id, kind, title}]}` |
| `safety` | 安全层结论 | `{blocked, rule_ids, emergency}` |
| `done` | 结束 | `{intent, department_candidates, request_id, elapsed_ms, conversation_id}` |
| `error` | 失败 | `{code, message}` |

禁止用未登记的 `type` 作为前端主路径。

## 5. HTTP 请求（板块三）

```json
{
  "query": "最近头痛头晕该挂哪科",
  "conversation_id": "可选",
  "history": [{"role": "user", "content": "..."}]
}
```

鉴权：请求头 `X-API-Key` 或 `Authorization: Bearer`。无 Key → 401；超限 → 429。

`done.conversation_id` 用于续聊与拉历史。历史接口（须同样带 Key）：

- `GET /v1/conversations` → `{items: [{conversation_id, updated_at, preview}]}`
- `GET /v1/conversations/{conversation_id}` → `{conversation_id, messages: [{role, content, request_id?, intent?, sources?, department_candidates?, elapsed_ms?}]}`

历史默认 SQLite（`SQLITE_PATH`），近 12 轮用于上下文，全量落盘含证据 ID。重启进程后记录仍在。

## 6. 配置键（`.env` / YAML）

| 键 | 含义 |
|---|---|
| `CHAT_BASE_URL` / `CHAT_API_KEY` / `CHAT_MODEL` | 主问答 |
| `EXTRACT_BASE_URL` / `EXTRACT_MODEL` | 离线抽取（后置） |
| `EMBEDDING_MODEL` | 默认 `BAAI/bge-m3` |
| `VECTOR_BACKEND` | `faiss` 或 `chroma` |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | 图谱只读 |
| `API_KEYS` / `RATE_LIMIT_PER_MINUTE` | HTTP 鉴权与限流 |
| `SQLITE_PATH` / `HISTORY_MAX_TURNS` | 会话 SQLite；Redis/MySQL 后接 |
| `REDIS_URL` / `MYSQL_DSN` | 会话升级用，可空 |
| `LOG_LEVEL` / `LOG_JSON` | 文本或 JSON 审计日志 |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | 可选追踪，无 Key 关闭 |

改这些键不得要求改业务代码。
