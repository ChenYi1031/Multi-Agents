<template>
  <el-card class="progress-card" shadow="hover">
    <div class="progress-header">
      <h3 class="progress-title">
        <el-icon :size="18"><Tickets /></el-icon>
        运行日志
      </h3>
      <el-tag type="info" size="small" effect="plain">
        {{ progressLog.length }} 条事件
      </el-tag>
    </div>

    <!-- Cancel Button -->
    <div v-if="showCancel" class="cancel-row">
      <el-button
        type="danger"
        size="small"
        plain
        :icon="Close"
        @click="$emit('cancel')"
      >
        取消研究
      </el-button>
    </div>

    <!-- Event Log -->
    <div class="log-container" ref="logContainer">
      <div
        v-for="log in progressLog"
        :key="log.id"
        class="log-entry"
        :class="'log-' + log.type"
      >
        <span class="log-time">{{ log.time }}</span>
        <span class="log-message">{{ log.message }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Tickets, Close } from '@element-plus/icons-vue'

const props = defineProps({
  progressStages: { type: Array, required: true },
  progressLog: { type: Array, required: true },
  currentStage: { type: String, default: 'idle' },
  showCancel: { type: Boolean, default: false },
})

defineEmits(['cancel'])

const logContainer = ref(null)

watch(
  () => props.progressLog.length,
  async () => {
    await nextTick()
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.progress-card { border-radius: 12px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.progress-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; margin: 0; }
.cancel-row { text-align: center; margin-bottom: 16px; }
.log-container { max-height: 240px; overflow-y: auto; background: var(--el-fill-color-lighter); border-radius: 8px; padding: 12px; }
.log-entry { padding: 4px 8px; font-size: 13px; line-height: 1.6; display: flex; gap: 8px; border-radius: 4px; }
.log-entry:hover { background: var(--el-fill-color); }
.log-time { color: var(--el-text-color-placeholder); white-space: nowrap; font-family: monospace; font-size: 12px; min-width: 70px; }
.log-message { color: var(--el-text-color-primary); }
.log-progress .log-message { color: var(--el-color-primary); }
.log-success .log-message { color: #67c23a; }
.log-error .log-message { color: #f56c6c; }
</style>
