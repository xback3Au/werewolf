<template>
  <div class="analysis-progress">
    <!-- Timer Banner -->
    <div class="timer-banner" v-if="isAnalyzing">
      <div class="timer-display">
        <el-icon class="timer-icon" :size="24"><Timer /></el-icon>
        <span class="timer-label">分析用时</span>
        <span class="timer-value">{{ formatDuration(elapsedSeconds) }}</span>
      </div>
      <div class="stage-timer" v-if="currentStage">
        <span class="stage-label">{{ currentStage.name }}</span>
        <span class="stage-time">已进行 {{ currentStageSeconds }} 秒</span>
      </div>
    </div>

    <!-- Stage Progress Indicator -->
    <el-card class="progress-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><List /></el-icon>
            分析进度
            <el-tag v-if="!isAnalyzing && hasResult" type="success" effect="dark" size="small">
              已完成
            </el-tag>
          </span>
          <div class="header-actions">
            <el-button v-if="!isAnalyzing && hasResult" type="primary" size="small" @click="emit('viewResults')" :icon="View">
              查看完整结果
            </el-button>
            <el-button v-if="isAnalyzing" type="danger" size="small" @click="cancelAnalysis" :icon="CircleClose">
              取消
            </el-button>
          </div>
        </div>
      </template>

      <div class="steps-container">
        <el-steps :active="currentStageNum" finish-status="success" align-center>
          <el-step v-for="stage in stages" :key="stage.stage" :title="stage.name"
            :description="getStageStatus(stage)" :status="getStepStatus(stage)"
            @click="showStageResult(stage)">
            <template #icon>
              <el-icon v-if="stage.status === 'running'" class="is-loading spin-icon">
                <Loading />
              </el-icon>
              <el-icon v-else-if="stage.status === 'completed'" class="success-icon">
                <CircleCheck />
              </el-icon>
              <el-icon v-else class="pending-icon">
                <CircleCheck />
              </el-icon>
            </template>
          </el-step>
        </el-steps>
      </div>

      <!-- Stage Result Preview Dialog -->
      <el-dialog
        v-model="stageResultVisible"
        :title="`${selectedStage?.name} - 结果预览`"
        width="900px"
        top="5vh"
        destroy-on-close
        class="stage-result-dialog"
      >
        <div v-if="selectedStage?.result" class="stage-preview">
          <el-alert type="success" :closable="false" show-icon class="stage-alert">
            <template #title>
              {{ selectedStage.name }} 已完成
              <el-button
                size="small"
                link
                type="primary"
                @click="showRawJSON = !showRawJSON"
                class="json-toggle"
              >
                {{ showRawJSON ? '隐藏原始JSON' : '查看原始JSON' }}
              </el-button>
            </template>
          </el-alert>

          <!-- 可视化展示 -->
          <div v-show="!showRawJSON" class="visual-preview">
            <Stage1ResultView v-if="selectedStage.stage === 1" :result="selectedStage.result" />
            <Stage2ResultView v-else-if="selectedStage.stage === 2" :result="selectedStage.result" />
            <Stage3ResultView v-else-if="selectedStage.stage === 3" :result="selectedStage.result" />
          </div>

          <!-- 原始JSON -->
          <div v-show="showRawJSON" class="preview-content">
            <pre>{{ formatJSON(selectedStage.result) }}</pre>
          </div>
        </div>
      </el-dialog>

      <!-- Current Action（只在分析中显示） -->
      <div v-if="isAnalyzing && currentStage" class="current-action">
        <el-alert :title="`当前阶段：${currentStage.name}`" type="primary" :closable="false" show-icon>
          <template #default>
            <div class="action-detail">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ currentAction }}</span>
              <span class="stage-timer-inline" v-if="currentStageSeconds > 0">
                ({{ currentStageSeconds }}s)
              </span>
            </div>
          </template>
        </el-alert>
      </div>
    </el-card>

    <!-- Main Content Area -->
    <div class="content-grid">
      <!-- Left: Real-time Reasoning & Content -->
      <el-card class="reasoning-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="header-title">
              <el-icon><ChatDotRound /></el-icon>
              实时深度思考
            </span>
            <div class="header-actions">
              <el-tooltip content="显示AI分析过程中的思考内容" placement="top">
                <el-icon class="help-icon"><InfoFilled /></el-icon>
              </el-tooltip>
              <el-checkbox v-model="autoScroll" size="small">自动滚动</el-checkbox>
              <el-button size="small" @click="clearLog" :icon="Delete">清空</el-button>
            </div>
          </div>
        </template>

        <div ref="reasoningContainer" class="reasoning-container">
          <!-- 思考过程（按阶段分组显示） -->
          <div v-for="stageGroup in mergedReasoningLogByStage" :key="stageGroup.stage" class="reasoning-section">
            <div class="section-header" @click="toggleReasoningCollapse(stageGroup.stage)">
              <el-icon><ArrowDown v-if="!isReasoningCollapsedForStage(stageGroup.stage)" /><ArrowRight v-else /></el-icon>
              <el-tag size="small" :type="getStageTagType(stageGroup.stage)" effect="light">Stage {{ stageGroup.stage }}</el-tag>
              <span>思考过程</span>
              <el-tag v-if="isReasoningCollapsedForStage(stageGroup.stage)" size="small" type="info">已折叠</el-tag>
            </div>
            <div v-show="!isReasoningCollapsedForStage(stageGroup.stage)" class="reasoning-entries">
              <div v-for="(entry, idx) in stageGroup.entries" :key="`r-${stageGroup.stage}-${idx}`" class="reasoning-entry"
                :class="`stage-${entry.stage}`">
                <div class="entry-header">
                  <span class="timestamp">{{ formatTime(entry.timestamp) }}</span>
                </div>
                <div class="entry-content-wrapper">
                  <div class="entry-content" :class="{ 'expanded': expandedEntries.has(`r-${stageGroup.stage}-${idx}`) }">
                    {{ entry.content }}
                  </div>
                  <el-button
                    v-if="entry.content.length > 100"
                    size="small"
                    link
                    @click="toggleExpand(`r-${stageGroup.stage}-${idx}`)"
                    class="expand-btn"
                  >
                    {{ expandedEntries.has(`r-${stageGroup.stage}-${idx}`) ? '收起' : '展开' }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 正式输出内容 -->
          <div v-if="mergedContentLog.length > 0" class="content-section">
            <div class="section-header content-header">
              <el-icon><Document /></el-icon>
              <span>正式输出</span>
              <el-tag size="small" type="success">JSON</el-tag>
            </div>
            <div class="content-entries">
              <div v-for="(entry, index) in mergedContentLog" :key="`c-${index}`" class="content-entry"
                :class="`stage-${entry.stage}`">
                <div class="entry-header">
                  <el-tag size="small" :type="getStageTagType(entry.stage)" effect="light">
                    Stage {{ entry.stage }}
                  </el-tag>
                  <span class="timestamp">{{ formatTime(entry.timestamp) }}</span>
                </div>
                <div class="entry-content-wrapper">
                  <div class="entry-content content-text" :class="{ 'expanded': expandedEntries.has(`c-${index}`) }">
                    {{ entry.content }}
                  </div>
                  <el-button
                    v-if="entry.content.length > 100"
                    size="small"
                    link
                    @click="toggleExpand(`c-${index}`)"
                    class="expand-btn"
                  >
                    {{ expandedEntries.has(`c-${index}`) ? '收起' : '展开' }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="mergedReasoningLogByStage.length === 0 && mergedContentLog.length === 0" class="empty-log">
            <el-empty description="等待模型开始推理...">
              <template #image>
                <el-icon :size="60" class="empty-icon"><ChatDotRound /></el-icon>
              </template>
            </el-empty>
          </div>
        </div>
      </el-card>

      <!-- Right: Analysis Result Preview (Previous Stage) -->
      <el-card class="preview-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="header-title">
              <el-icon><View /></el-icon>
              {{ lastCompletedStageName }} 结果预览
            </span>
          </div>
        </template>

        <div class="preview-container">
          <div v-if="lastCompletedStage === 1 && hasStage1Result" class="stage-preview">
            <Stage1ResultView :result="currentTask?.stages?.[1]?.result" />
          </div>
          <div v-else-if="lastCompletedStage === 2 && hasStage2Result" class="stage-preview">
            <Stage2ResultView :result="currentTask?.stages?.[2]?.result" />
          </div>
          <div v-else-if="lastCompletedStage === 3 && hasStage3Result" class="stage-preview">
            <Stage3ResultView :result="currentTask?.stages?.[3]?.result" />
          </div>
          <div v-else class="preview-empty">
            <el-empty description="暂无上一阶段结果" :image-size="80">
              <template #description>
                <p>暂无上一阶段结果</p>
                <p class="empty-hint">分析进行中，上一阶段完成后将显示结果</p>
              </template>
            </el-empty>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { Loading, CircleCheck, CircleClose, Delete, Timer, List, ChatDotRound, InfoFilled, ArrowDown, ArrowRight, Document, View } from '@element-plus/icons-vue'
import { useAnalysisStore } from '@/stores/analysis'
import type { StageInfo } from '@/types'
import Stage1ResultView from './Stage1ResultView.vue'
import Stage2ResultView from './Stage2ResultView.vue'
import Stage3ResultView from './Stage3ResultView.vue'

const store = useAnalysisStore()
const { currentTask, reasoningLog, contentLog, isAnalyzing, hasResult, currentStage } = storeToRefs(store)

const emit = defineEmits<{
  viewResults: []
}>()

// 合并相邻的同阶段推理内容
const mergedReasoningLog = computed(() => {
  const result: { stage: number; content: string; timestamp: number }[] = []
  for (const entry of reasoningLog.value) {
    const last = result[result.length - 1]
    if (last && last.stage === entry.stage) {
      if (entry.delta && !last.content.includes(entry.delta)) {
        last.content = entry.content
      }
    } else {
      result.push({
        stage: entry.stage,
        content: entry.content,
        timestamp: entry.timestamp
      })
    }
  }
  return result
})

// 合并相邻的同阶段正式输出内容
const mergedContentLog = computed(() => {
  const result: { stage: number; content: string; timestamp: number }[] = []
  for (const entry of contentLog.value) {
    const last = result[result.length - 1]
    if (last && last.stage === entry.stage) {
      last.content = entry.content
    } else {
      result.push({
        stage: entry.stage,
        content: entry.content,
        timestamp: entry.timestamp
      })
    }
  }
  return result
})

// 按阶段分组的推理日志（用于按阶段显示）
const mergedReasoningLogByStage = computed(() => {
  const groups: { stage: number; entries: typeof mergedReasoningLog.value }[] = []
  for (const entry of mergedReasoningLog.value) {
    const last = groups[groups.length - 1]
    if (last && last.stage === entry.stage) {
      last.entries.push(entry)
    } else {
      groups.push({ stage: entry.stage, entries: [entry] })
    }
  }
  return groups
})

const autoScroll = ref(true)
const reasoningContainer = ref<HTMLElement>()
const expandedEntries = ref<Set<string>>(new Set())
const reasoningCollapsedByStage = ref<Record<number, boolean>>({})

const stageResultVisible = ref(false)
const selectedStage = ref<StageInfo | null>(null)
const showRawJSON = ref(false)

// Timer state
const elapsedSeconds = ref(0)
const currentStageSeconds = ref(0)
let timerInterval: number | null = null
let stageTimerInterval: number | null = null

// Start timers when analyzing starts
watch(isAnalyzing, (analyzing) => {
  if (analyzing) {
    startTimers()
  } else {
    stopTimers()
  }
}, { immediate: true })

function startTimers() {
  elapsedSeconds.value = 0
  currentStageSeconds.value = 0

  timerInterval = window.setInterval(() => {
    elapsedSeconds.value++
  }, 1000)

  stageTimerInterval = window.setInterval(() => {
    if (currentStage.value?.status === 'running') {
      currentStageSeconds.value++
    }
  }, 1000)
}

function stopTimers() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  if (stageTimerInterval) {
    clearInterval(stageTimerInterval)
    stageTimerInterval = null
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins > 0) {
    return `${mins}分${secs.toString().padStart(2, '0')}秒`
  }
  return `${secs}秒`
}

onUnmounted(() => {
  stopTimers()
})

const stages = computed(() => {
  if (!currentTask.value) return []
  return Object.values(currentTask.value.stages).sort((a, b) => a.stage - b.stage)
})

const currentStageNum = computed(() => {
  const stages = Object.values(currentTask.value?.stages || {})
  const completed = stages.filter(s => s.status === 'completed').length
  const running = stages.find(s => s.status === 'running')
  return running ? completed + 1 : completed
})

// 检查各阶段是否有结果
const hasStage1Result = computed(() => !!currentTask.value?.stages?.[1]?.result)
const hasStage2Result = computed(() => !!currentTask.value?.stages?.[2]?.result)
const hasStage3Result = computed(() => !!currentTask.value?.stages?.[3]?.result)

// 上一完成阶段（用于预览）
const lastCompletedStage = computed(() => {
  const stages = Object.values(currentTask.value?.stages || {})
  const completedStages = stages.filter(s => s.status === 'completed')
  if (completedStages.length === 0) return null
  // 返回最后一个完成阶段的编号
  return completedStages[completedStages.length - 1]?.stage || null
})

const lastCompletedStageName = computed(() => {
  const stageNames: Record<number, string> = {
    1: '第一阶段（事实抽取）',
    2: '第二阶段（发言整理）',
    3: '第三阶段（意图分析）'
  }
  return lastCompletedStage.value ? stageNames[lastCompletedStage.value] : ''
})

const currentAction = computed(() => {
  const actions: Record<number, string> = {
    1: '正在抽取结构化事实数据...',
    2: '正在整理玩家发言与立场...',
    3: '正在进行意图分析与身份推断...'
  }
  return currentStage.value ? actions[currentStage.value.stage] || '分析中...' : '准备中...'
})

function getStageStatus(stage: StageInfo): string {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    running: '进行中...',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[stage.status] || stage.status
}

function getStepStatus(stage: StageInfo): '' | 'wait' | 'process' | 'finish' | 'error' {
  const statusMap: Record<string, '' | 'wait' | 'process' | 'finish' | 'error'> = {
    pending: 'wait',
    running: 'process',
    completed: 'finish',
    failed: 'error'
  }
  return statusMap[stage.status] || 'wait'
}

function getStageTagType(stage: number): 'primary' | 'success' | 'warning' {
  const typeMap: Record<number, 'primary' | 'success' | 'warning'> = {
    1: 'primary',
    2: 'success',
    3: 'warning'
  }
  return typeMap[stage] || 'primary'
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function showStageResult(stage: StageInfo) {
  console.log('[Stage] Clicked:', stage.stage, 'status:', stage.status, 'hasResult:', !!stage.result)
  if (stage.status === 'completed' && stage.result) {
    selectedStage.value = stage
    showRawJSON.value = false
    stageResultVisible.value = true
  } else if (stage.status === 'completed' && !stage.result) {
    console.warn('[Stage] Stage completed but no result available')
    ElMessage.warning('该阶段结果暂不可用，请稍后重试')
  }
}

function toggleExpand(index: string | number) {
  const key = String(index)
  if (expandedEntries.value.has(key)) {
    expandedEntries.value.delete(key)
  } else {
    expandedEntries.value.add(key)
  }
}

function toggleReasoningCollapse(stage: number) {
  reasoningCollapsedByStage.value[stage] = !isReasoningCollapsedForStage(stage)
}

function isReasoningCollapsedForStage(stage: number): boolean {
  const hasContentForStage = contentLog.value.some(c => c.stage === stage)
  return reasoningCollapsedByStage.value[stage] ?? hasContentForStage
}

function formatJSON(obj: any): string {
  return JSON.stringify(obj, null, 2)
}

function clearLog() {
  reasoningLog.value = []
  contentLog.value = []
  reasoningCollapsedByStage.value = {}
}

function cancelAnalysis() {
  stopTimers()
  store.disconnect()
  store.$reset()
}

// Auto scroll
watch(reasoningLog, () => {
  if (autoScroll.value && reasoningContainer.value) {
    nextTick(() => {
      reasoningContainer.value!.scrollTop = reasoningContainer.value!.scrollHeight
    })
  }
}, { deep: true })

// Auto scroll for content
watch(contentLog, () => {
  if (autoScroll.value && reasoningContainer.value) {
    nextTick(() => {
      reasoningContainer.value!.scrollTop = reasoningContainer.value!.scrollHeight
    })
  }
}, { deep: true })
</script>

<style scoped>
.analysis-progress {
  max-width: 1400px;
  margin: 0 auto;
}

/* Timer Banner */
.timer-banner {
  background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
  border-radius: 12px;
  padding: 16px 24px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.3);
}

.timer-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.timer-icon {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.timer-label {
  font-size: 14px;
  opacity: 0.9;
}

.timer-value {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
}

.stage-timer {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.stage-label {
  font-size: 14px;
  opacity: 0.9;
}

.stage-time {
  font-size: 18px;
  font-weight: 600;
}

/* Progress Card */
.progress-card {
  margin-bottom: 20px;
  background: white;
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.steps-container {
  padding: 20px 0;
}

:deep(.el-step__title) {
  font-size: 14px;
  font-weight: 500;
}

:deep(.el-step__description) {
  font-size: 12px;
}

:deep(.el-step) {
  cursor: pointer;
}

:deep(.el-step.is-finish:hover .el-step__head),
:deep(.el-step.is-process:hover .el-step__head) {
  transform: scale(1.1);
  transition: transform 0.3s;
}

.stage-preview {
  max-height: 70vh;
  overflow-y: auto;
}

.stage-alert {
  margin-bottom: 16px;
}

.json-toggle {
  margin-left: 12px;
}

.visual-preview {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.preview-content {
  margin-top: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
}

.preview-content pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
}

.spin-icon {
  color: #409eff;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.success-icon {
  color: #67c23a;
}

.pending-icon {
  color: #c0c4cc;
}

.current-action {
  margin-top: 20px;
}

.action-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: #409eff;
  font-size: 14px;
}

.stage-timer-inline {
  color: #67c23a;
  font-weight: 600;
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.reasoning-card,
.preview-card {
  background: white;
  border-radius: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.help-icon {
  color: #909399;
  font-size: 16px;
  cursor: help;
}

/* Reasoning Container */
.reasoning-container {
  height: 500px;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.reasoning-entry {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s;
}

.reasoning-entry:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.reasoning-entry.stage-1 {
  border-left: 4px solid #409eff;
}

.reasoning-entry.stage-2 {
  border-left: 4px solid #67c23a;
}

.reasoning-entry.stage-3 {
  border-left: 4px solid #e6a23c;
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.timestamp {
  font-size: 12px;
  color: #909399;
}

.entry-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.entry-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  min-height: 20px;
  max-height: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.entry-content.expanded {
  max-height: none;
  -webkit-line-clamp: unset;
  overflow: visible;
}

.expand-btn {
  align-self: flex-start;
  padding: 0;
  font-size: 12px;
}

.empty-log {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon {
  color: #c0c4cc;
}

/* Reasoning & Content Sections */
.reasoning-section,
.content-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 8px;
  font-weight: 500;
  color: #606266;
  cursor: pointer;
  transition: all 0.3s;
}

.section-header:hover {
  background: #e4e7ed;
}

.content-header {
  background: #f0f9ff;
  color: #409eff;
}

.content-header:hover {
  background: #e6f7ff;
}

.reasoning-entries,
.content-entries {
  padding-left: 8px;
}

.content-entry {
  margin-bottom: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f0f9ff;
  border-left: 4px solid #409eff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.content-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #303133;
  background: #fff;
  padding: 8px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Preview Card */
.preview-container {
  height: 500px;
  overflow-y: auto;
}

.preview-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .timer-banner {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }

  .stage-timer {
    align-items: center;
  }
}
</style>
