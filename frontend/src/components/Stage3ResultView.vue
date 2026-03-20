<template>
  <div class="stage3-result">
    <!-- 准确度统计 -->
    <el-card v-if="accuracy" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><DataLine /></el-icon>
          <span>预测准确度</span>
        </div>
      </template>
      <div class="accuracy-stats">
        <div class="accuracy-item">
          <el-progress type="dashboard" :percentage="Math.round(accuracy.role_accuracy * 100)" :color="progressColors" />
          <div class="accuracy-label">角色准确度</div>
        </div>
        <div class="accuracy-item">
          <el-progress type="dashboard" :percentage="Math.round(accuracy.camp_accuracy * 100)" :color="progressColors" />
          <div class="accuracy-label">阵营准确度</div>
        </div>
      </div>
    </el-card>

    <!-- 关键玩家提示 -->
    <el-alert v-if="keyPlayers.length > 0" type="info" :closable="false" class="section-card" show-icon>
      <template #title>
        关键玩家
      </template>
      <div class="key-players-inline">
        <el-tag v-for="p in keyPlayers" :key="p" type="warning" size="small" effect="dark">
          {{ p }}号
        </el-tag>
      </div>
    </el-alert>

    <!-- 验证对比 -->
    <el-card v-if="validationItems.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><DocumentChecked /></el-icon>
          <span>验证对比 ({{ correctCount }}/{{ validationItems.length }} 正确)</span>
        </div>
      </template>
      <div class="validation-list">
        <div v-for="item in validationItems" :key="item.player" class="validation-item" :class="{ correct: item.is_correct }">
          <div class="validation-header">
            <span class="player-id">{{ item.player }}号</span>
            <el-tag :type="item.is_correct ? 'success' : 'danger'" size="small">
              <el-icon v-if="item.is_correct"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
              {{ item.is_correct ? '正确' : '错误' }}
            </el-tag>
          </div>
          <div class="validation-compare">
            <div class="compare-row">
              <span class="compare-label">盲猜:</span>
              <el-tag type="info" size="small" effect="plain">{{ item.blind_guess }}</el-tag>
            </div>
            <div class="compare-row">
              <span class="compare-label">真相:</span>
              <el-tag :type="getRoleType(item.truth)" size="small">{{ item.truth }}</el-tag>
            </div>
            <div v-if="!item.is_correct && item.error_type" class="compare-row error-type">
              <span class="compare-label">错误:</span>
              <span class="error-text">{{ item.error_type }}</span>
            </div>
            <!-- 漏看的信号 -->
            <div v-if="!item.is_correct && item.missed_signals?.length" class="compare-row missed-signals">
              <span class="compare-label">漏看:</span>
              <div class="signals-list">
                <span v-for="(sig, idx) in item.missed_signals" :key="idx" class="signal-tag">{{ sig }}</span>
              </div>
            </div>
            <!-- 错误逻辑 -->
            <div v-if="!item.is_correct && item.wrong_logic" class="compare-row wrong-logic">
              <span class="compare-label">错因:</span>
              <span class="logic-text">{{ item.wrong_logic }}</span>
            </div>
            <div v-if="item.fix_suggestion" class="compare-row fix-suggestion">
              <span class="compare-label">建议:</span>
              <span class="suggestion-text">{{ item.fix_suggestion }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 每日推理链 (新增) -->
    <el-card v-if="reasoningChains.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Link /></el-icon>
          <span>逐日推理链</span>
        </div>
      </template>
      <el-collapse>
        <el-collapse-item v-for="chain in reasoningChains" :key="`${chain.observer_id}-${chain.day}`" :title="`${chain.observer_id}号 - 第${chain.day}天`">
          <div class="reasoning-chain">
            <div class="chain-header">
              <el-tag :type="getRoleType(chain.observer_role)" size="small">身份: {{ chain.observer_role }}</el-tag>
              <div v-if="chain.known_info?.length" class="known-info">
                <span class="info-label">已知信息:</span>
                <el-tag v-for="(info, idx) in chain.known_info" :key="idx" size="small" type="info" effect="plain">{{ info }}</el-tag>
              </div>
            </div>
            <div class="beliefs-list">
              <div v-for="(belief, targetId) in chain.beliefs" :key="targetId" class="belief-item">
                <div class="belief-header">
                  <span class="target-id">对 {{ targetId }} 号判断:</span>
                  <el-tag size="small" :type="belief.conclusion?.includes('狼') ? 'danger' : 'success'">{{ belief.conclusion }}</el-tag>
                  <el-progress :percentage="Math.round((belief.confidence || 0.5) * 100)" :stroke-width="4" style="width: 80px" />
                </div>
                <div class="belief-reason">{{ belief.reasoning }}</div>
              </div>
            </div>
            <div v-if="Object.keys(chain.belief_changes || {}).length > 0" class="belief-changes">
              <div class="changes-title">认知变化:</div>
              <div v-for="(change, targetId) in chain.belief_changes" :key="targetId" class="change-item">
                <span class="change-target">{{ targetId }}号:</span>
                <span class="change-from">{{ change.from || '未知' }}</span>
                <el-icon><ArrowRight /></el-icon>
                <span class="change-to">{{ change.to }}</span>
                <el-tag size="small" type="warning">{{ change.triggered_by }}</el-tag>
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 操作策略评价 (新增) -->
    <el-card v-if="operationStrategies.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Trophy /></el-icon>
          <span>操作策略评价</span>
        </div>
      </template>
      <div class="strategies-list">
        <div v-for="(strategy, idx) in operationStrategies" :key="idx" class="strategy-card" :class="strategy.skill_level">
          <div class="strategy-header">
            <div class="strategy-player">
              <span class="player-id">{{ strategy.player_id }}号</span>
              <el-tag size="small" :type="getRoleType(strategy.player_role)">{{ strategy.player_role }}</el-tag>
            </div>
            <div class="strategy-meta">
              <el-tag size="small" type="info">第{{ strategy.day }}天</el-tag>
              <el-tag size="small" :type="getSkillLevelType(strategy.skill_level)">{{ strategy.skill_level }}</el-tag>
              <el-rate v-if="strategy.effectiveness_score" :model-value="strategy.effectiveness_score / 2" disabled show-score :max="5" />
            </div>
          </div>
          <div class="strategy-detail">{{ strategy.operation_detail }}</div>
          <div v-if="strategy.good_points" class="strategy-points good">
            <el-icon><CircleCheck /></el-icon> {{ strategy.good_points }}
          </div>
          <div v-if="strategy.bad_points" class="strategy-points bad">
            <el-icon><Warning /></el-icon> {{ strategy.bad_points }}
          </div>
          <div v-if="strategy.alternative_actions" class="strategy-alternative">
            <span class="alt-label">替代方案:</span> {{ strategy.alternative_actions }}
          </div>
          <div v-if="strategy.lesson_learned" class="strategy-lesson">
            <el-icon><InfoFilled /></el-icon> {{ strategy.lesson_learned }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- 知识片段 (只展示重要度 >= 0.7 的) -->
    <el-card v-if="filteredKnowledgeChunks.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Collection /></el-icon>
          <span>关键知识点 ({{ filteredKnowledgeChunks.length }}条)</span>
        </div>
      </template>
      <div class="knowledge-list">
        <div v-for="(chunk, idx) in filteredKnowledgeChunks" :key="idx" class="knowledge-item" :class="chunk.chunk_type">
          <div class="knowledge-header">
            <el-tag size="small" :type="getChunkTypeColor(chunk.chunk_type)">{{ chunk.chunk_type }}</el-tag>
            <el-rate v-model="chunk.importance_score" disabled :max="1" :colors="['#e6a23c']" void-color="#dcdfe6" />
          </div>
          <div class="knowledge-content">{{ chunk.content }}</div>
          <div v-if="chunk.related_players?.length" class="knowledge-players">
            <span>相关玩家:</span>
            <el-tag v-for="p in chunk.related_players" :key="p" size="small" type="info">{{ p }}号</el-tag>
          </div>
        </div>
      </div>
    </el-card>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataLine, DocumentChecked, CircleCheck, CircleClose, InfoFilled, Link, Trophy, Collection, ArrowRight, Warning } from '@element-plus/icons-vue'

interface ValidationItem {
  player: string
  blind_guess: string
  truth: string
  is_correct: boolean
  error_type: string
  missed_signals?: string[]
  wrong_logic?: string
  fix_suggestion: string
}

interface ReasoningChain {
  observer_id: string
  observer_role: string
  day: number
  known_info?: string[]
  beliefs: Record<string, {
    conclusion: string
    confidence: number
    reasoning: string
  }>
  belief_changes?: Record<string, {
    from: string
    to: string
    triggered_by: string
  }>
}

interface OperationStrategy {
  player_id: string
  player_role: string
  operation_type: string
  day: number
  operation_detail: string
  effectiveness_score?: number
  skill_level?: 'beginner' | 'intermediate' | 'advanced' | 'expert'
  good_points?: string
  bad_points?: string
  alternative_actions?: string
  lesson_learned?: string
}

interface KnowledgeChunk {
  chunk_type: 'strategy' | 'mistake' | 'insight' | 'relationship'
  content: string
  related_players?: string[]
  importance_score?: number
}

interface Stage3Result {
  intent_analysis_engine?: {
    phase_A_blind_inference?: {
      description?: string
      analysis_method?: string
      key_players?: string[]
    }
    phase_B_reveal_validation?: {
      compare_with_truth?: ValidationItem[]
      overall_accuracy?: {
        role_accuracy: number
        camp_accuracy: number
      }
      lesson_learned?: string
    }
    daily_reasoning_chains?: ReasoningChain[]
    operation_strategies?: OperationStrategy[]
    knowledge_chunks?: KnowledgeChunk[]
  }
}

const props = defineProps<{
  result: Stage3Result
}>()

const engine = computed(() => props.result?.intent_analysis_engine)

const accuracy = computed(() => engine.value?.phase_B_reveal_validation?.overall_accuracy)

const keyPlayers = computed(() => engine.value?.phase_A_blind_inference?.key_players || [])

const validationItems = computed(() => engine.value?.phase_B_reveal_validation?.compare_with_truth || [])
const correctCount = computed(() => validationItems.value.filter(i => i.is_correct).length)

// 新增的 computed 属性
const reasoningChains = computed<ReasoningChain[]>(() => {
  return engine.value?.daily_reasoning_chains || []
})

const operationStrategies = computed<OperationStrategy[]>(() => {
  return engine.value?.operation_strategies || []
})

const knowledgeChunks = computed<KnowledgeChunk[]>(() => {
  return engine.value?.knowledge_chunks || []
})

// 只展示重要度 >= 0.7 的知识片段
const filteredKnowledgeChunks = computed<KnowledgeChunk[]>(() => {
  return knowledgeChunks.value.filter(chunk => (chunk.importance_score || 0) >= 0.7)
})

// 格式化推断原因，高亮引用部分
function formatReason(reason: string | undefined): string {
  if (!reason) return ''
  // 高亮 "原文[...]" 格式的引用
  return reason.replace(/原文\[([^\]]+)\]/g, '<span class="quote-highlight">原文[$1]</span>')
}

