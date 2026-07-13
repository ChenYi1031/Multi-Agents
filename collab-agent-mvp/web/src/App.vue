<template>
  <el-container class="app-container">
    <!-- Header -->
    <el-header class="app-header" height="64px">
      <div class="header-content">
        <div class="header-left">
          <el-icon :size="28" class="header-icon"><Connection /></el-icon>
          <div class="header-text">
            <h1 class="app-title">CollabAgent MVP</h1>
            <span class="app-subtitle">多 Agent 协作研究报告生成系统</span>
          </div>
        </div>
        <div class="header-right">
          <el-tag
            :type="backendStatus === 'ok' ? 'success' : 'danger'"
            size="small"
            effect="dark"
          >
            {{ backendStatus === 'ok' ? '服务正常' : '未连接' }}
          </el-tag>
        </div>
      </div>
    </el-header>

    <!-- Main Content -->
    <el-main class="app-main">
      <div class="content-wrapper">
        <!-- Settings Panel (模型供应商管理) -->
        <SettingsPanel
          ref="settingsRef"
          @change="onSettingsChange"
        />

        <!-- Knowledge Base (RAG) -->
        <KnowledgePanel />

        <!-- Research Input -->
        <ResearchInput
          :loading="isResearching"
          @submit="handleSubmit"
        />

        <!-- DAG Visualization -->
        <DagVisualizer
          v-if="isResearching || progressStages.some(s => s.done || s.active)"
          :stages="progressStages"
        />

        <!-- Progress Panel -->
        <ProgressPanel
          v-if="isResearching || progressLog.length > 0"
          :progress-stages="progressStages"
          :progress-log="progressLog"
          :current-stage="currentStage"
          :show-cancel="isResearching"
          @cancel="handleCancel"
        />

        <!-- Token Usage Panel -->
        <TokenUsagePanel
          v-if="tokenUsage"
          :token-usage="tokenUsage"
        />

        <!-- Error Alert -->
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="true"
          @close="errorMessage = ''"
          class="error-alert"
        />

        <!-- Report Display -->
        <ReportPanel
          v-if="reportContent"
          :report="reportContent"
          :search-results="searchResults"
          :fact-check="factCheckData"
          :topic="lastTopic"
          :model-name="modelName"
          :search-source="searchSource"
          @clear="handleClear"
          @followup="handleFollowUp"
        />

        <!-- Research History -->
        <el-card v-if="historyList.length > 0" class="history-card" shadow="hover">
          <div class="card-header">
            <h3 class="card-title">
              <el-icon :size="18"><Clock /></el-icon>
              历史记录
            </h3>
            <el-button size="small" text type="danger" @click="clearHistory">
              清除历史
            </el-button>
          </div>
          <el-timeline>
            <el-timeline-item
              v-for="(item, index) in historyList"
              :key="index"
              :timestamp="item.time"
              placement="top"
            >
              <div class="history-item" @click="restoreHistory(item)">
                <el-link type="primary" :underline="false">
                  {{ item.topic }}
                </el-link>
                <span v-if="reportContent && reportContent === item.report" class="history-current-badge">
                  <el-tag size="small" type="success">当前</el-tag>
                </span>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </div>
    </el-main>

    <!-- Footer -->
    <el-footer class="app-footer" height="48px">
      <span>CollabAgent MVP v2.0 &copy; 2026</span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Connection, Clock } from '@element-plus/icons-vue'
import ResearchInput from './components/ResearchInput.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import ReportPanel from './components/ReportPanel.vue'
import TokenUsagePanel from './components/TokenUsagePanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import DagVisualizer from './components/DagVisualizer.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'

const HISTORY_KEY = 'collab-agent-history'

const isResearching = ref(false)
const errorMessage = ref('')
const reportContent = ref('')
const searchResults = ref([])
const progressLog = ref([])
const currentStage = ref('idle')
const backendStatus = ref('checking')
const currentTaskId = ref('')
const eventSourceRef = ref(null)
const historyList = ref([])
const tokenUsage = ref(null)
const settingsRef = ref(null)
const factCheckData = ref(null)
const lastTopic = ref('')
const followupPanel = ref(false)

