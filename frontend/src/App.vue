<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import HistorySidebar from "./components/HistorySidebar.vue";
import MessageList from "./components/MessageList.vue";
import {
  SUGGESTIONS,
  getApiKey,
  getConversation,
  listConversations,
  setApiKey,
  streamChat,
} from "./api";

const items = ref([]);
const messages = ref([]);
const currentId = ref("");
const draft = ref("");
const sending = ref(false);
const source = ref(null);
const showSource = ref(false);
const showKey = ref(false);
const apiKey = ref(getApiKey());
const mobileNav = ref(false);
const scroller = ref(null);

const empty = computed(() => !messages.value.length && !sending.value);

function hashId() {
  const m = location.hash.match(/#\/c\/([A-Za-z0-9_-]{8,64})/);
  return m ? m[1] : "";
}

function setHash(id) {
  if (id) location.hash = `#/c/${id}`;
  else history.replaceState(null, "", location.pathname);
}

async function refreshList() {
  try {
    const data = await listConversations();
    items.value = data.items || [];
  } catch (err) {
    ElMessage.error(err.message || "无法加载历史");
  }
}

function mapHistory(raw) {
  return (raw || []).map((m) => ({
    role: m.role,
    content: m.content,
    intent: m.intent || "",
    departments: m.department_candidates || [],
    sources: m.sources || [],
    safety: m.safety || {},
    elapsed_ms: m.elapsed_ms,
    request_id: m.request_id,
    streaming: false,
  }));
}

async function openConversation(id, { silent = false } = {}) {
  currentId.value = id;
  setHash(id);
  if (!silent) mobileNav.value = false;
  const data = await getConversation(id);
  messages.value = data ? mapHistory(data.messages) : [];
}

function patchAssistant(idx, partial) {
  const list = messages.value;
  if (idx < 0 || idx >= list.length || list[idx].role !== "assistant") return;
  const next = { ...list[idx], ...partial };
  messages.value = [...list.slice(0, idx), next, ...list.slice(idx + 1)];
}

function newChat() {
  currentId.value = "";
  messages.value = [];
  setHash("");
  mobileNav.value = false;
}

async function send(text) {
  const query = (text ?? draft.value).trim();
  if (!query || sending.value) return;
  draft.value = "";
  messages.value = [
    ...messages.value,
    { role: "user", content: query },
    {
      role: "assistant",
      content: "",
      intent: "",
      departments: [],
      sources: [],
      safety: {},
      elapsed_ms: null,
      streaming: true,
      error: "",
    },
  ];
  const idx = messages.value.length - 1;
  sending.value = true;
  await nextTick();
  scrollBottom();
  let finishedId = currentId.value;
  let synced = false;
  try {
    await streamChat({
      query,
      conversationId: currentId.value || undefined,
      onEvent(ev) {
        const cur = messages.value[idx] || {};
        if (ev.type === "token") {
          patchAssistant(idx, { content: (cur.content || "") + (ev.text || "") });
        }
        if (ev.type === "sources") patchAssistant(idx, { sources: ev.items || [] });
        if (ev.type === "safety") patchAssistant(idx, { safety: ev });
        if (ev.type === "done") {
          finishedId = ev.conversation_id || finishedId;
          if (finishedId) currentId.value = finishedId;
          patchAssistant(idx, {
            intent: ev.intent || "",
            departments: ev.department_candidates || [],
            elapsed_ms: ev.elapsed_ms,
            request_id: ev.request_id,
            streaming: false,
          });
        }
        if (ev.type === "error") {
          patchAssistant(idx, { error: ev.message || "生成失败", streaming: false });
        }
        scrollBottom();
      },
    });
    if (finishedId) {
      await openConversation(finishedId, { silent: true });
      synced = true;
    }
  } catch (err) {
    patchAssistant(idx, { error: err.message || "请求失败", streaming: false });
    if (String(err.message || "").includes("API Key")) showKey.value = true;
  } finally {
    if (!synced) patchAssistant(idx, { streaming: false });
    sending.value = false;
    await refreshList();
    scrollBottom();
  }
}

function scrollBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
  });
}

function saveKey() {
  setApiKey(apiKey.value);
  showKey.value = false;
  ElMessage.success("已保存 API Key");
  refreshList();
}

function openSource(item) {
  source.value = item;
  showSource.value = true;
}

onMounted(async () => {
  await refreshList();
  const id = hashId();
  if (id) await openConversation(id);
  window.addEventListener("hashchange", async () => {
    const hid = hashId();
    if (hid && hid !== currentId.value) await openConversation(hid);
  });
});
</script>