const progressColors = [
  { color: '#f56c6c', percentage: 40 },
  { color: '#e6a23c', percentage: 70 },
  { color: '#67c23a', percentage: 90 }
]

const wolfColor = '#f56c6c'
const goodColor = '#67c23a'

function getRoleType(role: string | undefined): 'danger' | 'success' | 'warning' | 'info' {
  if (!role) return 'info'
  if (role.includes('狼')) return 'danger'
  if (role.includes('平民')) return 'success'
  if (['通灵师', '预言家', '女巫', '猎人', '守卫'].some(r => role.includes(r))) return 'warning'
  return 'info'
}

// 新增辅助函数
function getSkillLevelType(level: string | undefined): 'info' | 'success' | 'warning' | 'danger' {
  if (!level) return 'info'
  if (level === 'expert') return 'danger'
  if (level === 'advanced') return 'warning'
  if (level === 'intermediate') return 'success'
  return 'info'
}

function getChunkTypeColor(type: string | undefined): 'success' | 'danger' | 'warning' | 'primary' {
  if (!type) return 'info'
  if (type === 'strategy') return 'success'
  if (type === 'mistake') return 'danger'
  if (type === 'insight') return 'warning'
  if (type === 'relationship') return 'primary'
  return 'info'
}
</script>

<style scoped>
.stage3-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #303133;
}