// Provider config (from SettingsPanel)
const providerConfig = ref(null)

function onSettingsChange({ provider }) {
  if (provider) {
    providerConfig.value = {
      api_base_url: provider.baseUrl,
      api_key: provider.apiKey,
      api_format: provider.apiFormat,
      model_name: provider.selectedModel,
    }
  } else {
    providerConfig.value = null
  }
}

const progressStages = reactive([
  { key: 'research',   label: '信息搜索',   done: false, active: false },
  { key: 'writing',    label: '报告撰写',   done: false, active: false },
  { key: 'fact_check', label: '事实核查',   done: false, active: false },
  { key: 'complete',   label: '生成完成',   done: false, active: false },
])

onMounted(async () => {
  await checkHealth()
  loadHistory()
})

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    historyList.value = raw ? JSON.parse(raw) : []
  } catch { historyList.value = [] }
}

function saveToHistory(topic, report, results) {
  const entry = { topic, report, searchResults: results, time: new Date().toLocaleString('zh-CN') }
  const list = [entry, ...historyList.value.filter(h => h.topic !== topic)].slice(0, 20)
  historyList.value = list
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list)) } catch { /* ok */ }
}

function restoreHistory(item) {
  reportContent.value = item.report
  searchResults.value = item.searchResults || []
  errorMessage.value = ''
  progressLog.value = []
  resetStages()
}

function clearHistory() {
  historyList.value = []
  localStorage.removeItem(HISTORY_KEY)
}

async function checkHealth() {
  try {
    const res = await fetch('/health')
    const data = await res.json()
    backendStatus.value = data.status
  } catch { backendStatus.value = 'error' }
}

function resetStages() {
  progressStages.forEach(s => { s.done = false; s.active = false })
  progressLog.value = []
  currentStage.value = 'idle'
}

function addLog(message, type = 'info') {
  progressLog.value.push({ id: Date.now() + Math.random(), message, type, time: new Date().toLocaleTimeString() })
}

function handleCancel() {
  if (!currentTaskId.value) {
    if (eventSourceRef.value) eventSourceRef.value.close()
    isResearching.value = false
    addLog('⏹ 研究任务已取消', 'info')
    return
  }
  addLog('⏹ 正在取消研究任务...', 'info')
  fetch(`/research/stream/${currentTaskId.value}`, { method: 'DELETE' })
    .catch(() => {})
    .finally(() => {
      if (eventSourceRef.value) eventSourceRef.value.close()
      isResearching.value = false
      addLog('⏹ 研究任务已取消', 'info')
    })
}

