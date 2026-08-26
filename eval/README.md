# 评测与门禁

| 命令 | 作用 | CI |
|---|---|---|
| `python -m eval.gold` | 金标字段/覆盖 | 是 |
| `python -m eval.gate` | 急诊 100%、拒答、声明/禁句夹具 | 是（失败即红） |
| `python -m eval.retrieve` | 导诊科室 hit@1 / hit@3 | CI 用 dummy+FAQ，`--min-dept-recall 0.4` |
| `eval/ragas_stub.py` | faithfulness 等 | 板块二之后 |

报告写到 `eval/reports/gate_YYYY-MM-DD.json`、`retrieve_YYYY-MM-DD.json`（不入库）。
