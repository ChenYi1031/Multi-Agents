<template>
  <div class="report-section">
    <!-- Search Results -->
    <el-card v-if="searchResults.length > 0" class="result-card" shadow="hover">
      <div class="card-header">
        <h3 class="card-title">
          <el-icon :size="18"><Link /></el-icon>
          搜索结果（{{ searchResults.length }} 条）
        </h3>
        <el-button size="small" text @click="showSearchResults = !showSearchResults">
          {{ showSearchResults ? '收起' : '展开' }}
        </el-button>
      </div>
      <el-collapse-transition>
        <div v-show="showSearchResults">
          <el-table :data="searchResults" stripe style="width: 100%" size="small">
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="summary" label="摘要" min-width="300" show-overflow-tooltip />
            <el-table-column prop="source" label="来源" min-width="200">
              <template #default="{ row }">
                <el-link
                  v-if="row.source"
                  :href="row.source"
                  target="_blank"
                  type="primary"
                  :underline="false"
                >
                  {{ row.source.length > 40 ? row.source.slice(0, 40) + '...' : row.source }}
                </el-link>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-collapse-transition>
    </el-card>

    <!-- Fact-Check Report -->
    <el-card v-if="factCheck && factCheck.total_claims > 0" class="fact-check-card" shadow="hover">
      <div class="card-header">
        <h3 class="card-title">
          <el-icon :size="18"><Finished /></el-icon>
          事实核查报告
        </h3>
        <div class="fact-check-score">
          <el-tag :type="scoreType" size="small" effect="dark">
            评分 {{ factCheck.score }}/10
          </el-tag>
          <el-button size="small" text @click="showFactCheck = !showFactCheck">
            {{ showFactCheck ? '收起' : '展开' }}
          </el-button>
        </div>
      </div>
      <el-collapse-transition>
        <div v-show="showFactCheck">
          <div class="fact-check-stats">
            <el-statistic title="已验证" :value="factCheck.verified" />
            <el-statistic title="部分验证" :value="factCheck.partial" />
            <el-statistic title="未验证" :value="factCheck.unverified" />
          </div>
          <el-table v-if="factCheck.details && factCheck.details.length" :data="factCheck.details" size="small" stripe style="margin-top: 12px">
            <el-table-column prop="claim" label="主张" min-width="250" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'verified' ? 'success' : row.status === 'partial' ? 'warning' : 'danger'"
                  size="small"
                  effect="plain"
                >
                  {{ row.status === 'verified' ? '已验证' : row.status === 'partial' ? '部分' : '未验证' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="evidence" label="证据" min-width="200" show-overflow-tooltip />
            <el-table-column prop="suggestion" label="建议" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>
      </el-collapse-transition>
    </el-card>

    <!-- Report Display -->
    <el-card class="report-card" shadow="hover">
      <div class="card-header report-header">
        <div class="header-left">
          <h3 class="card-title">
            <el-icon :size="18"><Notebook /></el-icon>
            研究报告
          </h3>
          <el-tag type="success" size="small" effect="light" v-if="report">
            已生成
          </el-tag>
        </div>
        <div class="header-actions">
          <el-dropdown v-if="report" trigger="click" @command="handleExport">
            <el-button size="small" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="html">导出 HTML（可打印 PDF）</el-dropdown-item>
                <el-dropdown-item command="markdown">导出 Markdown</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" @click="copyReport" :icon="copyIcon">
            {{ copyText }}
          </el-button>
          <el-button size="small" type="danger" plain @click="$emit('clear')">
            <el-icon><Delete /></el-icon>
            清除
          </el-button>
        </div>
      </div>
      <div class="report-body">
        <div v-if="!report" class="report-empty">
          <el-empty description="暂无报告内容，请输入研究主题开始" />
        </div>
        <div v-else class="report-content" v-html="renderedReport" />
      </div>
    </el-card>

    <!-- Follow-up Question -->
    <el-card v-if="report" class="followup-card" shadow="hover">
      <div class="card-header">
        <h3 class="card-title">
          <el-icon :size="18"><ChatLineSquare /></el-icon>
          追问
        </h3>
        <el-button size="small" text @click="showFollowUp = !showFollowUp">
          {{ showFollowUp ? '收起' : '展开' }}
        </el-button>
      </div>
      <el-collapse-transition>
        <div v-show="showFollowUp" class="followup-body">
          <p class="followup-desc">基于当前研究报告发起追问，AI 将增量搜索并更新报告</p>
          <div class="followup-input-row">
            <el-input
              v-model="followUpQuestion"
              placeholder="输入追问内容…"
              :disabled="followUpLoading"
              size="large"
              clearable
              @keyup.enter="handleFollowUp"
            />
            <el-button
              type="primary"
              size="large"
              :loading="followUpLoading"
              :disabled="!followUpQuestion.trim()"
              @click="handleFollowUp"
            >
              追问
            </el-button>
          </div>
        </div>
      </el-collapse-transition>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Link, Notebook, Download, Delete, Finished, ChatLineSquare } from '@element-plus/icons-vue'
import { marked } from 'marked'

const props = defineProps({
  report: { type: String, default: '' },
  searchResults: { type: Array, default: () => [] },
  factCheck: { type: Object, default: () => null },
  topic: { type: String, default: '' },
  modelName: { type: String, default: '' },
  searchSource: { type: String, default: '' },
})

const emit = defineEmits(['clear', 'followup'])

const showSearchResults = ref(true)
const showFactCheck = ref(true)
const showFollowUp = ref(false)
const copyText = ref('复制内容')
const copyIcon = ref('CopyDocument')
const exporting = ref(false)
const followUpQuestion = ref('')
const followUpLoading = ref(false)

marked.setOptions({ breaks: true, gfm: true })

const renderedReport = computed(() => {
  if (!props.report) return ''
  return marked(props.report)
})

const scoreType = computed(() => {
  if (!props.factCheck) return 'info'
  const s = props.factCheck.score || 0
  if (s >= 8) return 'success'
  if (s >= 5) return 'warning'
  return 'danger'
})

function copyReport() {
  navigator.clipboard.writeText(props.report).then(() => {
    copyText.value = '已复制'
    copyIcon.value = 'Check'
    setTimeout(() => {
      copyText.value = '复制内容'
      copyIcon.value = 'CopyDocument'
    }, 2000)
  })
}

async function handleExport(format) {
  exporting.value = true
  try {
    const res = await fetch(`/research/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: props.report }),
    })
    if (!res.ok) throw new Error(`导出失败: ${res.status}`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = format === 'html' ? 'research-report.html' : 'research-report.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    exporting.value = false
  }
}

async function handleFollowUp() {
  if (!followUpQuestion.value.trim() || followUpLoading.value) return
  followUpLoading.value = true
  try {
    emit('followup', {
      topic: props.topic,
      followup_question: followUpQuestion.value.trim(),
      previous_report: props.report,
      search_results: props.searchResults,
      model_name: props.modelName,
      search_source: props.searchSource,
    })
    followUpQuestion.value = ''
  } finally {
    followUpLoading.value = false
  }
}
</script>

<style scoped>
.report-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-card,
.report-card,
.fact-check-card,
.followup-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.report-header .header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-header .header-actions {
  display: flex;
  gap: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.report-body {
  min-height: 200px;
}

.report-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.report-content {
  line-height: 1.8;
  padding: 8px;
}

.fact-check-stats {
  display: flex;
  gap: 32px;
  margin-top: 8px;
}

.fact-check-score {
  display: flex;
  align-items: center;
  gap: 8px;
}

.followup-body {
  padding-top: 4px;
}

.followup-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px 0;
}

.followup-input-row {
  display: flex;
  gap: 12px;
}

.followup-input-row .el-input {
  flex: 1;
}
</style>
