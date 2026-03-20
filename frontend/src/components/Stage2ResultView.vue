<template>
  <div class="stage2-result">
    <!-- 发言列表（按天数分组） -->
    <el-card v-if="speeches.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><ChatDotRound /></el-icon>
          <span>玩家发言 ({{ speeches.length }}条)</span>
        </div>
      </template>
      <div class="speech-day-groups">
        <div v-for="group in speechesByDay" :key="group.day" class="day-group">
          <div class="day-header">
            <el-tag :type="group.day === 0 ? 'warning' : 'primary'" size="large" effect="dark">
              {{ group.day === 0 ? '警上竞选' : `第${group.day}天` }}
            </el-tag>
            <span class="speech-count">{{ group.speeches.length }} 条发言</span>
          </div>
          <div class="speech-list">
            <div v-for="speech in group.speeches" :key="speech.id" class="speech-item">
              <div class="speech-header">
                <div class="speech-meta">
                  <span class="speaker">{{ speech.speaker }}号玩家</span>
                  <el-tag v-if="speech.speech_order !== '-'" type="info" size="small" effect="plain">第{{ speech.speech_order }}个发言</el-tag>
                </div>
              </div>
              <div class="speech-content">{{ speech.text_summary }}</div>
              <div v-if="speech.claims && speech.claims.length > 0" class="speech-claims">
                <el-tag v-for="(claim, idx) in speech.claims" :key="idx" type="warning" size="small" effect="plain">
                  {{ claim }}
                </el-tag>
              </div>
              <div v-if="speech.stance" class="speech-stance">
                <span v-if="speech.stance.supports?.length > 0" class="stance-item supports">
                  <el-icon><CaretTop /></el-icon>支持: {{ speech.stance.supports.join(', ') }}号
                </span>
                <span v-if="speech.stance.attacks?.length > 0" class="stance-item attacks">
                  <el-icon><CaretBottom /></el-icon>攻击: {{ speech.stance.attacks.join(', ') }}号
                </span>
                <span v-if="speech.stance.neutral_mentions?.length > 0" class="stance-item neutral">
                  <el-icon><More /></el-icon>提及: {{ speech.stance.neutral_mentions.join(', ') }}号
                </span>
              </div>
              <div v-if="speech.intent_tags?.length > 0" class="speech-intent">
                <el-tag v-for="(tag, idx) in speech.intent_tags" :key="idx" size="small" :type="getIntentType(tag)">
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 解说内容 -->
    <el-card v-if="commentatorSegments.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Microphone /></el-icon>
          <span>解说分析 ({{ commentatorSegments.length }}段)</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item v-for="(segment, index) in commentatorSegments" :key="index" type="primary">
          <div class="commentator-segment">
            <div class="segment-phase">{{ segment.phase }}</div>
            <div class="segment-summary">{{ segment.summary }}</div>
            <div v-if="segment.useful_for_intent_analysis === '是'" class="segment-useful">
              <el-tag type="success" size="small"><el-icon><Check /></el-icon> 对意图分析有用</el-tag>
              <div class="why-useful">{{ segment.why_useful }}</div>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChatDotRound, Microphone, CaretTop, CaretBottom, More, Check } from '@element-plus/icons-vue'

interface Speech {
  day: number
  speaker: string
  speech_order: string | number
  text_summary: string
  claims: string[]
  stance: {
    supports: string[]
    attacks: string[]
    neutral_mentions: string[]
  }
  intent_tags: string[]
}

interface CommentatorSegment {
  phase: string
  summary: string
  useful_for_intent_analysis: string
  why_useful: string
}

interface Stage2Result {
  class_2_daytime_speeches?: Speech[]
  class_3_commentator_content?: {
    segments: CommentatorSegment[]
  }
}

const props = defineProps<{
  result: Stage2Result
}>()

const speeches = computed(() => {
  const list = props.result?.class_2_daytime_speeches || []
  return list.map((s, idx) => ({ ...s, id: idx }))
})

// 按天数分组的发言
const speechesByDay = computed(() => {
  const groups: { day: number; speeches: typeof speeches.value }[] = []
  for (const speech of speeches.value) {
    const day = speech.day || 0
    const existing = groups.find(g => g.day === day)
    if (existing) {
      existing.speeches.push(speech)
    } else {
      groups.push({ day, speeches: [speech] })
    }
  }
  // 按天数排序（警上竞选 day=0 排在最前面）
  return groups.sort((a, b) => a.day - b.day)
})

const commentatorSegments = computed(() => {
  return props.result?.class_3_commentator_content?.segments || []
})

function getIntentType(tag: string): 'danger' | 'warning' | 'success' | 'info' {
  if (tag.includes('狼') || tag.includes('攻击') || tag.includes('抗推')) return 'danger'
  if (tag.includes('找') || tag.includes('分析') || tag.includes('推理')) return 'success'
  if (tag.includes('表水') || tag.includes('好人')) return 'primary'
  return 'info'
}
</script>

<style scoped>
.stage2-result {
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

.speech-day-groups {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.day-group {
  background: #f9f9f9;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #e4e7ed;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e4e7ed;
}

.speech-count {
  color: #909399;
  font-size: 14px;
}

.speech-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.speech-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  border-left: 4px solid #409eff;
}

.speech-header {
  margin-bottom: 8px;
}

.speech-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.speaker {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.speech-content {
  color: #303133;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.speech-claims {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.speech-stance {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
}

.stance-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stance-item.supports {
  color: #67c23a;
}

.stance-item.attacks {
  color: #f56c6c;
}

.stance-item.neutral {
  color: #909399;
}

.speech-intent {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.commentator-segment {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-phase {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.segment-summary {
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.segment-useful {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.why-useful {
  font-size: 12px;
  color: #909399;
  font-style: italic;
}
</style>
