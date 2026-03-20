
<template>
  <div class="player-comparison">
    <el-card shadow="never" class="comparison-card">
      <template #header>
        <span>📊 盲推猜测 vs 真实身份</span>
      </template>

      <el-table
        :data="comparisonData"
        style="width: 100%"
        :row-class-name="getRowClass"
        border
      >
        <el-table-column prop="player" label="玩家" width="70" align="center">
          <template #default="{ row }">
            <el-avatar :size="28">{{ row.player }}</el-avatar>
          </template>
        </el-table-column>

        <el-table-column prop="blindGuess" label="盲推猜测" min-width="120">
          <template #default="{ row }">
            <el-tag :type="getGuessType(row.blindGuess)">
              {{ row.blindGuess || '未知' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="truth" label="真实身份" min-width="120">
          <template #default="{ row }">
            <el-tag :type="getTruthType(row.truth)" effect="dark">
              {{ row.truth || '未知' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="isCorrect" label="结果" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.isCorrect" color="#67c23a" size="20">
              <Check />
            </el-icon>
            <el-icon v-else color="#f56c6c" size="20">
              <Close />
            </el-icon>
          </template>
        </el-table-column>

        <el-table-column prop="errorType" label="错误类型" min-width="120">
          <template #default="{ row }">
            <el-tag v-if="row.errorType" type="danger" effect="plain" size="small">
              {{ row.errorType }}
            </el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>

        <el-table-column prop="fixSuggestion" label="修正建议" min-width="200">
          <template #default="{ row }">
            <span class="suggestion">{{ row.fixSuggestion || '—' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="daily-inference-card">
      <template #header>
        <span>📅 逐日推断演变</span>
      </template>

      <el-tabs v-model="activeDay" type="card">
        <el-tab-pane
          v-for="day in availableDays"
          :key="day"
          :label="`第 ${day} 天`"
          :name="day"
        >
          <el-table :data="getDayInferences(day)" style="width: 100%" border>
            <el-table-column prop="playerId" label="玩家" width="70" align="center" />

            <el-table-column prop="roleGuess" label="角色猜测" min-width="120">
              <template #default="{ row }">
                <el-tag :type="getGuessType(row.roleGuess)">
                  {{ row.roleGuess || '未知' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="概率" min-width="150">
              <template #default="{ row }">
                <div class="prob-bars">
                  <div class="prob-bar">
                    <span class="label">🐺</span>
                    <el-progress
                      :percentage="Math.round(row.wolfProb * 100)"
                      :color="'#ff4757'"
                      :stroke-width="6"
                      :show-text="false"
                    />
                  </div>
                  <div class="prob-bar">
                    <span class="label">😇</span>
                    <el-progress
                      :percentage="Math.round(row.goodProb * 100)"
                      :color="'#2ed573'"
                      :stroke-width="6"
                      :show-text="false"
                    />
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="reason" label="推断理由" min-width="300">
              <template #default="{ row }">
                <div class="reason-text">{{ row.reason }}</div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Check, Close } from '@element-plus/icons-vue'

const props = defineProps<{
  blindInference?: {
    per_day_updates: Array<{
      day: number
      player_inference: Record<string, {
        role_probabilities: {
          wolf: number
          good: number
          specific_role_guess: string
        }
        reason: string
      }>
    }>
  }
  validation?: {
    compare_with_truth: Array<{
      player: string
      blind_guess: string
      truth: string
      is_correct: boolean
      error_type: string
      fix_suggestion: string
    }>
  }
}>()

const activeDay = ref(1)

const comparisonData = computed(() => {
  return props.validation?.compare_with_truth || []
})

const availableDays = computed(() => {
  const days = props.blindInference?.per_day_updates.map(u => u.day) || []
  return [...new Set(days)].sort((a, b) => a - b)
})

function getDayInferences(day: number) {
  const dayUpdate = props.blindInference?.per_day_updates.find(u => u.day === day)
  if (!dayUpdate) return []

  return Object.entries(dayUpdate.player_inference).map(([playerId, data]) => ({
    playerId,
    roleGuess: data.role_probabilities.specific_role_guess,
    wolfProb: data.role_probabilities.wolf,
    goodProb: data.role_probabilities.good,
    reason: data.reason
  }))
}

function getRowClass(row: any) {
  return row.isCorrect ? 'correct-row' : 'incorrect-row'
}

function getGuessType(guess: string): 'danger' | 'success' | 'warning' | 'info' {
  if (!guess) return 'info'
  if (guess.includes('狼')) return 'danger'
  if (guess.includes('平民')) return 'success'
  if (['通灵师', '女巫', '猎人', '守卫'].some(r => guess.includes(r))) return 'warning'
  return 'info'
}

function getTruthType(truth: string): 'danger' | 'success' | 'warning' | 'info' {
  if (!truth) return 'info'
  if (truth.includes('狼')) return 'danger'
  if (truth.includes('平民')) return 'success'
  if (['通灵师', '女巫', '猎人', '守卫'].some(r => truth.includes(r))) return 'warning'
  return 'info'
}
</script>

<style scoped>
.player-comparison {
  padding: 16px;
}

.comparison-card,
.daily-inference-card {
  margin-bottom: 20px;
  background: white;
  border: 1px solid #e4e7ed;
}

.comparison-card :deep(.el-card__header),
.daily-inference-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  font-weight: 600;
  color: #303133;
}

:deep(.correct-row) {
  background: #f0f9eb !important;
}

:deep(.incorrect-row) {
  background: #fef0f0 !important;
}

.suggestion {
  font-size: 13px;
  color: #606266;
}

.prob-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prob-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prob-bar .label {
  font-size: 12px;
  width: 20px;
}

.reason-text {
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
}
</style>
