<template>
  <el-config-provider :locale="currentLocale">
  <el-container class="app-container">
    <!-- Header -->
    <el-header class="app-header" height="56px">
      <div class="header-content">
        <div class="header-left">
          <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">
            <el-icon :size="20">
              <Fold v-if="sidebarOpen" />
              <Expand v-else />
            </el-icon>
          </button>
          <el-icon :size="24" class="header-icon"><Connection /></el-icon>
          <div class="header-text">
            <h1 class="app-title">{{ t('appTitle') }}</h1>
            <span class="app-subtitle">{{ t('appSubtitle') }}</span>
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

    <el-container class="body-container">
      <!-- Sidebar -->
      <el-aside :width="sidebarOpen ? '280px' : '0px'" class="app-sidebar">
        <div v-show="sidebarOpen" class="sidebar-inner">
          <!-- Sidebar Header -->
          <div class="sidebar-header">
            <div class="sidebar-header-title">
              <el-icon :size="16"><Clock /></el-icon>
              <span>{{ t('sidebarHistory') }}</span>
            </div>
            <el-button
              v-if="historyList.length > 0"
              size="small"
              text
              type="danger"
              @click="clearHistory"
            >
              {{ t('clear') }}
            </el-button>
          </div>

          <!-- History List -->
          <div class="sidebar-history">
            <div v-if="historyList.length === 0" class="sidebar-empty">
              {{ t('sidebarEmpty') }}
            </div>
            <div
              v-for="(item, index) in historyList"
              :key="index"
              class="history-item"
              :class="{ active: reportContent === item.report }"
              @click="restoreHistory(item)"
            >
              <div class="history-item-icon">
                <el-icon :size="14"><Document /></el-icon>
              </div>
              <div class="history-item-content">
                <span class="history-item-title">{{ item.topic }}</span>
                <span class="history-item-time">{{ item.time }}</span>
              </div>
            </div>
          </div>

          <!-- Sidebar Bottom: Settings + Knowledge -->
          <div class="sidebar-bottom">
            <SettingsPanel
              ref="settingsRef"
              :theme="currentTheme"
              :lang="currentLang"
              @change="onSettingsChange"
              @update:theme="setTheme"
              @update:lang="setLang"
            />
            <KnowledgePanel />
          </div>
        </div>
      </el-aside>

      <!-- Main Content -->
      <el-main class="app-main">
        <div class="content-wrapper">
          <!-- Research Input -->
          <ResearchInput
            :loading="isResearching"
            @submit="handleSubmit"
          />

          <!-- Progress Panel (圆形进度 + 运行日志) -->
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
          @clear="handleClear"
            @followup="handleFollowUp"
          />
        </div>
      </el-main>
    </el-container>

    <!-- Footer -->
    <el-footer class="app-footer" height="40px">
      <span>CollabAgent MVP v2.0 &copy; 2026</span>
    </el-footer>
  </el-container>
  </el-config-provider>
</template>

<script setup>
import { ref, reactive, computed, onMounted, provide, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import en from 'element-plus/dist/locale/en.mjs'
import { Connection, Fold, Expand, Clock, Document } from '@element-plus/icons-vue'
import { LANG_SYMBOL, createLocale, messages } from './utils/i18n'
import ResearchInput from './components/ResearchInput.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import ReportPanel from './components/ReportPanel.vue'
import TokenUsagePanel from './components/TokenUsagePanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'

const HISTORY_KEY = 'collab-agent-history'

const sidebarOpen = ref(true)
const isResearching = ref(false)

// Theme & Language (sync with localStorage)
const THEME_KEY = 'collab-agent-theme'
const LANG_KEY = 'collab-agent-lang'
const currentTheme = ref(localStorage.getItem(THEME_KEY) || 'light')
const currentLang = ref(localStorage.getItem(LANG_KEY) || 'zh')
const currentLocale = computed(() => currentLang.value === 'en' ? en : zhCn)

// Apply theme on init
document.documentElement.classList.toggle('dark', currentTheme.value === 'dark')

// Provide i18n locale to all descendants
const currentLocaleMessages = createLocale(currentLang)
provide(LANG_SYMBOL, currentLocaleMessages)

// t() for App.vue template (can't use useI18n since we're the provider)
const t = (key) => (messages[currentLang.value] || messages.zh)[key] || key

function setTheme(t) {
  currentTheme.value = t
  localStorage.setItem(THEME_KEY, t)
  document.documentElement.classList.toggle('dark', t === 'dark')
}

function setLang(l) {
  currentLang.value = l
  localStorage.setItem(LANG_KEY, l)
  document.documentElement.lang = l
}
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
const currentUseLlm = ref(true)

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
  { key: 'research',   label: '', done: false, active: false },
  { key: 'writing',    label: '', done: false, active: false },
  { key: 'fact_check', label: '', done: false, active: false },
  { key: 'complete',   label: '', done: false, active: false },
])

