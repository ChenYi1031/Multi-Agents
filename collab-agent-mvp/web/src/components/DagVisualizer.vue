<template>
  <el-card class="dag-card" shadow="hover">
    <div class="dag-header">
      <h3 class="dag-title">
        <el-icon :size="18"><DataAnalysis /></el-icon>
        研究进度
      </h3>
    </div>
    <div class="dag-progress-row">
      <div
        v-for="(stage, index) in stages"
        :key="stage.key"
        class="stage-block"
      >
        <el-progress
          type="circle"
          :percentage="stagePercentage(stage)"
          :status="stageStatus(stage)"
          :width="80"
          :stroke-width="6"
        >
          <span class="stage-percent-text">{{ stagePercentageText(stage) }}</span>
        </el-progress>
        <span class="stage-label" :class="{ 'label-active': stage.active, 'label-done': stage.done }">
          {{ stage.label }}
        </span>
      </div>
    </div>
    <div v-if="stages.some(s => s.active || s.done)" class="stage-connectors">
      <el-progress
        :percentage="overallPercent"
        :stroke-width="8"
        :color="overallColors"
        class="overall-bar"
      />
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'

const props = defineProps({
  stages: {
    type: Array,
    default: () => [
      { key: 'research',   label: '信息搜索',   active: false, done: false },
      { key: 'writing',    label: '报告撰写',   active: false, done: false },
      { key: 'fact_check', label: '事实核查',   active: false, done: false },
      { key: 'complete',   label: '生成完成',   active: false, done: false },
    ],
  },
})

function stagePercentage(stage) {
  if (stage.done) return 100
  if (stage.active) return 60
  return 0
}

function stageStatus(stage) {
  if (stage.done) return 'success'
  if (stage.active) return 'warning'
  return undefined
}

function stagePercentageText(stage) {
  if (stage.done) return '✓'
  if (stage.active) return '⟳'
  return ''
}

const overallPercent = computed(() => {
  const doneCount = props.stages.filter(s => s.done).length
  const total = props.stages.length
  return Math.round((doneCount / total) * 100)
})

const overallColors = [
  { color: '#409eff', percentage: 30 },
  { color: '#67c23a', percentage: 70 },
  { color: '#e6a23c', percentage: 100 },
]
</script>

<style scoped>
.dag-card {
  border-radius: 12px;
}

.dag-header {
  margin-bottom: 12px;
}

.dag-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.dag-progress-row {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  gap: 24px;
  flex-wrap: wrap;
  padding: 8px 0;
}

.stage-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 80px;
}

.stage-percent-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.stage-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.stage-label.label-active {
  color: var(--el-color-primary);
  font-weight: 600;
}

.stage-label.label-done {
  color: #67c23a;
  font-weight: 600;
}

.stage-connectors {
  margin-top: 16px;
}

.overall-bar {
  max-width: 500px;
  margin: 0 auto;
}
</style>
