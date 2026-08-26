<script setup>
import { INTENT_LABEL } from "../api";

defineProps({
  messages: { type: Array, default: () => [] },
});

const emit = defineEmits(["open-source"]);

function intentName(id) {
  return INTENT_LABEL[id] || id || "";
}

function intentClass(id) {
  if (id === "emergency") return "em";
  if (id === "refuse") return "rf";
  if (id === "triage") return "tr";
  return "ot";
}
</script>

<template>
  <div class="thread">
    <article
      v-for="(m, i) in messages"
      :key="i"
      :class="['row', m.role]"
    >
      <div v-if="m.role === 'user'" class="bubble user">{{ m.content }}</div>
      <div v-else class="bubble asst" :class="{ emergency: m.intent === 'emergency' }">
        <header v-if="m.intent || m.elapsed_ms">
          <span v-if="m.intent" :class="['tag', intentClass(m.intent)]">{{ intentName(m.intent) }}</span>
          <span v-for="d in m.departments || []" :key="d" class="tag dept">{{ d }}</span>
          <span v-if="m.safety?.blocked" class="tag em">已拦截</span>
          <span v-if="m.elapsed_ms != null" class="time">{{ m.elapsed_ms }} ms</span>
        </header>
        <p class="body">{{ m.content }}<span v-if="m.streaming" class="caret">▍</span></p>
        <p v-if="m.error" class="err">{{ m.error }}</p>
        <footer v-if="(m.sources || []).length">
          <button
            v-for="(s, si) in m.sources"
            :key="s.source_id || si"
            type="button"
            class="src"
            @click="emit('open-source', s)"
          >
            {{ s.title || s.source_id || "来源" }}
          </button>
        </footer>
      </div>
    </article>
  </div>
</template>

<style scoped>
.thread {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 0.2rem 0 1.2rem;
}
.row {
  display: flex;
}
.row.user {
  justify-content: flex-end;
}
.bubble {
  max-width: min(42rem, 92%);
  border-radius: 1rem;
  padding: 0.85rem 1rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.user {
  background: var(--teal);
  color: #fff;
  border-bottom-right-radius: 0.25rem;
}
.asst {
  background: var(--card);
  border: 1px solid var(--line);
  border-bottom-left-radius: 0.25rem;
}
.asst.emergency {
  border-color: #e8b4b4;
  background: #fff6f6;
}
header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  margin-bottom: 0.45rem;
}
.tag {
  font-size: 0.72rem;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}
.tr {
  background: #d7f0e8;
  color: #0a4d4a;
}
.em {
  background: #f8d4d4;
  color: var(--danger);
}
.rf {
  background: #fce8c8;
  color: #7a4b00;
}
.ot {
  background: #e7e4dc;
  color: #3d3a32;
}
.dept {
  background: #e6eef8;
  color: #1d4f8a;
}
.time {
  margin-left: auto;
  color: var(--muted);
  font-size: 0.72rem;
}
.body {
  margin: 0;
}
.caret {
  color: var(--teal);
}
.err {
  color: var(--danger);
  margin: 0.4rem 0 0;
}
footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.7rem;
}
.src {
  border: 1px solid var(--line);
  background: #f7f3ea;
  border-radius: 999px;
  padding: 0.12rem 0.55rem;
  font-size: 0.75rem;
  cursor: pointer;
  color: var(--teal-deep);
}
.src:hover {
  border-color: var(--teal);
}
</style>
