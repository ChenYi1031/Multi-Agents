<template>
  <el-card class="token-card" shadow="hover">
    <div class="token-header">
      <div class="token-title-row">
        <el-icon :size="18"><DataAnalysis /></el-icon>
        <h3 class="token-title">{{ t('tokenUsage') }}</h3>
      </div>
      <el-tag
        :type="totalCost > 0 ? 'warning' : 'info'"
        size="small"
        effect="dark"
      >
        ≈ ¥{{ totalCost.toFixed(6) }}
      </el-tag>
    </div>

    <!-- Summary numbers -->
    <div class="token-summary">
      <div class="token-stat">
        <span class="stat-label">{{ t('inputTokens') }}</span>
        <span class="stat-value">{{ formatNumber(totalInput) }}</span>
      </div>
      <el-icon class="stat-arrow"><ArrowRight /></el-icon>
      <div class="token-stat">
        <span class="stat-label">{{ t('outputTokens') }}</span>
        <span class="stat-value">{{ formatNumber(totalOutput) }}</span>
      </div>
      <div class="token-stat total">
        <span class="stat-label">{{ t('total') }}</span>
        <span class="stat-value highlight">{{ formatNumber(totalTokens) }}</span>
      </div>
    </div>

    <!-- Per-agent breakdown -->
    <div v-if="agentBreakdown.length > 1" class="token-breakdown">
      <el-divider />
      <h4 class="breakdown-title">{{ t('byAgent') }}</h4>
      <div
        v-for="agent in agentBreakdown"
        :key="agent.agent"
        class="agent-row"
      >
        <div class="agent-info">
          <span class="agent-name">{{ agent.label }}</span>
          <span class="agent-calls">{{ agent.call_count }} {{ t('calls') }}</span>
        </div>
        <div class="agent-bar-wrapper">
          <el-progress
            :percentage="agent.percentage"
            :format="() => formatNumber(agent.total_tokens) + ' tokens'"
            :stroke-width="18"
            :color="agent.color"
          />
          <span class="agent-cost">¥{{ agent.total_cost.toFixed(6) }}</span>
        </div>
      </div>
    </div>

    <!-- Per-call detail cards -->
    <div v-if="calls.length > 0" class="token-detail">
      <el-divider />
      <div class="detail-header">
        <h4 class="breakdown-title">{{ t('callDetail') }}</h4>
        <span class="detail-count">{{ calls.length }} {{ t('calls') }}</span>
      </div>
      <div class="call-list">
        <div
          v-for="(call, idx) in calls"
          :key="idx"
          class="call-item"
          :class="'call-agent-' + (call.agent || 'unknown')"
        >
          <div class="call-top">
            <span class="call-agent-tag">{{ agentLabel(call.agent) || call.agent }}</span>
            <span class="call-cost">¥{{ call.cost.toFixed(6) }}</span>
          </div>
          <div class="call-bars">
            <div class="call-bar-group">
              <span class="call-bar-label">{{ t('inputTokens') }}</span>
              <div class="call-bar-track">
                <div
                  class="call-bar-fill input-fill"
                  :style="{ width: barPercent(call.input_tokens, call.total_tokens) + '%' }"
                />
              </div>
              <span class="call-bar-val">{{ call.input_tokens.toLocaleString() }}</span>
            </div>
            <div class="call-bar-group">
              <span class="call-bar-label">{{ t('outputTokens') }}</span>
              <div class="call-bar-track">
                <div
                  class="call-bar-fill output-fill"
                  :style="{ width: barPercent(call.output_tokens, call.total_tokens) + '%' }"
                />
              </div>
              <span class="call-bar-val">{{ call.output_tokens.toLocaleString() }}</span>
            </div>
          </div>
          <div class="call-meta">
            <span class="call-meta-item">
              <el-icon :size="12"><Timer /></el-icon>
              {{ call.duration_ms.toFixed(0) }}ms
            </span>
            <span class="call-meta-item">{{ call.total_tokens.toLocaleString() }} tokens</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { DataAnalysis, ArrowRight, Timer } from '@element-plus/icons-vue'
import { useI18n } from '../utils/i18n'

const props = defineProps({
  tokenUsage: {
    type: Object,
    default: () => ({}),
  },
})

const { t } = useI18n()

const AGENT_COLORS = {
  researcher: '#409eff',
  writer: '#67c23a',
}
function agentLabel(key) {
  return t(key === 'researcher' ? 'researcher' : 'writer')
}

