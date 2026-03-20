<template>
  <div class="stage2-view">
    <!-- Day Tabs -->
    <el-tabs v-model="activeDay" type="card">
      <el-tab-pane v-for="day in availableDays" :key="day" :label="`第 ${day} 天`" :name="day">
        <div class="day-content">
          <!-- Speeches -->
          <el-timeline>
            <el-timeline-item
              v-for="speech in getSpeechesByDay(day)"
              :key="`${speech.day}-${speech.speaker}-${speech.speech_order}`"
              :type="getStanceType(speech.stance)"
            >
              <el-card class="speech-card" shadow="hover">
                <template #header>
                  <div class="speech-header">
                    <div class="speaker-info">
                      <el-avatar :size="32" :class="`player-${speech.speaker}`">
                        {{ speech.speaker }}号
                      </el-avatar>
                      <span class="speech-order">第 {{ speech.speech_order }} 个发言</span>
                    </div>
                    <div class="intent-tags">
                      <el-tag
                        v-for="tag in speech.intent_tags"
                        :key="tag"
                        size="small"
                        effect="dark"
                        :type="getIntentTagType(tag)"
                      >
                        {{ tag }}
                      </el-tag>
                    </div>
                  </div>
                </template>

                <div class="speech-body">
                  <p class="summary">{{ speech.text_summary }}</p>

                  <!-- Claims -->
                  <div v-if="speech.claims?.length" class="claims">
                    <el-tag
                      v-for="claim in speech.claims"
                      :key="claim"
                      type="warning"
                      effect="plain"
                    >
                      🎭 {{ claim }}
                    </el-tag>
                  </div>

                  <!-- Stance -->
                  <div class="stance">
                    <div v-if="speech.stance?.supports?.length" class="stance-item">
                      <span class="stance-label">支持:</span>
                      <el-tag
                        v-for="p in speech.stance.supports"
                        :key="p"
                        type="success"
                        size="small"
                      >
                        {{ p }}号
                      </el-tag>
                    </div>
                    <div v-if="speech.stance?.attacks?.length" class="stance-item">
                      <span class="stance-label">攻击:</span>
                      <el-tag
                        v-for="p in speech.stance.attacks"
                        :key="p"
                        type="danger"
                        size="small"
                      >
                        {{ p }}号
                      </el-tag>
                    </div>
                    <div v-if="speech.stance?.neutral_mentions?.length" class="stance-item">
                      <span class="stance-label">提及:</span>
                      <el-tag
                        v-for="p in speech.stance.neutral_mentions"
                        :key="p"
                        type="info"
                        size="small"
                      >
                        {{ p }}号
                      </el-tag>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Commentator Info -->
    <el-card v-if="commentatorSegments.length" class="commentator-card" shadow="never">
      <template #header>
        <span>🎙️ 解说信息</span>
      </template>
      <el-collapse>
        <el-collapse-item
          v-for="(seg, idx) in commentatorSegments"
          :key="idx"
          :title="`${seg.phase} - ${seg.useful_for_intent_analysis === 'yes' ? '✅ 有用' : '❌ 无用'}`"
        >
          <p>{{ seg.summary }}</p>
          <p v-if="seg.why_useful" class="why-useful">原因: {{ seg.why_useful }}</p>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Stage2Result, Speech } from '@/types'

const props = defineProps<{
  data?: Stage2Result
}>()

const activeDay = ref(1)

const availableDays = computed(() => {
  const speeches = props.data?.class_2_daytime_speeches || []
  const days = [...new Set(speeches.map(s => s.day))]
  return days.sort((a, b) => a - b)
})

const commentatorSegments = computed(() => {
  return props.data?.class_3_commentator_content?.segments || []
})

function getSpeechesByDay(day: number): Speech[] {
  const speeches = props.data?.class_2_daytime_speeches || []
  return speeches.filter(s => s.day === day)
}

function getStanceType(stance: Speech['stance']): 'primary' | 'success' | 'danger' | 'warning' {
  if (stance?.attacks?.length) return 'danger'
  if (stance?.supports?.length) return 'success'
  return 'primary'
}

function getIntentTagType(tag: string): 'danger' | 'success' | 'warning' | 'info' {
  const tagTypes: Record<string, 'danger' | 'success' | 'warning' | 'info'> = {
    '悍跳': 'danger',
    '冲锋': 'danger',
    '倒钩': 'danger',
    '找狼': 'success',
    '表水': 'success',
    '守卫起跳': 'warning',
    '通灵师起跳': 'warning',
    '划水': 'info',
    '垫飞': 'danger'
  }
  return tagTypes[tag] || 'info'
}
</script>

<style scoped>
.stage2-view {
  padding: 16px;
}

.day-content {
  max-height: 600px;
  overflow-y: auto;
}

:deep(.el-tabs__header) {
  background: #f5f7fa;
}

:deep(.el-tabs__item) {
  color: #606266;
}

:deep(.el-tabs__item.is-active) {
  color: #409eff;
  background: white;
}

.speech-card {
  margin-bottom: 12px;
  background: white;
  border: 1px solid #e4e7ed;
}

:deep(.el-card__header) {
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.speech-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.speaker-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

:deep(.el-avatar) {
  background: linear-gradient(135deg, #409eff 0%, #79bbff 100%);
  font-weight: 600;
}

.speech-order {
  color: #909399;
  font-size: 14px;
}

.intent-tags {
  display: flex;
  gap: 8px;
}

.speech-body {
  color: #303133;
}

.speech-body .summary {
  margin-bottom: 12px;
  line-height: 1.6;
}

.claims {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stance {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stance-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.stance-label {
  color: #909399;
  font-size: 14px;
  min-width: 50px;
}

.commentator-card {
  margin-top: 20px;
  background: white;
  border: 1px solid #e4e7ed;
}

.commentator-card :deep(.el-card__header) {
  background: #f5f7fa;
  font-weight: 600;
  color: #303133;
}

.why-useful {
  color: #67c23a;
  font-size: 14px;
  margin-top: 8px;
}
</style>
