const KEY = "smc_api_key";

export function getApiKey() {
  return localStorage.getItem(KEY) || "dev-key";
}

export function setApiKey(value) {
  localStorage.setItem(KEY, (value || "").trim() || "dev-key");
}

function headers() {
  return {
    "Content-Type": "application/json",
    "X-API-Key": getApiKey(),
  };
}

async function readError(res) {
  try {
    const data = await res.json();
    return data.message || data.detail?.message || data.code || res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function listConversations() {
  const res = await fetch("/v1/conversations", { headers: headers() });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getConversation(id) {
  const res = await fetch(`/v1/conversations/${id}`, { headers: headers() });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function streamChat({ query, conversationId, onEvent, signal }) {
  const res = await fetch("/v1/chat", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      query,
      conversation_id: conversationId || undefined,
    }),
    signal,
  });
  if (res.status === 401) throw new Error("API Key 无效，请在右上角设置");
  if (res.status === 429) throw new Error("请求过于频繁，请稍后再试");
  if (!res.ok) throw new Error(await readError(res));
  if (!res.body) throw new Error("响应没有正文");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    buf += decoder.decode(value || new Uint8Array(), { stream: !done });
    buf = consumeSse(buf, onEvent, done);
    if (done) break;
  }
}

export function consumeSse(buf, onEvent, flush = false) {
  const normalized = buf.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = flush ? "" : parts.pop() || "";
  for (const part of parts) {
    if (!part.trim()) continue;
    const line = part.split("\n").find((l) => l.startsWith("data:"));
    if (!line) continue;
    onEvent(JSON.parse(line.slice(5).trim()));
  }
  return rest;
}

export const INTENT_LABEL = {
  emergency: "急诊",
  triage: "导诊",
  visit_prep: "就诊准备",
  knowledge: "医学科普",
  medication_info: "药品说明",
  chitchat: "闲聊",
  refuse: "拒答",
};

export const SUGGESTIONS = [
  "最近头疼该挂哪科",
  "去医院就诊前要带什么",
  "偏头痛和普通头痛有什么区别",
  "阿司匹林一般用在什么情况",
];
