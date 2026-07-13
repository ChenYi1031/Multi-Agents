<template>
  <el-card class="knowledge-card" shadow="hover">
    <div class="knowledge-header" @click="expanded = !expanded">
      <div class="knowledge-title">
        <el-icon :size="18"><FolderOpened /></el-icon>
        <span>{{ t('knowledgeBase') }} (RAG)</span>
        <el-tag v-if="chunks.length" size="small" type="info">{{ chunks.length }} {{ t('chunks') }}</el-tag>
      </div>
      <el-icon :class="['chevron', { rotated: expanded }]"><ArrowDown /></el-icon>
    </div>
    <el-collapse-transition>
      <div v-show="expanded" class="knowledge-body">
        <!-- Upload -->
        <div class="upload-row">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :show-file-list="false"
            accept=".txt,.pdf"
            :disabled="uploading"
          >
            <el-button type="primary" size="small" :loading="uploading">
              <el-icon><Upload /></el-icon>
              {{ t('uploadFile') }} (.txt/.pdf)
            </el-button>
          </el-upload>
          <el-button
            v-if="chunks.length"
            size="small"
            type="danger"
            plain
            @click="handleClear"
          >
            <el-icon><Delete /></el-icon>
            {{ t('clear') }}
          </el-button>
        </div>

        <!-- Upload feedback -->
        <el-alert
          v-if="uploadMessage"
          :title="uploadMessage"
          :type="uploadMessageType"
          show-icon
          :closable="true"
          @close="uploadMessage = ''"
          class="upload-alert"
        />

        <!-- Chunks list -->
        <div v-if="chunks.length" class="chunks-list">
          <p class="chunks-summary">{{ chunks.length }} {{ t('chunks') }}</p>
          <div class="chunk-items">
            <div v-for="(c, i) in chunks.slice(0, 10)" :key="i" class="chunk-item">
              <span class="chunk-source">{{ c.source || '未知' }}</span>
              <span class="chunk-preview">{{ (c.content || '').slice(0, 60) }}...</span>
            </div>
            <div v-if="chunks.length > 10" class="chunk-more">
              还有 {{ chunks.length - 10 }} 块...
            </div>
          </div>
        </div>
        <div v-else class="empty-hint">
          <span class="empty-text">暂无知识文档</span>
        </div>
      </div>
    </el-collapse-transition>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FolderOpened, ArrowDown, Upload, Delete } from '@element-plus/icons-vue'
import { useI18n } from '../utils/i18n'

const { t } = useI18n()
const expanded = ref(false)
const uploading = ref(false)
const chunks = ref([])
const uploadMessage = ref('')
const uploadMessageType = ref('success')

const uploadUrl = '/knowledge/upload'
const uploadHeaders = { 'Accept': 'application/json' }

onMounted(async () => {
  await fetchChunks()
})

async function fetchChunks() {
  try {
    const res = await fetch('/knowledge/list')
    const data = await res.json()
    chunks.value = data.chunks || []
  } catch { /* ignore */ }
}

function handleUploadSuccess(res) {
  uploading.value = false
  if (res.status === 'ok') {
    uploadMessage.value = `✅ ${res.filename} 上传成功 (${res.chunks_count || '?'} 块)`
    uploadMessageType.value = 'success'
    fetchChunks()
  } else {
    uploadMessage.value = `❌ 上传失败: ${res.detail || '未知错误'}`
    uploadMessageType.value = 'error'
  }
}

function handleUploadError(err) {
  uploading.value = false
  uploadMessage.value = `❌ 上传失败: ${err.message || '网络错误'}`
  uploadMessageType.value = 'error'
}

async function handleClear() {
  try {
    await fetch('/knowledge/clear', { method: 'DELETE' })
    chunks.value = []
    uploadMessage.value = '✅ 知识库已清空'
    uploadMessageType.value = 'success'
  } catch (e) {
    uploadMessage.value = `❌ 清空失败: ${e.message}`
    uploadMessageType.value = 'error'
  }
}
</script>

<style scoped>
.knowledge-card {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  border-radius: 8px;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background .12s;
}

.knowledge-header:hover {
  background: var(--el-fill-color-light);
}

.knowledge-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.chevron {
  transition: transform 0.3s ease;
  font-size: 14px;
  color: var(--el-text-color-placeholder);
}

.chevron.rotated {
  transform: rotate(180deg);
}

.knowledge-body {
  padding: 8px 8px 0;
}

.upload-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.upload-alert {
  margin-bottom: 8px;
}

.chunks-summary {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0 0 6px 0;
}

.chunk-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chunk-item {
  background: var(--el-fill-color);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
  line-height: 1.4;
}

.chunk-source {
  font-weight: 500;
  color: var(--el-color-primary);
  display: block;
  margin-bottom: 2px;
}

.chunk-preview {
  color: var(--el-text-color-secondary);
}

.chunk-more {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 4px 0;
}

.empty-hint {
  padding: 8px 0;
}

.empty-text {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
