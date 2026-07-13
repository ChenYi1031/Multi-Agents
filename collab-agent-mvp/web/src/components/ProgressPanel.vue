<template>
  <el-card class="progress-card" shadow="hover">
    <div class="progress-header">
      <h3 class="progress-title">
        <el-icon :size="18"><DataAnalysis /></el-icon>
        研究进度
      </h3>
      <el-tag type="info" size="small" effect="plain">
        {{ progressLog.length }} 条事件
      </el-tag>
    </div>

    <!-- Stage Progress -->
    <div class="stage-progress">
      <div
        v-for="(stage, index) in progressStages"
        :key="stage.key"
        class="stage-item"
        :class="{ active: stage.active, done: stage.done, pending: !stage.active && !stage.done }"
      >
        <div class="stage-indicator">
          <el-icon v-if="stage.done" class="stage-icon done-icon"><CircleCheckFilled /></el-icon>
          <el-icon v-else-if="stage.active" class="stage-icon active-icon"><Loading /></el-icon>
          <el-icon v-else class="stage-icon pending-icon"><CircleCheck /></el-icon>
          <div class="stage-connector" v-if="index < progressStages.length - 1" />
        </div>
        <div class="stage-info">
          <span class="stage-label" :class="{ 'label-active': stage.active }">
            {{ stage.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- Progress Bar -->
    <el-progress
      :percentage="progressPercent"
      :stroke-width="6"
      :color="progressColors"
      class="main-progress"
    />

    <!-- Cancel Button -->
    <div v-if="showCancel" class="cancel-row">
      <el-button
        type="danger"
        size="small"
        plain
        :icon="Close"
        @click="$emit('cancel')"
        :disabled="!showCancel"
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
import { computed, ref, watch, nextTick } from 'vue'
import { DataAnalysis, CircleCheckFilled, Loading, CircleCheck, Close } from '@element-plus/icons-vue'

const props = defineProps({
  progressStages: {
    type: Array,
    required: true,
  },
  progressLog: {
    type: Array,
    required: true,
  },
  currentStage: {
    type: String,
    default: 'idle',
  },
  showCancel: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['cancel'])

const logContainer = ref(null)

const progressPercent = computed(() => {
  const doneCount = props.progressStages.filter(s => s.done).length
  const total = props.progressStages.length
  if (doneCount === 0 && props.currentStage !== 'idle') return 15
  return Math.round((doneCount / total) * 100)
})

const progressColors = [
  { color: '#409eff', percentage: 30 },
  { color: '#67c23a', percentage: 70 },
  { color: '#e6a23c', percentage: 100 },
]

// Auto-scroll log to bottom
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
.progress-card {
  border-radius: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.progress-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

/* Stage indicators */
.stage-progress {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 0 20px;
}

.stage-item {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  flex: 1;
}

.stage-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.stage-icon {
  font-size: 24px;
  z-index: 1;
  background: var(--el-bg-color);
  border-radius: 50%;
}

.done-icon {
  color: #67c23a;
}

.active-icon {
  color: #409eff;
  animation: rotate 1.5s linear infinite;
}

.pending-icon {
  color: var(--el-text-color-placeholder);
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stage-connector {
  position: absolute;
  top: 12px;
  left: 24px;
  width: calc(100% - 16px);
  height: 2px;
  background: var(--el-border-color-light);
  z-index: 0;
}

.stage-item.done .stage-connector {
  background: #67c23a;
}

.stage-info {
  display: flex;
  flex-direction: column;
}

.stage-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.label-active {
  color: var(--el-color-primary);
  font-weight: 600;
}

.stage-item.done .stage-label {
  color: #67c23a;
}

.main-progress {
  margin-bottom: 16px;
}

/* Cancel button */
.cancel-row {
  text-align: center;
  margin-bottom: 16px;
}

/* Event log */
.log-container {
  max-height: 200px;
  overflow-y: auto;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 12px;
}

.log-entry {
  padding: 4px 8px;
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  gap: 8px;
  border-radius: 4px;
}

.log-entry:hover {
  background: var(--el-fill-color);
}

.log-time {
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
  font-family: monospace;
  font-size: 12px;
  min-width: 70px;
}

.log-message {
  color: var(--el-text-color-primary);
}

.log-progress .log-message {
  color: var(--el-color-primary);
}

.log-success .log-message {
  color: #67c23a;
}

.log-error .log-message {
  color: #f56c6c;
}
</style>