// Keep stage labels in sync with current language
function updateStageLabels() {
  const labels = [t('stageResearch'), t('stageWriting'), t('stageFactCheck'), t('stageComplete')]
  progressStages.forEach((s, i) => { s.label = labels[i] })
}
updateStageLabels()
watch(currentLang, updateStageLabels)

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

function handleSubmit(topic, useLlm = true) {
  if (!topic.trim()) return

  currentUseLlm.value = useLlm
  isResearching.value = true
  errorMessage.value = ''
  reportContent.value = ''
  searchResults.value = []
  factCheckData.value = null
  currentTaskId.value = ''
  tokenUsage.value = null
  lastTopic.value = topic
  resetStages()

  addLog(`开始研究: "${topic}"`, 'info')
  currentStage.value = 'research'
  progressStages[0].active = true

  // Build SSE URL with optional provider config and LLM toggle
  let url = `/research/stream?topic=${encodeURIComponent(topic)}&use_llm=${useLlm}`
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
      // API 错误弹窗（401/超时/Key 错误等）
      const msg = errorMessage.value
      if (/API\s*Key|401|403|超时|api_key|auth/i.test(msg)) {
        ElMessageBox.alert(msg, 'LLM 调用错误', {
          confirmButtonText: '知道了',
          type: 'error',
          dangerouslyUseHTMLString: true,
          message: `<div style="line-height:1.8">
            <p>${msg}</p>
            <p style="font-size:13px;color:#909399;margin-top:8px">
              请检查「模型供应商」中的 API Key 和 Base URL 配置是否正确。
            </p>
          </div>`,
        })
      }
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

  // Merge provider config + LLM toggle into followup payload
  const extendedPayload = { ...payload, use_llm: currentUseLlm.value }
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
/* ── Root ── */
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color-page);
  overflow: hidden;
}

/* ── Header ── */
.app-header {
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
  z-index: 100;
  position: relative;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-toggle {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background .15s;
}

.sidebar-toggle:hover {
  background: var(--el-fill-color-light);
}

.header-icon {
  color: var(--el-color-primary);
}

.header-text {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.app-title {
  font-size: 17px;
  font-weight: 700;
  margin: 0;
  line-height: 1.2;
  color: var(--el-text-color-primary);
}

.app-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ── Body (sidebar + main) ── */
.body-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ── Sidebar ── */
.app-sidebar {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  transition: width .25s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-inner {
  width: 280px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}

.sidebar-header-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.sidebar-history {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
}

.sidebar-empty {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 32px 0;
}

.sidebar-history .history-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background .12s;
  margin-bottom: 2px;
}

.sidebar-history .history-item:hover {
  background: var(--el-fill-color-light);
}

.sidebar-history .history-item.active {
  background: var(--el-color-primary-light-9);
}

.history-item-icon {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.history-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item-title {
  font-size: 13px;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.history-item-time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.sidebar-bottom {
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 10px 12px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── Main ── */
.app-main {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.error-alert {
  margin-top: 4px;
}

/* ── Footer ── */
.app-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}
</style>
