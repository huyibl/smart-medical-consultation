"""板块一命令：probe / ingest / search。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def cmd_probe(_: argparse.Namespace) -> int:
    from smc.tools.neo4j_client import neo4j_client, probe

    with neo4j_client() as client:
        data = probe(client)
    from smc.rag.kg_names import refresh_name_cache

    data["kg_names"] = refresh_name_cache()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    triage = data.get("triage") or []
    if not data.get("headache_symptoms") and not triage:
        print("WARN: 未查到「头痛」症状或导诊路径，请核对关系方向", file=sys.stderr)
        return 2
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from config.settings import get_settings
    from smc.rag.ingest import chunks_from_diseases, chunks_from_headache_bundle, ingest

    extra: list[dict] = []
    settings = get_settings()
    if not args.faq_only:
        try:
            from smc.tools.neo4j_client import neo4j_client, export_diseases, export_headache_bundle

            with neo4j_client(settings) as client:
                extra.extend(chunks_from_headache_bundle(export_headache_bundle(client)))
                extra.extend(
                    chunks_from_diseases(export_diseases(client, settings.ingest_disease_limit))
                )
            print(f"从 Neo4j 导出 {len(extra)} 条图谱文本")
        except Exception as exc:
            print(f"Neo4j 导出跳过（仅 FAQ）：{exc}", file=sys.stderr)
    stats = ingest(settings, extra_chunks=extra)
    if stats.get("rebuilt"):
        print("已清空旧索引后重新入库（避免残留噪声 chunk）")
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from smc.rag.retriever import headache_alias_ok, search

    hits = search(args.query)
    print(json.dumps(hits, ensure_ascii=False, indent=2))
    if "头疼" in args.query or "头痛" in args.query:
        ok = headache_alias_ok(hits)
        print("验收头疼→头痛:", "PASS" if ok else "FAIL")
        return 0 if ok else 3
    return 0 if hits else 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="智慧问诊数据层")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="探测 Neo4j 规模与头痛导诊路径").set_defaults(func=cmd_probe)
    ing = sub.add_parser("ingest", help="FAQ + 可选图谱文本入向量库")
    ing.add_argument("--faq-only", action="store_true")
    ing.set_defaults(func=cmd_ingest)
    se = sub.add_parser("search", help="检索")
    se.add_argument("query")
    se.set_defaults(func=cmd_search)

    def cmd_gold(_: argparse.Namespace) -> int:
        from eval.gold import main as gold_main

        return gold_main()

    def cmd_gate(_: argparse.Namespace) -> int:
        from eval.gate import main as gate_main

        return gate_main()

    def cmd_eval_retrieve(args: argparse.Namespace) -> int:
        from eval.retrieve import main as retrieve_main

        extra = []
        if args.min_dept_recall is not None:
            extra.extend(["--min-dept-recall", str(args.min_dept_recall)])
        return retrieve_main(extra or None)

    sub.add_parser("gold", help="校验金标格式").set_defaults(func=cmd_gold)
    sub.add_parser("gate", help="硬规则门禁").set_defaults(func=cmd_gate)
    ev = sub.add_parser("eval-retrieve", help="导诊检索评测并写报告")
    ev.add_argument("--min-dept-recall", type=float, default=0.0)
    ev.set_defaults(func=cmd_eval_retrieve)

    def cmd_ask(args: argparse.Namespace) -> int:
        from smc.services.ask import ask

        result = ask(args.query)
        print(result.get("answer") or "")
        print("---")
        print(
            json.dumps(
                {
                    "intent": result.get("intent"),
                    "emergency": result.get("emergency"),
                    "departments": result.get("department_candidates"),
                    "sources": [s.get("source_id") for s in (result.get("sources") or [])],
                    "safety": result.get("safety"),
                    "trace": [t.get("node") for t in (result.get("trace") or [])],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    ak = sub.add_parser("ask", help="多节点问答（板块二）")
    ak.add_argument("query")
    ak.set_defaults(func=cmd_ask)

    def cmd_serve(args: argparse.Namespace) -> int:
        import uvicorn
        from config.settings import get_settings
        from smc.api.app import create_app

        settings = get_settings()
        from smc.observability.log import setup_logging, setup_tracing

        setup_logging(settings)
        setup_tracing(settings)
        host = args.host or settings.api_host
        port = int(args.port or settings.api_port)
        try:
            from smc.rag.kg_names import refresh_name_cache

            names = refresh_name_cache()
            print(f"图谱名词 疾病={names.get('diseases')} 症状={names.get('symptoms')}")
        except Exception as exc:
            print(f"图谱名词缓存跳过：{exc}")
        print(f"对话页  http://{host}:{port}/")
        print(f"POST /v1/chat  SSE  http://{host}:{port}")
        print("鉴权头 X-API-Key 或 Authorization: Bearer（见 API_KEYS）")
        if not (settings.frontend_dist / "index.html").is_file():
            print("未找到 frontend/dist，先执行: cd frontend && npm install && npm run build")
        uvicorn.run(create_app(settings), host=host, port=port)
        return 0

    sv = sub.add_parser("serve", help="启动 HTTP API（板块三）")
    sv.add_argument("--host", default=None)
    sv.add_argument("--port", default=None)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
