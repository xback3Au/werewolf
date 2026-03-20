<template>
  <div class="stage3-view">
    <!-- Accuracy Summary -->
    <el-card class="accuracy-card" shadow="never">
      <template #header>
        <span>🎯 盲推准确率评估</span>
      </template>
      <div class="accuracy-stats">
        <div class="stat-item">
          <el-progress
            type="dashboard"
            :percentage="Math.round(accuracy.role * 100)"
            :color="progressColors"
          />
          <span class="stat-label">角色准确率</span>
        </div>
        <div class="stat-item">
          <el-progress
            type="dashboard"
            :percentage="Math.round(accuracy.camp * 100)"
            :color="progressColors"
          />
          <span class="stat-label">阵营准确率</span>
        </div>
      </div>
    </el-card>

    <!-- Intent Timeline -->
    <el-card class="timeline-card" shadow="never">
      <template #header>
        <span>📜 玩家意图时间线</span>
      </template>
      <el-tabs v-model="activePlayer" tab-position="left" class="player-tabs">
        <el-tab-pane
          v-for="(intent, playerId) in refinedIntents"
          :key="playerId"
          :label="`${playerId}号`"
          :name="playerId"
        >
          <div class="player-intent-detail">
            <div class="player-role-header">
              <el-tag :type="getRoleType(intent.final_role)" size="large" effect="dark">
                {{ intent.final_role }}
              </el-tag>
            </div>

            <el-timeline>
              <el-timeline-item
                v-for="item in intent.intent_timeline"
                :key="item.day"
                :type="item.confidence > 0.8 ? 'primary' : 'info'"
              >
                <h4>第 {{ item.day }} 天</h4>
                <el-card class="intent-item" shadow="hover">
                  <template #header>
                    <div class="intent-header">
                      <el-tag effect="dark" :type="getIntentType(item.main_intent)">
                        {{ item.main_intent }}
                      </el-tag>
                      <el-tag type="info" size="small">
                        置信度: {{ Math.round(item.confidence * 100) }}%
                      </el-tag>
                    </div>
                  </template>

                  <div v-if="item.sub_intents?.length" class="sub-intents">
                    <span class="label">子意图:</span>
                    <el-tag
                      v-for="sub in item.sub_intents"
                      :key="sub"
                      size="small"
                      effect="plain"
                    >
                      {{ sub }}
                    </el-tag>
                  </div>

                  <div v-if="item.evidence?.length" class="evidence">
                    <span class="label">依据:</span>
                    <ul>
                      <li v-for="(ev, idx) in item.evidence" :key="idx">{{ ev }}</li>
                    </ul>
                  </div>
                </el-card>
              </el-timeline-item>
            </el-timeline>

            <div v-if="intent.key_turning_points?.length" class="turning-points">
              <h4>关键转折点</h4>
              <el-tag
                v-for="(point, idx) in intent.key_turning_points"
                :key="idx"
                type="warning"
                effect="dark"
              >
                {{ point }}
              </el-tag>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Stage3Result, PlayerIntent } from '@/types'

const props = defineProps<{
  data?: Stage3Result
}>()

const activePlayer = ref('1')

const accuracy = computed(() => {
  const acc = props.data?.intent_analysis_engine?.phase_B_reveal_validation?.overall_accuracy
  return {
    role: acc?.role_accuracy || 0,
    camp: acc?.camp_accuracy || 0
  }
})

const refinedIntents = computed(() => {
  return props.data?.intent_analysis_engine?.phase_C_refined_intents || {}
})

const progressColors = [
  { color: '#f56c6c', percentage: 60 },
  { color: '#e6a23c', percentage: 80 },
  { color: '#67c23a', percentage: 100 }
]

function getRoleType(role: string): 'danger' | 'success' | 'warning' | 'info' {
  if (!role) return 'info'
  if (role.includes('狼')) return 'danger'
  if (role.includes('平民')) return 'success'
  if (['通灵师', '女巫', '猎人', '守卫'].some(r => role.includes(r))) return 'warning'
  return 'info'
}

function getIntentType(intent: string): 'danger' | 'success' | 'warning' | 'info' {
  const dangerous = ['悍跳', '冲锋', '倒钩', '深水倒钩', '殊死一搏']
  const good = ['找狼', '表水', '带队', '独立分析']
  if (dangerous.some(i => intent.includes(i))) return 'danger'
  if (good.some(i => intent.includes(i))) return 'success'
  return 'warning'
}
</script>

<style scoped>
.stage3-view {
  padding: 16px;
}

.accuracy-card {
  margin-bottom: 20px;
  background: white;
  border: 1px solid #e4e7ed;
}

.accuracy-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  font-weight: 600;
  color: #303133;
}

.accuracy-stats {
  display: flex;
  justify-content: center;
  gap: 60px;
  padding: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.stat-label {
  font-size: 16px;
  color: #606266;
}

.timeline-card {
  background: white;
  border: 1px solid #e4e7ed;
}

.timeline-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  font-weight: 600;
  color: #303133;
}

:deep(.el-tabs__nav-wrap) {
  background: #f5f7fa;
}

:deep(.el-tabs__item) {
  color: #606266;
  font-size: 16px;
}

:deep(.el-tabs__item.is-active) {
  color: #409eff;
  background: white;
}

.player-intent-detail {
  padding: 16px;
}

.player-role-header {
  margin-bottom: 20px;
}

.intent-item {
  margin-top: 12px;
  background: white;
  border: 1px solid #e4e7ed;
}

.intent-item :deep(.el-card__header) {
  background: #f5f7fa;
}

.intent-header {
  display: flex;
  gap: 12px;
}

.sub-intents,
.evidence {
  margin-top: 12px;
  color: #303133;
}

.label {
  color: #909399;
  font-size: 14px;
  margin-right: 8px;
}

.evidence ul {
  margin: 8px 0 0 0;
  padding-left: 20px;
  color: #606266;
  font-size: 14px;
}

.turning-points {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
}

.turning-points h4 {
  margin-bottom: 12px;
  color: #e6a23c;
}

h4 {
  margin: 0 0 8px 0;
  color: #409eff;
}
</style>
