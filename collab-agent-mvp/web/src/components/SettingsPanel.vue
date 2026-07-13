<template>
  <el-card class="settings-card" shadow="hover">
    <!-- Header (always visible) -->
    <div class="settings-header" @click="expanded = !expanded">
      <div class="settings-title">
        <el-icon :size="16"><Setting /></el-icon>
        <span>{{ t('modelProvider') }}</span>
        <el-tag v-if="activeProvider" size="small" type="success" effect="light">
          {{ activeProvider.name }}
        </el-tag>
      </div>
      <div class="settings-header-right">
        <el-button size="small" text @click.stop="openAddDialog">
          <el-icon><Plus /></el-icon> {{ t('add') }}
        </el-button>
        <el-icon :class="['chevron', { rotated: expanded }]"><ArrowDown /></el-icon>
      </div>
    </div>

    <!-- Collapsible body -->
    <el-collapse-transition>
      <div v-show="expanded" class="settings-body">

        <!-- ── General Preferences ── -->
        <div class="prefs-section">
          <div class="pref-row">
            <span class="pref-label">{{ t('theme') }}</span>
            <el-radio-group :model-value="theme" size="small" @change="$emit('update:theme', $event)">
              <el-radio-button value="light">☀️ {{ t('light') }}</el-radio-button>
              <el-radio-button value="dark">🌙 {{ t('dark') }}</el-radio-button>
            </el-radio-group>
          </div>
          <div class="pref-row">
            <span class="pref-label">{{ t('lang') }}</span>
            <el-radio-group :model-value="lang" size="small" @change="$emit('update:lang', $event)">
              <el-radio-button value="zh">{{ t('chinese') }}</el-radio-button>
              <el-radio-button value="en">{{ t('english') }}</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <el-divider style="margin:8px 0" />

        <!-- ── Provider Section ── -->
        <div v-if="providers.length === 0" class="empty-hint">
          <el-empty :description="t('emptyProvider')" :image-size="60">
            <el-button type="primary" size="small" @click="openAddDialog">{{ t('addProvider') }}</el-button>
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
    <el-dialog v-model="dialogVisible" :title="editingProvider ? t('editProvider') : t('addProvider')" width="520px" :close-on-click-modal="false">
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
import { useI18n } from '../utils/i18n'

const props = defineProps({
  theme: { type: String, default: 'light' },
  lang: { type: String, default: 'zh' },
})
const emit = defineEmits(['change', 'update:theme', 'update:lang'])

const { t } = useI18n()

const expanded = ref(false)
const providers = ref([])
const activeProviderId = ref('')
const dialogVisible = ref(false)
const editingProvider = ref(null)
const newModelName = ref('')
const loading = ref(false)

const form = reactive({
  name: '', baseUrl: '', apiKey: '', apiFormat: 'openai', models: [], selectedModel: '',
})

const activeProvider = computed(() => providers.value.find(p => p.id === activeProviderId.value) || null)
const formValid = computed(() => form.name.trim() && form.baseUrl.trim() && form.apiKey.trim() && form.models.length > 0)

onMounted(loadProviders)

async function loadProviders() {
  loading.value = true
  try {
    const res = await fetch('/settings')
    if (res.ok) {
      const data = await res.json()
      providers.value = data.providers || []
      activeProviderId.value = data.active_provider_id || ''
    } else {
      // fallback to empty
      providers.value = []
    }
  } catch {
    providers.value = []
  } finally {
    loading.value = false
  }
  // validate activeProviderId
  if (activeProviderId.value && !providers.value.find(p => p.id === activeProviderId.value)) {
    activeProviderId.value = providers.value.length > 0 ? providers.value[0].id : ''
  }
}

async function saveToStorage() {
  try {
    await fetch('/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        providers: providers.value,
        active_provider_id: activeProviderId.value,
      }),
    })
  } catch (e) {
    console.error('保存配置失败', e)
  }
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
.settings-card {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  border-radius: 8px;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background .12s;
}

.settings-header:hover {
  background: var(--el-fill-color-light);
}

.settings-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.settings-header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chevron {
  transition: transform 0.3s ease;
  font-size: 14px;
  color: var(--el-text-color-placeholder);
}

.chevron.rotated {
  transform: rotate(180deg);
}

.settings-body {
  padding: 8px 8px 0;
}

.prefs-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.pref-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.empty-hint {
  padding: 8px 0;
}

.provider-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
  transition: all 0.2s;
  background: var(--el-bg-color);
}

.provider-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.provider-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.provider-actions {
  display: flex;
  gap: 2px;
}

.provider-details {
  padding-left: 24px;
}

.detail-row {
  display: flex;
  gap: 6px;
  font-size: 12px;
  margin-bottom: 2px;
}

.detail-label {
  color: var(--el-text-color-secondary);
  min-width: 60px;
  flex-shrink: 0;
}

.detail-value {
  color: var(--el-text-color-primary);
  word-break: break-all;
  font-size: 12px;
}

.model-tag {
  margin-right: 2px;
  margin-bottom: 2px;
}

.models-input-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.models-input-row .el-input {
  flex: 1;
}

.model-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.model-tag-clickable {
  cursor: pointer;
}
</style>
