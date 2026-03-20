<template>
  <div class="results-view">
    <el-card class="result-header" shadow="hover">
      <template #header>
        <div class="header-content">
          <div class="title-section">
            <div class="success-badge">🎉</div>
            <div class="title-text">
              <h2>分析完成</h2>
              <p class="subtitle">{{ currentTask?.game_name }}</p>
            </div>
          </div>
          <div class="actions">
            <el-button type="primary" @click="$emit('new-analysis')" :icon="Plus">
              新分析
            </el-button>
            <el-button @click="saveToJSON" :icon="Download">
              导出 JSON
            </el-button>
          </div>
        </div>
      </template>

      <!-- Summary Stats -->
      <div class="stats-row">
        <el-statistic title="角色准确率" :value="accuracyStats.roleAccuracy" suffix="%">
          <template #prefix>
            <el-icon><Aim /></el-icon>
          </template>
        </el-statistic>
        <el-statistic title="阵营准确率" :value="accuracyStats.campAccuracy" suffix="%">
          <template #prefix>
            <el-icon><Flag /></el-icon>
          </template>
        </el-statistic>
        <el-statistic title="分析天数" :value="dayCount">
          <template #prefix>
            <el-icon><Calendar /></el-icon>
          </template>
        </el-statistic>
        <el-statistic title="发言记录" :value="speechCount">
          <template #prefix>
            <el-icon><ChatDotRound /></el-icon>
          </template>
        </el-statistic>
      </div>
    </el-card>

    <!-- Result Tabs -->
    <el-tabs v-model="activeTab" type="border-card" class="result-tabs">
      <el-tab-pane label="📊 Stage 1: 事实数据" name="stage1">
        <Stage1View :data="stage1Result" />
      </el-tab-pane>

      <el-tab-pane label="💬 Stage 2: 发言整理" name="stage2">
        <Stage2View :data="stage2Result" />
      </el-tab-pane>

      <el-tab-pane label="🎯 Stage 3: 意图分析" name="stage3">
        <Stage3View :data="stage3Result" />
      </el-tab-pane>

      <el-tab-pane label="👥 玩家对比" name="comparison">
        <PlayerComparisonView
          :blind-inference="stage3Result?.intent_analysis_engine?.phase_A_blind_inference"
          :validation="stage3Result?.intent_analysis_engine?.phase_B_reveal_validation"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Plus, Download, Aim, Flag, Calendar, ChatDotRound } from '@element-plus/icons-vue'
import { useAnalysisStore } from '@/stores/analysis'
import Stage1View from './Stage1View.vue'
import Stage2View from './Stage2View.vue'
import Stage3View from './Stage3View.vue'
import PlayerComparisonView from './PlayerComparisonView.vue'

const emit = defineEmits<{
  newAnalysis: []
}>()

const store = useAnalysisStore()
const { currentTask, stage1Result, stage2Result, stage3Result } = storeToRefs(store)

// Debug: 检查数据
watch(() => currentTask.value, (val) => {
  console.log('[ResultsView] currentTask:', val)
}, { immediate: true })
watch(stage1Result, (val) => console.log('[ResultsView] stage1Result:', val))
watch(stage2Result, (val) => console.log('[ResultsView] stage2Result:', val))
watch(stage3Result, (val) => console.log('[ResultsView] stage3Result:', val))

const activeTab = ref('stage1')

const accuracyStats = computed(() => {
  const accuracy = stage3Result.value?.intent_analysis_engine?.phase_B_reveal_validation?.overall_accuracy
  return {
    roleAccuracy: Math.round((accuracy?.role_accuracy || 0) * 100),
    campAccuracy: Math.round((accuracy?.camp_accuracy || 0) * 100)
  }
})

const dayCount = computed(() => {
  return stage1Result.value?.class_1_structured_facts?.night_events_by_day?.length || 0
})

const speechCount = computed(() => {
  return stage2Result.value?.class_2_daytime_speeches?.length || 0
})

function saveToJSON() {
  const data = {
    meta: {
      game_name: currentTask.value?.game_name,
      format: currentTask.value?.format_name,
      analyzed_at: new Date().toISOString()
    },
    stage1: stage1Result.value,
    stage2: stage2Result.value,
    stage3: stage3Result.value
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `analysis_${currentTask.value?.game_name}_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.results-view {
  max-width: 1400px;
  margin: 0 auto;
}

.result-header {
  margin-bottom: 20px;
  background: white;
  border-radius: 12px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.success-badge {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

.title-text h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  padding: 16px;
}

:deep(.el-statistic__content) {
  font-size: 28px;
  color: #409eff;
}

:deep(.el-statistic__title) {
  font-size: 14px;
  color: #606266;
}

.result-tabs {
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

:deep(.el-tabs__header) {
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

:deep(.el-tabs__item) {
  color: #606266;
  font-weight: 500;
}

:deep(.el-tabs__item.is-active) {
  color: #409eff;
  background: white;
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
}
</style>
