<template>
  <div class="stage1-view">
    <!-- Segmentation Info (Legacy) -->
    <el-card v-if="data?.meta?.segmentation" class="section-card" shadow="never">
      <template #header>
        <span>📑 文本分段</span>
      </template>
      <el-timeline>
        <el-timeline-item type="info" :hollow="true">
          <h4>无关内容 (Segment 1)</h4>
          <p>{{ data.meta.segmentation.segment_1_noise?.summary }}</p>
        </el-timeline-item>
        <el-timeline-item type="primary">
          <h4>游戏正文 (Segment 2)</h4>
          <p>{{ data.meta.segmentation.segment_2_gameplay?.summary }}</p>
        </el-timeline-item>
        <el-timeline-item type="success">
          <h4>赛后复盘 (Segment 3)</h4>
          <p>{{ data.meta.segmentation.segment_3_postgame?.summary }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- Day Segments (New) -->
    <el-card v-if="data?.meta?.segments" class="section-card" shadow="never">
      <template #header>
        <span>📚 对局分段</span>
      </template>
      <el-table :data="segmentsList" style="width: 100%" border>
        <el-table-column prop="day" label="天数" width="80" align="center" />
        <el-table-column prop="name" label="段落名称" min-width="150" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getSegmentTypeTag(row.type)" size="small">
              {{ getSegmentTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="for_stage2" label="Stage 2" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.for_stage2 ? 'success' : 'info'" size="small">
              {{ row.for_stage2 ? '✓ 分析' : '— 跳过' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="textLength" label="文本长度" width="100" align="right">
          <template #default="{ row }">
            {{ row.textLength }} 字
          </template>
        </el-table-column>
        <el-table-column prop="contains_commentary" label="解说" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.contains_commentary" type="warning" size="small">含</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Players Table -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <span>👥 玩家信息汇总</span>
      </template>
      <el-table :data="playersList" style="width: 100%" border>
        <el-table-column prop="id" label="编号" width="70" align="center" />
        <el-table-column prop="role" label="身份" width="120">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role)" effect="dark">
              {{ row.role || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="badge" label="警徽" width="150">
          <template #default="{ row }">
            <span v-if="row.wonBadge">👑 警长</span>
            <span v-else-if="row.wentForSheriff">🙋 上警</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.alive ? 'success' : 'danger'">
              {{ row.alive ? '存活' : '出局' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="elimination" label="出局方式" min-width="150">
          <template #default="{ row }">
            {{ formatElimination(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="votes" label="投票记录" min-width="200">
          <template #default="{ row }">
            <div class="vote-tags">
              <el-tag v-for="vote in row.votes" :key="vote.day" size="small" class="vote-tag">
                Day{{ vote.day }}: {{ vote.target === 'abstain' ? '弃票' : vote.target + '号' }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Night Events -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <span>🌙 夜间事件</span>
      </template>
      <el-timeline>
        <el-timeline-item v-for="event in sortedNightEvents" :key="`${event.day}-${event.phase}`" type="warning">
          <h4>{{ getEventTitle(event) }}</h4>
          <el-descriptions :column="2" border>
            <template v-if="isSheriffPhase(event)">
              <el-descriptions-item label="警上竞选" :span="2">
                <el-tag type="warning">🎤 警上发言阶段</el-tag>
              </el-descriptions-item>
            </template>
            <template v-else>
              <el-descriptions-item label="🐺 狼刀">{{ event.wolf_kill_target || '无' }}</el-descriptions-item>
              <el-descriptions-item label="💊 救">{{ event.witch_save_target || '无' }}</el-descriptions-item>
              <el-descriptions-item label="☠️ 毒">{{ event.witch_poison_target || '无' }}</el-descriptions-item>
              <el-descriptions-item label="🛡️ 守">{{ event.guard_target || '无' }}</el-descriptions-item>
              <el-descriptions-item label="🔮 验" :span="2">{{ event.seer_or_medium_check || '无' }}</el-descriptions-item>
              <el-descriptions-item v-if="event.mechanic_wolf_learn" label="🤖 学" :span="2">{{ event.mechanic_wolf_learn }}</el-descriptions-item>
            </template>
            <el-descriptions-item label="结果" :span="2">{{ event.night_outcome_summary || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Stage1Result, PlayerFact, Segment } from '@/types'

const props = defineProps<{
  data?: Stage1Result
}>()

// Segments list for the new segmentation table
const segmentsList = computed(() => {
  const segments = props.data?.meta?.segments
  if (!segments) return []

  return segments.map((seg: Segment) => ({
    ...seg,
    textLength: seg.text?.length || 0
  }))
})

function getSegmentTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    'sheriff_vote': '警上竞选',
    'daytime': '白天发言',
    'night_commentary': '夜间解说'
  }
  return labels[type] || type
}

function getSegmentTypeTag(type: string): 'primary' | 'success' | 'warning' | 'info' {
  const tags: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    'sheriff_vote': 'warning',
    'daytime': 'primary',
    'night_commentary': 'info'
  }
  return tags[type] || 'info'
}

const playersList = computed(() => {
  const players = props.data?.class_1_structured_facts?.players
  if (!players) return []

  return Object.entries(players).map(([id, player]: [string, PlayerFact]) => ({
    id,
    role: player.fact_role,
    wentForSheriff: player.police_badge.went_for_sheriff === 'yes',
    wonBadge: player.police_badge.won_badge === 'yes',
    alive: player.elimination.final_status === 'alive',
    elimination: player.elimination,
    votes: player.day_votes
  }))
})

// 按游戏时间顺序排序：第一晚 -> 警上竞选 -> 第一天白天 -> 第二晚...
const sortedNightEvents = computed(() => {
  const events = props.data?.class_1_structured_facts?.night_events_by_day || []
  return [...events].sort((a, b) => {
    // 先按天数排序
    if (a.day !== b.day) return a.day - b.day
    // 同一天内，夜晚(night)在警上(sheriff_vote)之前
    // 因为：第1夜 -> 第1天警上竞选 -> 第1天白天
    const aIsSheriff = isSheriffPhase(a)
    const bIsSheriff = isSheriffPhase(b)
    if (!aIsSheriff && bIsSheriff) return -1
    if (aIsSheriff && !bIsSheriff) return 1
    return 0
  })
})

function getEventTitle(event: any): string {
  if (isSheriffPhase(event)) {
    return `第 ${event.day} 天 - 警上竞选`
  }
  return `第 ${event.day} 夜`
}

// 更健壮的判断是否是警上竞选阶段
function isSheriffPhase(event: any): boolean {
  // 检查各种可能的值
  const phase = String(event.phase || '').toLowerCase()
  return phase === 'sheriff_vote' || phase === 'sheriff' || phase.includes('警上')
}

function getRoleTagType(role: string): 'danger' | 'success' | 'warning' | 'info' {
  if (!role) return 'info'
  if (role.includes('狼')) return 'danger'
  if (role.includes('平民')) return 'success'
  if (['通灵师', '女巫', '猎人', '守卫'].some(r => role.includes(r))) return 'warning'
  return 'info'
}

function formatElimination(player: any): string {
  const e = player.elimination
  if (e.self_exploded_on_day) return `第${e.self_exploded_on_day}天自爆`
  if (e.voted_out_on_day) return `第${e.voted_out_on_day}天放逐`
  if (e.night_killed_on_day) return `第${e.night_killed_on_day}夜刀死`
  if (e.poisoned_on_day) return `第${e.poisoned_on_day}天毒死`
  return '—'
}
</script>

<style scoped>
.stage1-view {
  padding: 16px;
}

.section-card {
  margin-bottom: 20px;
  background: white;
  border: 1px solid #e4e7ed;
}

.vote-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.vote-tag {
  margin: 0;
}

h4 {
  margin: 0 0 8px 0;
  color: #409eff;
}

p {
  color: #606266;
  line-height: 1.6;
  margin: 0;
}

:deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  font-weight: 600;
  color: #303133;
}

:deep(.el-timeline-item__node) {
  background-color: #409eff;
}

:deep(.el-descriptions__label) {
  background-color: #f5f7fa;
  color: #606266;
  font-weight: 500;
}

:deep(.el-descriptions__content) {
  color: #303133;
}
</style>