function handleSubmit(topic) {
  if (!topic.trim()) return

  isResearching.value = true
  errorMessage.value = ''
  reportContent.value = ''
  searchResults.value = []
  factCheckData.value = null
  currentTaskId.value = ''
  tokenUsage.value = null
  lastTopic.value = topic
  resetStages()

  addLog(`开始研究主题: "${topic}"`, 'info')
  currentStage.value = 'research'
  progressStages[0].active = true

  // Build SSE URL with optional provider config
  let url = `/research/stream?topic=${encodeURIComponent(topic)}`
  if (providerConfig.value) {
    const c = providerConfig.value
    if (c.model_name) url += `&model_name=${encodeURIComponent(c.model_name)}`
    if (c.api_base_url) url += `&api_base_url=${encodeURIComponent(c.api_base_url)}`
    if (c.api_key) url += `&api_key=${encodeURIComponent(c.api_key)}`
    if (c.api_format) url += `&api_format=${encodeURIComponent(c.api_format)}`
  }

  const eventSource = new EventSource(url)
  eventSourceRef.value = eventSource

  eventSource.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    const { stage, message, task_id } = data

    if (task_id) currentTaskId.value = task_id
    addLog(message, 'progress')

    if (stage === 'starting') {
      // no stage change
    } else if (stage === 'research') {
      currentStage.value = 'research'
      progressStages[0].active = true
      progressStages[0].done = false
    } else if (stage === 'research_done') {
      progressStages[0].done = true
      progressStages[0].active = false
      currentStage.value = 'research_done'
      if (data.search_results) searchResults.value = data.search_results
      if (data.token_usage) tokenUsage.value = data.token_usage
    } else if (stage === 'writing') {
      currentStage.value = 'writing'
      progressStages[1].active = true
      progressStages[1].done = false
    } else if (stage === 'writing_done') {
      progressStages[1].done = true
      progressStages[1].active = false
      currentStage.value = 'writing_done'
    } else if (stage === 'fact_check') {
      currentStage.value = 'fact_check'
      progressStages[2].active = true
      progressStages[2].done = false
    } else if (stage === 'fact_check_done') {
      progressStages[2].done = true
      progressStages[2].active = false
      currentStage.value = 'fact_check_done'
      if (data.fact_check) factCheckData.value = data.fact_check
      if (data.token_usage) tokenUsage.value = data.token_usage
    }
  })

  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data)
    reportContent.value = data.report
    if (data.search_results) searchResults.value = data.search_results
    if (data.token_usage) tokenUsage.value = data.token_usage
    if (data.fact_check) factCheckData.value = data.fact_check
    progressStages[3].done = true
    currentStage.value = 'complete'
    addLog('✅ 研究报告生成完成！', 'success')
    isResearching.value = false
    eventSource.close()
    eventSourceRef.value = null
    saveToHistory(lastTopic.value, data.report, data.search_results || [])
  })

  eventSource.addEventListener('error', (e) => {
    try {
      const data = JSON.parse((e.data || '{}'))
      errorMessage.value = data.message || '研究过程发生错误，请重试'
    } catch {
      errorMessage.value = eventSource.readyState === EventSource.CLOSED
        ? '连接中断，请检查后端服务是否运行'
        : '研究过程发生错误，请重试'
    }
    addLog(`❌ ${errorMessage.value}`, 'error')
    isResearching.value = false
    eventSource.close()
    eventSourceRef.value = null
  })
}

async function handleFollowUp(payload) {
  addLog(`🔍 发起追问: "${payload.followup_question}"`, 'info')
  isResearching.value = true
  errorMessage.value = ''
  resetStages()
  progressStages[0].active = true
  currentStage.value = 'research'

  // Merge provider config into followup payload
  const extendedPayload = { ...payload }
  if (providerConfig.value) {
    extendedPayload.api_base_url = providerConfig.value.api_base_url
    extendedPayload.api_key = providerConfig.value.api_key
    extendedPayload.api_format = providerConfig.value.api_format
    extendedPayload.model_name = providerConfig.value.model_name
  }

  try {
    const res = await fetch('/research/followup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(extendedPayload),
    })
    const data = await res.json()
    if (data.status === 'error') {
      errorMessage.value = data.detail || '追问失败'
      addLog(`❌ ${errorMessage.value}`, 'error')
    } else {
      reportContent.value = data.final_report
      searchResults.value = data.search_results || []
      if (data.token_usage) tokenUsage.value = data.token_usage
      if (data.fact_check) factCheckData.value = data.fact_check
      addLog('✅ 追问完成，报告已更新', 'success')
      progressStages[3].done = true
      currentStage.value = 'complete'
    }
  } catch (e) {
    errorMessage.value = '追问请求失败: ' + e.message
    addLog(`❌ ${errorMessage.value}`, 'error')
  } finally {
    isResearching.value = false
  }
}

function handleClear() {
  reportContent.value = ''
  searchResults.value = []
  factCheckData.value = null
  progressLog.value = []
  tokenUsage.value = null
  resetStages()
}
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: white;
  display: flex;
  align-items: center;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  background: rgba(255, 255, 255, 0.2);
  padding: 6px;
  border-radius: 8px;
}

.header-text {
  display: flex;
  flex-direction: column;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  line-height: 1.2;
}

.app-subtitle {
  font-size: 12px;
  opacity: 0.85;
}

.app-main {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.error-alert {
  margin-top: 8px;
}

.app-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  border-top: 1px solid var(--el-border-color-light);
}

.history-card {
  border-radius: 12px;
}

.history-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.history-card .card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.history-item {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.history-item:hover {
  opacity: 0.8;
}
</style>