<template>
  <div class="shell">
    <div class="banner">
      本系统不能替代专业诊疗，不做诊断、不开药、不调剂量。急症请立即拨打当地急救电话或前往急诊。
    </div>
    <div class="workspace">
      <div class="desk" :class="{ open: mobileNav }">
        <HistorySidebar
          :items="items"
          :current-id="currentId"
          @new="newChat"
          @select="openConversation"
        />
      </div>
      <main>
        <header class="bar">
          <button class="nav" type="button" @click="mobileNav = !mobileNav">菜单</button>
          <h1>就医导诊与医学科普</h1>
          <button class="ghost" type="button" @click="showKey = true">设置</button>
        </header>
        <div ref="scroller" class="scroll">
          <section v-if="empty" class="hero">
            <p>直接说症状或问题。知识来自公开图谱，不是医院号源。</p>
            <div class="chips">
              <button
                v-for="q in SUGGESTIONS"
                :key="q"
                type="button"
                @click="send(q)"
              >
                {{ q }}
              </button>
            </div>
          </section>
          <MessageList :messages="messages" @open-source="openSource" />
        </div>
        <form class="composer" @submit.prevent="send()">
          <textarea
            v-model="draft"
            rows="2"
            maxlength="2000"
            placeholder="例如：最近头疼头晕该挂哪科"
            :disabled="sending"
            @keydown.enter.exact.prevent="send()"
          />
          <button type="submit" :disabled="sending || !draft.trim()">发送</button>
        </form>
        <p class="attr">
          知识来自 OpenKG / 东南大学「面向家庭常见疾病的知识图谱」，CC BY-SA 4.0。不代表任何医院的号源或诊疗意见。
        </p>
      </main>
    </div>

    <el-drawer v-model="showSource" title="来源" size="360px">
      <p v-if="source">
        <strong>{{ source.title || source.source_id }}</strong>
      </p>
      <p v-if="source?.kind">类型：{{ source.kind }}</p>
      <p v-if="source?.source_id" class="mono">{{ source.source_id }}</p>
      <p v-if="source?.snippet">{{ source.snippet }}</p>
    </el-drawer>

    <el-dialog v-model="showKey" title="接口设置" width="420px">
      <p class="hint">与服务器 <code>API_KEYS</code> 一致，本地默认 <code>dev-key</code>。</p>
      <el-input v-model="apiKey" placeholder="X-API-Key" show-password />
      <template #footer>
        <el-button @click="showKey = false">取消</el-button>
        <el-button type="primary" @click="saveKey">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.banner {
  background: var(--amber);
  color: var(--amber-ink);
  text-align: center;
  padding: 0.55rem 1rem;
  font-size: 0.86rem;
  font-weight: 600;
}
.workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px 1fr;
}
.desk {
  min-height: 0;
}
main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #f7f3ea 0%, #efe8d8 100%);
}
.bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--line);
}
.bar h1 {
  flex: 1;
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
}
.nav {
  display: none;
}
.ghost,
.nav {
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 0.45rem;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
}
.scroll {
  flex: 1;
  overflow: auto;
  padding: 1.1rem 1.2rem 0;
}
.hero {
  max-width: 36rem;
  margin: 2.5rem auto 1rem;
  color: var(--muted);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.8rem;
}
.chips button {
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  cursor: pointer;
}
.chips button:hover {
  border-color: var(--teal);
  color: var(--teal-deep);
}
.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
  padding: 0.7rem 1.1rem 0;
}
textarea {
  resize: none;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  padding: 0.65rem 0.8rem;
  background: var(--card);
}
.composer button {
  background: var(--teal);
  color: #fff;
  border: 0;
  border-radius: 0.75rem;
  padding: 0 1.1rem;
  cursor: pointer;
}
.composer button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.attr {
  margin: 0.35rem 1.1rem 0.7rem;
  font-size: 0.72rem;
  color: var(--muted);
}
.mono {
  font-family: ui-monospace, Consolas, monospace;
  word-break: break-all;
}
.hint {
  color: var(--muted);
  font-size: 0.85rem;
}
@media (max-width: 800px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .desk {
    display: none;
    position: absolute;
    inset: 2.6rem 0 0 0;
    z-index: 4;
    width: min(86vw, 280px);
  }
  .desk.open {
    display: block;
  }
  .nav {
    display: inline-block;
  }
}
</style>
