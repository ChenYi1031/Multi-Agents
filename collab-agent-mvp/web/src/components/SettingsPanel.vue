<template>
  <el-card class="settings-card" shadow="hover">
    <!-- Header (always visible) -->
    <div class="settings-header" @click="expanded = !expanded">
      <div class="settings-title">
        <el-icon :size="16"><Setting /></el-icon>
        <span>模型供应商</span>
        <el-tag v-if="activeProvider" size="small" type="success" effect="light">
          {{ activeProvider.name }}
        </el-tag>
      </div>
      <div class="settings-header-right">
        <el-button size="small" text @click.stop="openAddDialog">
          <el-icon><Plus /></el-icon> 添加
        </el-button>
        <el-icon :class="['chevron', { rotated: expanded }]"><ArrowDown /></el-icon>
      </div>
    </div>

    <!-- Collapsible body -->
    <el-collapse-transition>
      <div v-show="expanded" class="settings-body">
        <div v-if="providers.length === 0" class="empty-hint">
          <el-empty description="暂未配置供应商" :image-size="60">
            <el-button type="primary" size="small" @click="openAddDialog">添加供应商</el-button>
          </el-empty>
        </div>

        <div v-for="p in providers" :key="p.id" class="provider-card" :class="{ active: activeProviderId === p.id }">
          <div class="provider-header">
            <div class="provider-name-row">
              <el-radio v-model="activeProviderId" :value="p.id" @change="onActiveChange">
                <strong>{{ p.name }}</strong>
              </el-radio>
              <el-tag size="small" type="info" effect="plain">{{ p.apiFormat === 'anthropic' ? 'Anthropic' : 'OpenAI' }}</el-tag>
            </div>
            <div class="provider-actions">
              <el-button size="small" text @click="openEditDialog(p)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" text type="danger" @click="removeProvider(p.id)"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
          <div class="provider-details">
            <div class="detail-row">
              <span class="detail-label">Base URL</span>
              <span class="detail-value">{{ p.baseUrl }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">API Key</span>
              <span class="detail-value">{{ maskKey(p.apiKey) }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">模型</span>
              <span class="detail-value">
                <el-tag v-for="m in p.models" :key="m" size="small" :type="m === p.selectedModel ? 'primary' : 'info'" effect="plain" class="model-tag">{{ m }}</el-tag>
              </span>
            </div>
          </div>
        </div>
      </div>
    </el-collapse-transition>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingProvider ? '编辑供应商' : '添加供应商'" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top" size="small">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：智谱 GLM、DeepSeek" />
        </el-form-item>
        <el-form-item label="Base URL" required>
          <el-input v-model="form.baseUrl" placeholder="https://api.example.com/v1" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="form.apiKey" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="API 格式" required>
          <el-select v-model="form.apiFormat" style="width:100%">
            <el-option label="OpenAI 兼容 (/v1/chat/completions)" value="openai" />
            <el-option label="Anthropic Messages (/v1/messages)" value="anthropic" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型列表">
          <div class="models-input-row">
            <el-input v-model="newModelName" placeholder="输入模型名称，回车添加" @keyup.enter="addModel" />
            <el-button @click="addModel" :disabled="!newModelName.trim()" type="primary">添加</el-button>
          </div>
          <div v-if="form.models.length" class="model-tags">
            <el-tag v-for="(m, i) in form.models" :key="i" closable :type="m === form.selectedModel ? 'primary' : 'info'" @close="removeModel(i)" @click="form.selectedModel = m" class="model-tag-clickable">{{ m }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="默认模型" v-if="form.models.length">
          <el-select v-model="form.selectedModel" style="width:100%">
            <el-option v-for="m in form.models" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProvider" :disabled="!formValid">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Setting, ArrowDown, Plus, Edit, Delete } from '@element-plus/icons-vue'

const STORAGE_KEY = 'collab-agent-providers'
const ACTIVE_KEY = 'collab-agent-active-provider'

const emit = defineEmits(['change'])

const expanded = ref(false)
const providers = ref([])
const activeProviderId = ref('')
const dialogVisible = ref(false)
const editingProvider = ref(null)
const newModelName = ref('')

const form = reactive({
  name: '', baseUrl: '', apiKey: '', apiFormat: 'openai', models: [], selectedModel: '',
})

const activeProvider = computed(() => providers.value.find(p => p.id === activeProviderId.value) || null)
const formValid = computed(() => form.name.trim() && form.baseUrl.trim() && form.apiKey.trim() && form.models.length > 0)

onMounted(loadProviders)

function loadProviders() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    providers.value = raw ? JSON.parse(raw) : []
    activeProviderId.value = localStorage.getItem(ACTIVE_KEY) || ''
    if (activeProviderId.value && !providers.value.find(p => p.id === activeProviderId.value)) {
      activeProviderId.value = providers.value.length > 0 ? providers.value[0].id : ''
    }
  } catch { providers.value = [] }
}

function saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(providers.value))
    if (activeProviderId.value) localStorage.setItem(ACTIVE_KEY, activeProviderId.value)
    else localStorage.removeItem(ACTIVE_KEY)
  } catch { /* ok */ }
}

