# 图谱 Schema 对照稿 v0.1

状态：**已按 Neo4j 实测回写。** 在线 Cypher 必须用本文中文 Label / 关系名，禁止再写 `Disease` / `has_symptom`。  
`属于` vs `所属科室` 的方向见第 2.3 节，尚未用样例边抽检，写 tools 前先跑第 4 节「方向确认」。

探查日期：2026-08-22。库内节点合计 **62,196**（与 OpenKG 公开规模一致）。

## 1. 数据源

- 名称：面向家庭常见疾病的知识图谱
- 发布：OpenKG，东南大学
- 许可：CC BY-SA 4.0，见 [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md)
- 机器可读映射：[config/kg_schema.yaml](../config/kg_schema.yaml)
- 模板查询：[kg/templates.cypher](../kg/templates.cypher)

## 2. 实测 Schema

### 2.1 节点

| 逻辑名 | 实测 Label | 数量 | 在线是否使用 | 已证实属性 |
|---|---|---|---|---|
| Disease | `疾病` | 11,871 | 是 | `名称`, `描述`, `病因`, `预防方法`, `治愈概率`, `易得人群`, `治疗时长` |
| Symptom | `症状` | 16,091 | 是 | `名称`（其余键待补） |
| DeptL2 | `二级科室` | 44 | 是（导诊主推荐） | 待补，至少有 `名称` |
| DeptL1 | `一级科室` | 10 | 是（可并列展示） | 待补 |
| Drug | `药物` | 6,017 | 是（仅科普） | 待补 |
| Check | `检查手段` | 5,529 | 是（就诊准备） | 待补 |
| Treatment | `治疗方案` | 544 | 可选 | 待补 |
| Food | `食物` | 364 | 低优先级 | 待补 |
| Recipe | `食谱` | 4,506 | 低优先级 | 待补 |
| Producer | `生产商` | 17,201 | 否 | 待补 |
| Other | `其他` | 19 | 否 | — |

名称属性键是 **`名称`，不是 `name`。**  
疾病长文本在 **`描述` / `病因` / `预防方法`**，向量库优先吃这三列。

科室是两级：金标里的「神经内科」应对 `二级科室`；`一级科室` 仅 10 个，更像内科/外科这类大类。

### 2.2 关系（名称已实测，方向待抽检）

| 逻辑名 | 实测 Type | 推断方向 | 在线 |
|---|---|---|---|
| HAS_SYMPTOM | `症状` | `疾病` → `症状` | 是 |
| BELONGS_TO_DEPT | `所属科室` | `疾病` → `二级科室` 或 `一级科室` | 是 |
| DEPT_PARENT | `属于` | 疑似 `二级科室` → `一级科室` | 是（展示用） |
| COMMON_DRUG | `常用药品` | `疾病` → `药物` | 是（科普） |
| RATED_DRUG | `好评药品` | `疾病` → `药物` | 是（科普） |
| NEED_CHECK | `诊断检查` | `疾病` → `检查手段` | 是 |
| ACOMPANY_WITH | `并发症` | `疾病` → `疾病` | 可选 |
| TREATMENT | `治疗方法` | `疾病` → `治疗方案` | 可选 |
| DO_EAT | `宜吃` | `疾病` → `食物` | 低 |
| NOT_EAT | `忌吃` | `疾病` → `食物` | 低 |
| RECIPE | `推荐食谱` | `疾病` → `食谱` | 低 |
| PRODUCES | `生产药品` | `生产商` → `药物` | 否 |

注意：关系类型 `症状` 与节点 Label `症状` 同名。Cypher 里节点写 `(:症状)`，边写 `-[:症状]->`。

### 2.3 「头痛」查询说明（已跑）

```cypher
MATCH (n)
WHERE any(k IN keys(n) WHERE toString(n[k]) CONTAINS '头痛')
RETURN labels(n), n LIMIT 10;
```

命中的是 **`疾病` 节点**（如「雷诺病」），因为 `描述` / `病因` 正文里出现了「头痛」，**不是**症状节点本身。  
导诊主路径必须改查 `(:症状 {名称: $name})`，不能对全属性做 CONTAINS。

## 3. 模板 Cypher（已换真名）

参数绑定，禁止拼接用户原句。

**症状 → 疾病 → 二级科室（导诊）**

```cypher
MATCH (s:症状)
WHERE s.名称 IN $symptom_names
MATCH (d:疾病)-[:症状]->(s)
OPTIONAL MATCH (d)-[:所属科室]->(dep)
RETURN s.名称 AS symptom, d.名称 AS disease,
       labels(dep) AS dept_labels, dep.名称 AS department
LIMIT 20
```

**疾病 → 药品（只供科普，生成层不得写成处方）**

```cypher
MATCH (d:疾病 {名称: $disease_name})
OPTIONAL MATCH (d)-[:常用药品|好评药品]->(drug:药物)
RETURN d.名称 AS disease, collect(DISTINCT drug.名称) AS drugs
LIMIT 1
```

**口语 → 标准名**：向量 / 别名表，实体链接阈值 0.85。Text2Cypher 默认关闭。

## 4. 写 tools 前再跑这 3 条（确认边方向）

```cypher
MATCH (s:症状)
WHERE s.名称 = '头痛' OR s.名称 CONTAINS '头痛'
RETURN s.名称, labels(s)
LIMIT 10;
```

```cypher
MATCH (d:疾病)-[r:症状]->(s:症状)
WHERE s.名称 CONTAINS '头痛'
OPTIONAL MATCH (d)-[:所属科室]->(dep)
RETURN d.名称, s.名称, labels(dep), dep.名称
LIMIT 20;
```

```cypher
MATCH (a)-[r:属于]->(b)
RETURN labels(a)[0] AS from_label, labels(b)[0] AS to_label, count(*) AS n;
MATCH (a)-[r:所属科室]->(b)
RETURN labels(a)[0] AS from_label, labels(b)[0] AS to_label, count(*) AS n;
```

前两条能出「头痛 → 疾病 → 科室」，导诊模板就算通。第三条用来钉死 `属于` / `所属科室`，结果回来后改 yaml 里的 `direction`。

## 5. 向量库对照

- 嵌入：BGE-M3（可配置）
- 语料：`疾病.描述` / `病因` / `预防方法` + `data/faq/`（含头疼→头痛）
- 验收：查询「头疼」召回含「头痛」的 chunk
- 不要把全库 1.7 万生产商灌进向量索引

## 6. 变更纪律

1. 边方向与第 4 节不一致：先改本文和 `config/kg_schema.yaml`，再改 `src/tools`。
2. 新关系进在线路径：补模板 + 至少 3 条金标。
3. 属性键继续用中文，代码里不要映射成 `name` 再查库。
