<template>
  <el-card class="research-card" shadow="hover">
    <div class="research-form">
      <div class="form-header">
        <h2 class="form-title">
          <el-icon :size="20"><Promotion /></el-icon>
          {{ t('researchTitle') }}
        </h2>
        <p class="form-desc">
          {{ t('researchDesc') }}
        </p>
      </div>
      <div class="form-input-row">
        <el-input
          v-model="topic"
          :placeholder="t('researchPlaceholder')"
          :disabled="loading"
          size="large"
          clearable
          @keyup.enter="handleSubmit"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="!topic.trim()"
          @click="handleSubmit"
          class="submit-btn"
        >
          <el-icon v-if="!loading"><Document /></el-icon>
          <span v-if="loading">{{ t('researching') }}</span>
          <span v-else>{{ t('startResearch') }}</span>
        </el-button>
      </div>
      <div class="form-options">
        <el-checkbox v-model="useLlm" :disabled="loading" size="small">
          {{ t('llmLabel') }}
        </el-checkbox>
      </div>
      <!-- Example topics -->
      <div class="example-topics">
        <span class="example-label">{{ t('hotTopics') }}</span>
        <el-tag
          v-for="example in examples"
          :key="example"
          size="small"
          effect="plain"
          :disabled="loading"
          class="example-tag"
          @click="!loading && (topic = example)"
        >
          {{ example }}
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import { Promotion, Search, Document } from '@element-plus/icons-vue'
import { useI18n } from '../utils/i18n'

const emit = defineEmits(['submit'])
const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
})

const { t } = useI18n()

const topic = ref('')
const useLlm = ref(true)

const examples = [
  '2026年全球人工智能发展趋势',
  '量子计算在金融领域的应用前景',
  '碳中和目标下的新能源技术突破',
]

function handleSubmit() {
  if (topic.value.trim() && !props.loading) {
    emit('submit', topic.value.trim(), useLlm.value)
  }
}
</script>

<style scoped>
.research-card {
  border-radius: 12px;
}

.research-form {
  padding: 8px 0;
}

.form-header {
  margin-bottom: 20px;
}

.form-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: var(--el-text-color-primary);
}

.form-desc {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.form-input-row {
  display: flex;
  gap: 12px;
}

.form-input-row .el-input {
  flex: 1;
}

.submit-btn {
  min-width: 130px;
}

.example-topics {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.example-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.example-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  transform: scale(1.05);
}

.form-options {
  margin-top: 12px;
  display: flex;
  align-items: center;
}
</style>
