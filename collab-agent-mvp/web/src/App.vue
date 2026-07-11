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
        <!-- Research Input -->
        <ResearchInput
          :loading="isResearching"
          @submit="handleSubmit"
        />

        <!-- Progress Panel (visible during research) -->
        <ProgressPanel
          v-if="isResearching || progressLog.length > 0"
          :progress-stages="progressStages"
          :progress-log="progressLog"
          :current-stage="currentStage"
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
          @clear="handleClear"
        />
      </div>
    </el-main>

    <!-- Footer -->
    <el-footer class="app-footer" height="48px">
      <span>CollabAgent MVP v1.0 &copy; 2026</span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Connection } from '@element-plus/icons-vue'
import ResearchInput from './components/ResearchInput.vue'
import ProgressPanel from './components/ProgressPanel.vue'
import ReportPanel from './components/ReportPanel.vue'

const isResearching = ref(false)
const errorMessage = ref('')
const reportContent = ref('')
const searchResults = ref([])
const progressLog = ref([])
const currentStage = ref('idle')
const backendStatus = ref('checking')

const progressStages = reactive([
  { key: 'research', label: '信息搜索', icon: 'Search', done: false, active: false },
  { key: 'writing', label: '报告撰写', icon: 'Edit', done: false, active: false },
  { key: 'complete', label: '生成完成', icon: 'Check', done: false, active: false },
])

onMounted(async () => {
  await checkHealth()
})

async function checkHealth() {
  try {
    const res = await fetch('/health')
    const data = await res.json()
    backendStatus.value = data.status
  } catch {
    backendStatus.value = 'error'
  }
}

function resetStages() {
  progressStages.forEach(s => {
    s.done = false
    s.active = false
  })
  progressLog.value = []
  currentStage.value = 'idle'
}

function addLog(message, type = 'info') {
  progressLog.value.push({
    id: Date.now() + Math.random(),
    message,
    type,
    time: new Date().toLocaleTimeString(),
  })
}

function handleSubmit(topic) {
  if (!topic.trim()) return

  isResearching.value = true
  errorMessage.value = ''
  reportContent.value = ''
  searchResults.value = []
  resetStages()

  addLog(`开始研究主题: "${topic}"`, 'info')
  currentStage.value = 'research'
  progressStages[0].active = true

  const eventSource = new EventSource(
    `/research/stream?topic=${encodeURIComponent(topic)}`
  )

  eventSource.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    const { stage, message } = data

    addLog(message, 'progress')

    if (stage === 'research') {
      currentStage.value = 'research'
      progressStages[0].active = true
      progressStages[0].done = false
    } else if (stage === 'research_done') {
      progressStages[0].done = true
      progressStages[0].active = false
      currentStage.value = 'research_done'
      if (data.search_results) {
        searchResults.value = data.search_results
      }
    } else if (stage === 'writing') {
      currentStage.value = 'writing'
      progressStages[1].active = true
      progressStages[1].done = false
    } else if (stage === 'writing_done') {
      progressStages[1].done = true
      progressStages[1].active = false
      currentStage.value = 'writing_done'
    }
  })

  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data)
    reportContent.value = data.report
    if (data.search_results) {
      searchResults.value = data.search_results
    }
    progressStages[2].done = true
    currentStage.value = 'complete'
    addLog('✅ 研究报告生成完成！', 'success')
    isResearching.value = false
    eventSource.close()
  })

  eventSource.addEventListener('error', (e) => {
    // Try to parse error message if available
    try {
      const data = JSON.parse((e.data || '{}'))
      errorMessage.value = data.message || '研究过程发生错误，请重试'
    } catch {
      // If EventSource itself errors (connection issue)
      if (eventSource.readyState === EventSource.CLOSED) {
        errorMessage.value = '连接中断，请检查后端服务是否运行'
      } else {
        errorMessage.value = '研究过程发生错误，请重试'
      }
    }
    addLog(`❌ ${errorMessage.value}`, 'error')
    isResearching.value = false
    eventSource.close()
  })
}

function handleClear() {
  reportContent.value = ''
  searchResults.value = []
  progressLog.value = []
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
</style>
