<template>
  <el-card class="progress-card" shadow="hover">
    <!-- Title + event count -->
    <div class="progress-header">
        <h3 class="progress-title">
          <el-icon :size="18"><DataAnalysis /></el-icon>
          {{ t('progressTitle') }}
        </h3>
        <el-tag type="info" size="small" effect="plain">
          {{ progressLog.length }} {{ t('eventsFormat') }}
        </el-tag>
    </div>

    <!-- Circle Progress Row -->
    <div class="progress-circles">
      <div v-for="stage in progressStages" :key="stage.key" class="stage-block">
        <el-progress
          type="circle"
          :percentage="stagePercentage(stage)"
          :status="stageStatus(stage)"
          :width="76"
          :stroke-width="6"
        >
          <span class="stage-percent-text">{{ stagePercentText(stage) }}</span>
        </el-progress>
        <span class="stage-label" :class="{ 'label-active': stage.active, 'label-done': stage.done }">
          {{ stage.label }}
        </span>
      </div>
    </div>

    <!-- Overall bar -->
    <el-progress
      v-if="progressStages.some(s => s.active || s.done)"
      :percentage="overallPercent"
      :stroke-width="6"
      :color="overallColors"
      class="overall-bar"
    />

    <!-- Cancel Button -->
    <div v-if="showCancel" class="cancel-row">
      <el-button type="danger" size="small" plain :icon="Close" @click="$emit('cancel')">
        {{ t('cancelResearch') }}
      </el-button>
    </div>

    <!-- Event Log -->
    <div class="log-section">
      <div class="log-section-title">
        <el-icon :size="14"><Tickets /></el-icon>
        <span>{{ t('logTitle') }}</span>
      </div>
      <div class="log-container" ref="logContainer">
        <div v-for="log in progressLog" :key="log.id" class="log-entry" :class="'log-' + log.type">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="progressLog.length === 0" class="log-empty">{{ t('logEmpty') }}</div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { DataAnalysis, Tickets, Close } from '@element-plus/icons-vue'

const props = defineProps({
  progressStages: { type: Array, required: true },
  progressLog: { type: Array, required: true },
  currentStage: { type: String, default: 'idle' },
  showCancel: { type: Boolean, default: false },
})

defineEmits(['cancel'])

const logContainer = ref(null)

function stagePercentage(s) {
  if (s.done) return 100
  if (s.active) return 60
  return 0
}
function stageStatus(s) {
  if (s.done) return 'success'
  if (s.active) return 'warning'
  return undefined
}
function stagePercentText(s) {
  if (s.done) return '✓'
  if (s.active) return '⟳'
  return ''
}

const overallPercent = computed(() => {
  const done = props.progressStages.filter(s => s.done).length
  return Math.round((done / props.progressStages.length) * 100)
})
const overallColors = [
  { color: '#409eff', percentage: 30 },
  { color: '#67c23a', percentage: 70 },
  { color: '#e6a23c', percentage: 100 },
]

watch(() => props.progressLog.length, async () => {
  await nextTick()
  if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
})
</script>

<style scoped>
.progress-card { border-radius: 12px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.progress-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; margin: 0; }

.progress-circles { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; padding: 4px 0 12px; }
.stage-block { display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 76px; }
.stage-percent-text { font-size: 15px; font-weight: 700; color: var(--el-text-color-primary); }
.stage-label { font-size: 13px; color: var(--el-text-color-secondary); white-space: nowrap; }
.stage-label.label-active { color: var(--el-color-primary); font-weight: 600; }
.stage-label.label-done { color: #67c23a; font-weight: 600; }

.overall-bar { max-width: 480px; margin: 0 auto 12px; }

.cancel-row { text-align: center; margin-bottom: 12px; }

.log-section { border-top: 1px solid var(--el-border-color-light); padding-top: 12px; }
.log-section-title { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.log-container { max-height: 200px; overflow-y: auto; background: var(--el-fill-color-lighter); border-radius: 8px; padding: 8px 12px; }
.log-empty { text-align: center; color: var(--el-text-color-placeholder); font-size: 13px; padding: 16px 0; }
.log-entry { padding: 3px 6px; font-size: 13px; line-height: 1.5; display: flex; gap: 8px; border-radius: 4px; }
.log-entry:hover { background: var(--el-fill-color); }
.log-time { color: var(--el-text-color-placeholder); white-space: nowrap; font-family: monospace; font-size: 12px; min-width: 68px; }
.log-message { color: var(--el-text-color-primary); }
.log-progress .log-message { color: var(--el-color-primary); }
.log-success .log-message { color: #67c23a; }
.log-error .log-message { color: #f56c6c; }
</style>