.accuracy-stats {
  display: flex;
  justify-content: space-around;
  padding: 20px;
}

.accuracy-item {
  text-align: center;
}

.accuracy-label {
  margin-top: 12px;
  font-size: 14px;
  color: #606266;
}

.key-players-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.missed-signals {
  align-items: flex-start;
}

.signals-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
}

.signal-tag {
  background: #fef0f0;
  color: #f56c6c;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.wrong-logic {
  align-items: flex-start;
}

.logic-text {
  flex: 1;
  color: #e6a23c;
  font-size: 12px;
  line-height: 1.5;
}

.validation-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.validation-item {
  background: #fef0f0;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #fde2e2;
}

.validation-item.correct {
  background: #f0f9ff;
  border-color: #a0cfff;
}

.validation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.validation-compare {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compare-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.compare-label {
  color: #909399;
  width: 40px;
}

.error-type {
  color: #f56c6c;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}

.fix-suggestion {
  color: #67c23a;
}

.suggestion-text {
  color: #67c23a;
  font-size: 12px;
}

/* 推理链样式 */
.reasoning-chain {
  padding: 12px;
}

.chain-header {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #dcdfe6;
}

.known-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: #606266;
}

.beliefs-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.belief-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.belief-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.target-id {
  font-weight: 600;
  color: #303133;
}

.belief-reason {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.belief-changes {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #dcdfe6;
}

.changes-title {
  font-weight: 600;
  color: #e6a23c;
  margin-bottom: 12px;
}

.change-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #fdf6ec;
  border-radius: 6px;
  margin-bottom: 8px;
}

.change-target {
  font-weight: 600;
  color: #303133;
}

.change-from {
  color: #909399;
  text-decoration: line-through;
}

.change-to {
  color: #67c23a;
  font-weight: 600;
}

/* 操作策略样式 */
.strategies-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.strategy-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  border-left: 4px solid #909399;
}

