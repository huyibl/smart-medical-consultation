// 只读模板。参数绑定，禁止拼接用户原句。
// Label / Type 来自 2026-08-22 实测，见 docs/KG_SCHEMA.md

// 导诊：标准症状名 → 疾病 → 科室
// $symptom_names: list<string>
MATCH (s:症状)
WHERE s.名称 IN $symptom_names
MATCH (d:疾病)-[:症状]->(s)
OPTIONAL MATCH (d)-[:所属科室]->(dep)
RETURN s.名称 AS symptom,
       d.名称 AS disease,
       labels(dep) AS dept_labels,
       dep.名称 AS department
LIMIT 20;

// 科普：疾病 → 常用/好评药品（生成层不得写成处方）
// $disease_name: string
MATCH (d:疾病 {名称: $disease_name})
OPTIONAL MATCH (d)-[:常用药品|好评药品]->(drug:药物)
RETURN d.名称 AS disease, collect(DISTINCT drug.名称) AS drugs
LIMIT 1;

// 就诊准备：疾病 → 检查
// $disease_name: string
MATCH (d:疾病 {名称: $disease_name})
OPTIONAL MATCH (d)-[:诊断检查]->(c:检查手段)
RETURN d.名称 AS disease, collect(DISTINCT c.名称) AS checks
LIMIT 1;