const totalInput = computed(() => props.tokenUsage?.total_input_tokens ?? 0)
const totalOutput = computed(() => props.tokenUsage?.total_output_tokens ?? 0)
const totalTokens = computed(() => props.tokenUsage?.total_tokens ?? 0)
const totalCost = computed(() => props.tokenUsage?.total_cost ?? 0)
const calls = computed(() => props.tokenUsage?.calls ?? [])

const agentBreakdown = computed(() => {
  const raw = props.tokenUsage?.agent_breakdown
  if (!raw || raw.length === 0) {
    // If no breakdown, build one from calls
    return buildBreakdownFromCalls()
  }
  const total = raw.reduce((s, a) => s + a.total_tokens, 0) || 1
  return raw.map((a) => ({
    ...a,
    label: agentLabel(a.agent) || a.agent,
    color: AGENT_COLORS[a.agent] || '#909399',
    percentage: Math.round((a.total_tokens / total) * 100),
  }))
})

function buildBreakdownFromCalls() {
  const groups = {}
  for (const c of calls.value) {
    if (!groups[c.agent]) {
      groups[c.agent] = {
        agent: c.agent,
        label: agentLabel(c.agent) || c.agent,
        total_input_tokens: 0,
        total_output_tokens: 0,
        total_tokens: 0,
        total_cost: 0,
        call_count: 0,
        color: AGENT_COLORS[c.agent] || '#909399',
      }
    }
    groups[c.agent].total_input_tokens += c.input_tokens
    groups[c.agent].total_output_tokens += c.output_tokens
    groups[c.agent].total_tokens += c.total_tokens
    groups[c.agent].total_cost += c.cost
    groups[c.agent].call_count += 1
  }
  const arr = Object.values(groups)
  const total = arr.reduce((s, a) => s + a.total_tokens, 0) || 1
  return arr.map((a) => ({ ...a, percentage: Math.round((a.total_tokens / total) * 100) }))
}

function barPercent(part, total) {
  if (!total) return 0
  return Math.max(4, (part / total) * 100)
}

function formatNumber(n) {
  if (n == null) return '0'
  return n.toLocaleString('zh-CN')
}
</script>

<style scoped>
.token-card {
  border-radius: 12px;
}

.token-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.token-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.token-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.token-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 16px 0 8px;
}

.token-stat {
  text-align: center;
  min-width: 80px;
}

.token-stat.total {
  background: var(--el-color-primary-light-9);
  border-radius: 8px;
  padding: 8px 16px;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.stat-value.highlight {
  color: var(--el-color-primary);
}

.stat-arrow {
  color: var(--el-text-color-placeholder);
  font-size: 16px;
}

.token-breakdown {
  margin-top: 4px;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--el-text-color-regular);
}

.agent-row {
  margin-bottom: 12px;
}

.agent-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.agent-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.agent-calls {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.agent-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-bar-wrapper :deep(.el-progress) {
  flex: 1;
}

.agent-cost {
  font-size: 12px;
  color: var(--el-color-warning);
  white-space: nowrap;
  min-width: 72px;
  text-align: right;
}

.token-detail {
  margin-top: 4px;
}

:deep(.el-divider) {
  margin: 12px 0;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.detail-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.call-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.call-item {
  background: var(--el-fill-color);
  border-radius: 8px;
  padding: 10px 12px;
  border-left: 3px solid var(--el-border-color);
  transition: background 0.15s;
}

.call-item:hover {
  background: var(--el-fill-color-light);
}

.call-item.call-agent-researcher {
  border-left-color: var(--el-color-primary);
}

.call-item.call-agent-writer {
  border-left-color: var(--el-color-success);
}

.call-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.call-agent-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  background: var(--el-fill-color);
  padding: 1px 8px;
  border-radius: 4px;
}

.call-cost {
  font-size: 12px;
  color: var(--el-color-warning);
  font-weight: 500;
}

.call-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
}

.call-bar-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.call-bar-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  width: 20px;
  text-align: right;
  flex-shrink: 0;
}

.call-bar-track {
  flex: 1;
  height: 6px;
  background: var(--el-fill-color);
  border-radius: 3px;
  overflow: hidden;
}

.call-bar-fill {
  height: 100%;
  border-radius: 3px;
  min-width: 4px;
  transition: width 0.3s ease;
}

.input-fill {
  background: linear-gradient(90deg, var(--el-color-primary), var(--el-color-primary-light-5));
}

.output-fill {
  background: linear-gradient(90deg, var(--el-color-success), var(--el-color-success-light-5));
}

.call-bar-val {
  font-size: 11px;
  color: var(--el-text-color-regular);
  width: 50px;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.call-meta {
  display: flex;
  gap: 16px;
  margin-top: 4px;
}

.call-meta-item {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
