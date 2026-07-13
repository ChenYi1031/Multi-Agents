import { inject, computed } from 'vue'

const LANG_SYMBOL = Symbol('locale')

const messages = {
  zh: {
    appTitle: 'CollabAgent 协作研究员',
    appSubtitle: 'AI 专家协作研究平台',
    sidebarHistory: '研究历史',
    sidebarEmpty: '暂无研究历史',
    footer: 'CollabAgent MVP v2.0 © 2026',

    researchTitle: '输入研究主题',
    researchDesc: '输入你想研究的任何主题，AI 研究员将自动搜索信息并生成专业报告',
    researchPlaceholder: '请输入研究主题，例如：2026年全球人工智能发展趋势',
    startResearch: '开始研究',
    researching: '研究中...',
    llmLabel: 'LLM 参与（勾选后将搜索结果交给 AI 二次加工生成结构化报告）',
    hotTopics: '热门主题：',

    progressTitle: '研究进度',
    logTitle: '运行日志',
    logEmpty: '暂无事件',
    cancelResearch: '取消研究',
    stageResearch: '搜索研究',
    stageWriting: '撰写报告',
    stageFactCheck: '事实核查',
    stageComplete: '生成完成',
    eventsFormat: '条事件',

    searchResults: '搜索结果',
    countSuffix: '条',
    factCheckReport: '事实核查报告',
    score: '评分',
    followupTitle: '追问',
    followupDesc: '对当前报告内容有疑问？可以针对性地继续追问：',
    followupPlaceholder: '请输入追问内容',
    followupSubmit: '发送追问',
    followupLoading: '追问中...',
    collapse: '收起',
    expand: '展开',
    reportTitle: '研究报告',
    generated: '已生成',
    exportText: '导出',
    clearText: '清除',
    copyText: '复制内容',
    copied: '已复制',
    claimStatusVerified: '已验证',
    claimStatusPartial: '部分',
    claimStatusUnverified: '未验证',
    emptyReportDesc: '暂无报告内容，请输入研究主题开始',
    emptyProvider: '暂未配置供应商',
    addProvider: '添加供应商',
    editProvider: '编辑供应商',

    modelProvider: '模型供应商',
    add: '添加',
    theme: '主题',
    lang: '语言',
    light: '浅色',
    dark: '深色',
    chinese: '中文',
    english: 'English',

    knowledgeBase: '知识库',
    chunks: '块',
    uploadFile: '上传文件',
    clear: '清空',

    tokenUsage: 'Token 用量',
    inputTokens: '输入',
    outputTokens: '输出',
    callDetail: '调用详情',
    byAgent: '按 Agent',
    calls: '次调用',

    researcher: '搜索研究员',
    writer: '报告撰写员',
    total: '总计',
  },
  en: {
    appTitle: 'CollabAgent',
    appSubtitle: 'AI Collaborative Research',
    sidebarHistory: 'History',
    sidebarEmpty: 'No history yet',
    footer: 'CollabAgent MVP v2.0 © 2026',

    researchTitle: 'Research Topic',
    researchDesc: 'Enter any topic to research. AI agents will search and generate a professional report.',
    researchPlaceholder: 'e.g. Global AI trends in 2026',
    startResearch: 'Start',
    researching: 'Processing...',
    llmLabel: 'LLM Enhancement (AI processes search results into structured reports)',
    hotTopics: 'Hot Topics:',

    progressTitle: 'Progress',
    logTitle: 'Event Log',
    logEmpty: 'No events yet',
    cancelResearch: 'Cancel',
    stageResearch: 'Researching',
    stageWriting: 'Writing',
    stageFactCheck: 'Fact Check',
    stageComplete: 'Complete',
    eventsFormat: 'events',

    searchResults: 'Search Results',
    countSuffix: 'results',
    factCheckReport: 'Fact Check',
    score: 'Score',
    followupTitle: 'Follow-up',
    followupDesc: 'Have follow-up questions about the report?',
    followupPlaceholder: 'Enter your question',
    followupSubmit: 'Submit',
    followupLoading: 'Processing...',
    collapse: 'Collapse',
    expand: 'Expand',
    reportTitle: 'Report',
    generated: 'Generated',
    exportText: 'Export',
    clearText: 'Clear',
    copyText: 'Copy',
    copied: 'Copied',
    claimStatusVerified: 'Verified',
    claimStatusPartial: 'Partial',
    claimStatusUnverified: 'Unverified',
    emptyReportDesc: 'No report yet. Enter a topic to start.',
    emptyProvider: 'No provider configured',
    addProvider: 'Add Provider',
    editProvider: 'Edit Provider',

    modelProvider: 'Provider',
    add: 'Add',
    theme: 'Theme',
    lang: 'Language',
    light: 'Light',
    dark: 'Dark',
    chinese: '中文',
    english: 'English',

    knowledgeBase: 'Knowledge',
    chunks: 'chunks',
    uploadFile: 'Upload',
    clear: 'Clear',

    tokenUsage: 'Tokens',
    inputTokens: 'Input',
    outputTokens: 'Output',
    callDetail: 'Call Details',
    byAgent: 'By Agent',
    calls: 'calls',

    researcher: 'Researcher',
    writer: 'Writer',
    total: 'Total',
  },
}

export { LANG_SYMBOL, messages }

export function useI18n() {
  const currentMessages = inject(LANG_SYMBOL, null)
  const t = (key) => {
    if (!currentMessages?.value) return key
    return currentMessages.value[key] || key
  }
  return { t, locale: currentMessages }
}

export function createLocale(langRef) {
  return computed(() => messages[langRef.value] || messages.zh)
}
