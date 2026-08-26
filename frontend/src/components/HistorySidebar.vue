<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  currentId: { type: String, default: "" },
});

const emit = defineEmits(["new", "select"]);

function preview(item) {
  return item.preview || "空对话";
}

function when(item) {
  const raw = item.updated_at || "";
  return raw.replace("T", " ").slice(0, 16);
}
</script>

<template>
  <aside class="side">
    <div class="brand">
      <div class="mark">问</div>
      <div>
        <strong>智慧问诊</strong>
        <small>导诊 · 科普 · 不替代医师</small>
      </div>
    </div>
    <button class="new" type="button" @click="emit('new')">新对话</button>
    <p class="label">历史</p>
    <ul>
      <li v-for="item in items" :key="item.conversation_id">
        <button
          type="button"
          :class="{ active: item.conversation_id === currentId }"
          @click="emit('select', item.conversation_id)"
        >
          <span>{{ preview(item) }}</span>
          <time>{{ when(item) }}</time>
        </button>
      </li>
      <li v-if="!items.length" class="empty">还没有记录</li>
    </ul>
  </aside>
</template>

<style scoped>
.side {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--sidebar);
  color: #e8efe9;
  padding: 1rem 0.85rem;
}
.brand {
  display: flex;
  gap: 0.7rem;
  align-items: center;
  margin-bottom: 1rem;
}
.mark {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 0.55rem;
  background: #2a8f7c;
  display: grid;
  place-items: center;
  font-weight: 700;
}
.brand small {
  display: block;
  color: #9bb5ae;
  font-size: 0.72rem;
}
.new {
  border: 1px dashed #4d7a72;
  background: transparent;
  color: #dff3ee;
  border-radius: 0.5rem;
  padding: 0.55rem;
  cursor: pointer;
}
.new:hover {
  background: #1e403b;
}
.label {
  margin: 1rem 0 0.4rem;
  font-size: 0.75rem;
  color: #8aa39c;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  flex: 1;
}
li button {
  width: 100%;
  text-align: left;
  background: transparent;
  border: 0;
  color: inherit;
  border-radius: 0.45rem;
  padding: 0.55rem 0.5rem;
  cursor: pointer;
  margin-bottom: 0.2rem;
}
li button:hover,
li button.active {
  background: #21443e;
}
li span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
time {
  display: block;
  font-size: 0.7rem;
  color: #8aa39c;
  margin-top: 0.15rem;
}
.empty {
  color: #8aa39c;
  font-size: 0.85rem;
  padding: 0.5rem;
}
</style>
