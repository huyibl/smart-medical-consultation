"""OpenAI 兼容 Chat。无 Key 返回空串，由模板兜底。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from config.settings import get_settings


def chat_complete(messages: list[dict[str, str]], max_tokens: int = 400) -> str:
    s = get_settings()
    key = s.chat_api_key
    if not key:
        return ""
    body = json.dumps(
        {
            "model": s.chat_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    url = s.chat_base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "").strip()