function openAddDialog() {
  editingProvider.value = null
  form.name = ''; form.baseUrl = ''; form.apiKey = ''; form.apiFormat = 'openai'; form.models = []; form.selectedModel = ''
  newModelName.value = ''
  dialogVisible.value = true
}

function openEditDialog(p) {
  editingProvider.value = p
  form.name = p.name; form.baseUrl = p.baseUrl; form.apiKey = p.apiKey; form.apiFormat = p.apiFormat
  form.models = [...p.models]; form.selectedModel = p.selectedModel
  newModelName.value = ''
  dialogVisible.value = true
}

function saveProvider() {
  if (!formValid.value) return
  const provider = {
    id: editingProvider.value ? editingProvider.value.id : Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    name: form.name.trim(),
    baseUrl: form.baseUrl.trim().replace(/\/+$/, ''),
    apiKey: form.apiKey.trim(),
    apiFormat: form.apiFormat,
    models: [...form.models],
    selectedModel: form.selectedModel || form.models[0],
  }
  if (editingProvider.value) {
    const idx = providers.value.findIndex(p => p.id === editingProvider.value.id)
    if (idx !== -1) providers.value[idx] = provider
  } else {
    providers.value.push(provider)
    if (!activeProviderId.value) activeProviderId.value = provider.id
  }
  saveToStorage()
  dialogVisible.value = false
  emitChange()
}

function removeProvider(id) {
  providers.value = providers.value.filter(p => p.id !== id)
  if (activeProviderId.value === id) activeProviderId.value = providers.value.length > 0 ? providers.value[0].id : ''
  saveToStorage()
  emitChange()
}

function addModel() {
  const m = newModelName.value.trim()
  if (m && !form.models.includes(m)) {
    form.models.push(m)
    if (!form.selectedModel) form.selectedModel = m
  }
  newModelName.value = ''
}

function removeModel(index) {
  const removed = form.models[index]
  form.models.splice(index, 1)
  if (form.selectedModel === removed) form.selectedModel = form.models.length > 0 ? form.models[0] : ''
}

function onActiveChange() { saveToStorage(); emitChange() }
function maskKey(key) {
  if (!key || key.length < 8) return '***'
  return key.slice(0, 4) + '****' + key.slice(-4)
}
function emitChange() { emit('change', { provider: activeProvider.value }) }

defineExpose({
  getActiveConfig: () => {
    const p = activeProvider.value
    if (!p) return null
    return { api_base_url: p.baseUrl, api_key: p.apiKey, api_format: p.apiFormat, model_name: p.selectedModel }
  },
})
</script>

<style scoped>
.settings-card { border-radius: 12px; }
.settings-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
.settings-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; }
.settings-header-right { display: flex; align-items: center; gap: 8px; }
.chevron { transition: transform 0.3s ease; }
.chevron.rotated { transform: rotate(180deg); }
.settings-body { padding-top: 16px; }
.empty-hint { padding: 12px 0; }
.provider-card { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; transition: all 0.2s; }
.provider-card.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.provider-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.provider-name-row { display: flex; align-items: center; gap: 8px; }
.provider-actions { display: flex; gap: 4px; }
.provider-details { padding-left: 28px; }
.detail-row { display: flex; gap: 8px; font-size: 13px; margin-bottom: 4px; }
.detail-label { color: var(--el-text-color-secondary); min-width: 70px; flex-shrink: 0; }
.detail-value { color: var(--el-text-color-primary); word-break: break-all; }
.model-tag { margin-right: 4px; margin-bottom: 4px; }
.models-input-row { display: flex; gap: 8px; margin-bottom: 8px; }
.models-input-row .el-input { flex: 1; }
.model-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.model-tag-clickable { cursor: pointer; }
</style>
