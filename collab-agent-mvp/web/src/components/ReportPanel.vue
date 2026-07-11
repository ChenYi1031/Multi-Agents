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
          <el-button size="small" @click="copyReport" :icon="copyIcon">
            {{ copyText }}
          </el-button>
          <el-button size="small" @click="downloadReport">
            <el-icon><Download /></el-icon>
            下载 MD
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Link, Notebook, Download, Delete } from '@element-plus/icons-vue'
import { marked } from 'marked'

const props = defineProps({
  report: {
    type: String,
    default: '',
  },
  searchResults: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['clear'])

const showSearchResults = ref(true)
const copyText = ref('复制内容')
const copyIcon = ref('CopyDocument')

// Configure marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderedReport = computed(() => {
  if (!props.report) return ''
  return marked(props.report)
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

function downloadReport() {
  const blob = new Blob([props.report], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `research-report-${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.report-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-card,
.report-card {
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
</style>