.strategy-card.expert {
  background: #fdf6ec;
  border-left-color: #f56c6c;
}

.strategy-card.advanced {
  background: #f0f9ff;
  border-left-color: #409eff;
}

.strategy-card.intermediate {
  background: #f0f9eb;
  border-left-color: #67c23a;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.strategy-player {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-detail {
  font-size: 14px;
  color: #303133;
  margin-bottom: 12px;
  line-height: 1.6;
}

.strategy-points {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 6px;
}

.strategy-points.good {
  background: #f0f9eb;
  color: #67c23a;
}

.strategy-points.bad {
  background: #fef0f0;
  color: #f56c6c;
}

.strategy-alternative {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  padding: 8px;
  background: #ecf5ff;
  border-radius: 6px;
}

.alt-label {
  font-weight: 600;
  color: #409eff;
}

.strategy-lesson {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #e6a23c;
  padding: 8px;
  background: #fdf6ec;
  border-radius: 6px;
}

/* 知识片段样式 */
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.knowledge-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  border-left: 4px solid #909399;
}

.knowledge-item.strategy {
  background: #f0f9eb;
  border-left-color: #67c23a;
}

.knowledge-item.mistake {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.knowledge-item.insight {
  background: #fdf6ec;
  border-left-color: #e6a23c;
}

.knowledge-item.relationship {
  background: #ecf5ff;
  border-left-color: #409eff;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.knowledge-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  margin-bottom: 8px;
}

.knowledge-players {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}
</style>
