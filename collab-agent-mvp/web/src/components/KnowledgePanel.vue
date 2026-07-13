<template>
  <el-card class="knowledge-card" shadow="hover">
    <div class="knowledge-header" @click="expanded = !expanded">
      <div class="knowledge-title">
        <el-icon :size="18"><FolderOpened /></el-icon>
        <span>知识库 (RAG)</span>
        <el-tag v-if="chunks.length" size="small" type="info">{{ chunks.length }} 块</el-tag>
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
              上传文件 (.txt/.pdf)
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
            清空
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
          <p class="chunks-summary">共 {{ chunks.length }} 个文档块，研究时将自动检索相关知识</p>
          <el-table :data="chunks" size="small" stripe max-height="300">
            <el-table-column prop="source" label="来源" width="150" show-overflow-tooltip />
            <el-table-column prop="content" label="内容摘要" min-width="250" show-overflow-tooltip />
            <el-table-column prop="chunk_index" label="#" width="50" />
          </el-table>
        </div>
        <div v-else class="empty-hint">
          <el-empty description="尚未上传知识文档" :image-size="60" />
        </div>
      </div>
    </el-collapse-transition>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FolderOpened, ArrowDown, Upload, Delete } from '@element-plus/icons-vue'

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
  border-radius: 12px;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.knowledge-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.chevron {
  transition: transform 0.3s ease;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.knowledge-body {
  padding-top: 16px;
}

.upload-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.upload-alert {
  margin-bottom: 12px;
}

.chunks-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 8px 0;
}

.empty-hint {
  padding: 16px 0;
}
</style>
