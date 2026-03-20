<template>
  <div class="stage1-result">
    <!-- 全局结果 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Trophy /></el-icon>
          <span>游戏结果</span>
        </div>
      </template>
      <div class="winner-info">
        <el-tag :type="winnerType" size="large" effect="dark">
          {{ winnerText }}
        </el-tag>
        <p class="summary">{{ globalResult?.fact_summary || '无总结' }}</p>
      </div>
    </el-card>

    <!-- 警徽投票 -->
    <el-card v-if="sheriffVoteTable" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Medal /></el-icon>
          <span>警徽竞选</span>
          <el-tag v-if="sheriffVoteTable.winner" type="warning" size="small" effect="dark">
            🏆 {{ sheriffVoteTable.winner }}号当选
          </el-tag>
        </div>
      </template>

      <!-- 警徽竞选完整表格 -->
      <el-table :data="sheriffVoteDetails" stripe size="small" class="sheriff-table">
        <el-table-column prop="id" label="玩家" width="80" align="center">
          <template #default="{ row }">
            <span :class="{ 'winner-text': row.id === sheriffVoteTable.winner }">{{ row.id }}号</span>
          </template>
        </el-table-column>
        <el-table-column label="上警情况" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.wentForSheriff" type="warning" size="small" effect="dark">上警</el-tag>
            <el-tag v-else type="primary" size="small" effect="plain">警下</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="投票目标" min-width="120" align="center">
          <template #default="{ row }">
            <div class="vote-target-cell">
              <template v-if="row.wentForSheriff">
                <el-tag type="info" size="small" effect="plain">竞选者</el-tag>
              </template>
              <template v-else>
                <span
                  class="vote-target"
                  :class="{ 'is-winner': row.voteTarget === sheriffVoteTable.winner && row.voteTarget !== 'abstain' }"
                >
                  {{ row.voteTarget === 'abstain' ? '弃权' : row.voteTarget + '号' }}
                </span>
                <el-icon v-if="row.voteTarget === sheriffVoteTable.winner && row.voteTarget !== 'abstain'" color="#e6a23c">
                  <Medal />
                </el-icon>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 统计信息 -->
      <div class="sheriff-stats">
        <el-statistic title="上警人数" :value="sheriffCandidates.length" />
        <el-statistic title="警下人数" :value="sheriffVoters.length" />
        <el-statistic v-if="sheriffVoteTable.winner" title="当选警长" :value="sheriffVoteTable.winner + '号'" />
      </div>
    </el-card>

    <!-- 对局分段 -->
    <el-card v-if="segments.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Document /></el-icon>
          <span>对局分段 ({{ segments.length }}段)</span>
        </div>
      </template>
      <el-table :data="segmentsList" style="width: 100%" border size="small">
        <el-table-column prop="day" label="天数" width="70" align="center" />
        <el-table-column prop="name" label="段落名称" min-width="140" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getSegmentTypeTag(row.type)" size="small">
              {{ getSegmentTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="for_stage2" label="Stage 2" width="85" align="center">
          <template #default="{ row }">
            <el-tag :type="row.for_stage2 ? 'success' : 'info'" size="small">
              {{ row.for_stage2 ? '✓ 分析' : '— 跳过' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="textLength" label="文本长度" width="90" align="right">
          <template #default="{ row }">
            {{ row.textLength }} 字
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 玩家信息表格 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><User /></el-icon>
          <span>玩家信息 ({{ playerCount }}人)</span>
        </div>
      </template>
      <el-table :data="playerList" stripe size="small" class="player-table">
        <el-table-column prop="id" label="编号" width="60" align="center" />
        <el-table-column prop="fact_role" label="实际角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.fact_role)" size="small">
              {{ row.fact_role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="警徽" width="120" align="center">
          <template #default="{ row }">
            <div class="badge-info">
              <el-tooltip v-if="row.police_badge?.went_for_sheriff === 'yes'" content="上警" placement="top">
                <el-tag size="small" type="warning" effect="plain">上警</el-tag>
              </el-tooltip>
              <el-icon v-if="row.police_badge?.won_badge === 'yes'" color="#e6a23c" :size="20" class="medal-icon">
                <Medal />
              </el-icon>
              <el-tooltip v-if="row.police_badge?.badge_transfer_out" :content="`警徽飞给${row.police_badge.badge_transfer_out}号`" placement="top">
                <el-icon color="#409eff" :size="16"><ArrowRight /></el-icon>
              </el-tooltip>
              <el-tooltip v-if="row.police_badge?.badge_transfer_in" :content="`从${row.police_badge.badge_transfer_in}号接徽`" placement="top">
                <el-icon color="#67c23a" :size="16"><ArrowLeft /></el-icon>
              </el-tooltip>
              <span v-if="!row.police_badge?.went_for_sheriff && !row.police_badge?.won_badge && !row.police_badge?.badge_transfer_in && !row.police_badge?.badge_transfer_out">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="出局方式" min-width="120">
          <template #default="{ row }">
            <el-tag :type="getEliminationType(row.elimination)" size="small" effect="plain">
              {{ getEliminationText(row.elimination) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.elimination?.final_status === '存活'" color="#67c23a"><CircleCheck /></el-icon>
            <el-icon v-else color="#f56c6c"><CircleClose /></el-icon>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 夜晚情况 -->
    <el-card v-if="nightEventsOnly.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Moon /></el-icon>
          <span>夜晚情况 ({{ nightEventsOnly.length }}个)</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="event in nightEventsOnly"
          :key="`${event.day}-${event.phase}`"
          type="primary"
        >
          <!-- 夜晚事件 -->
          <div class="night-event">
            <div class="day-label">第{{ event.displayNightIndex }}夜</div>
            <div class="event-tags">
              <el-tag v-if="event.wolf_kill_target" type="danger" size="small">
                🐺 刀 {{ event.wolf_kill_target }}号
              </el-tag>
              <el-tag v-if="event.witch_save_target" type="success" size="small">
                💊 救 {{ event.witch_save_target }}号
              </el-tag>
              <el-tag v-if="event.witch_poison_target" type="warning" size="small">
                ☠️ 毒 {{ event.witch_poison_target }}号
              </el-tag>
              <el-tag v-if="event.guard_target" type="primary" size="small">
                🛡️ 守 {{ event.guard_target }}号
              </el-tag>
              <el-tag v-if="event.seer_or_medium_check" type="info" size="small">
                🔮 验 {{ event.seer_or_medium_check }}
              </el-tag>
              <!-- 机械狼行动 -->
              <el-tag v-if="event.mechanic_wolf_learn" type="danger" size="small" effect="dark">
                🤖 学 {{ event.mechanic_wolf_learn }}号
              </el-tag>
              <el-tag v-if="event.mechanic_wolf_kill" type="danger" size="small" effect="dark">
                🤖 刀 {{ event.mechanic_wolf_kill }}号
              </el-tag>
            </div>
            <div v-if="event.night_outcome_summary" class="outcome-summary">
              {{ event.night_outcome_summary }}
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 投票记录 -->
    <el-card v-if="voteTables.length > 0" class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <el-icon><Collection /></el-icon>
          <span>投票记录 ({{ voteTables.length }}天)</span>
        </div>
      </template>
      <div class="vote-list">
        <div v-for="vote in voteTables" :key="vote.day" class="vote-day">
          <div class="vote-day-header">第{{ vote.day }}天投票</div>
          <div class="vote-chips">
            <el-tag
              v-for="(target, voter) in vote.votes"
              :key="voter"
              :type="target === vote.voted_out ? 'danger' : 'info'"
              size="small"
              class="vote-tag"
            >
              {{ voter }}号 → {{ target }}号
            </el-tag>
          </div>
          <div v-if="vote.voted_out" class="voted-out">
            出局: <el-tag type="danger" size="small">{{ vote.voted_out }}号</el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Trophy, User, Medal, Moon, CircleCheck, CircleClose, Collection, ArrowRight, ArrowLeft, Document } from '@element-plus/icons-vue'

interface Player {
  fact_role: string
  police_badge: {
    went_for_sheriff: string
    won_badge: string
    badge_transfer_in: string | null
    badge_transfer_out: string | null
  }
  elimination: {
    night_killed_on_day: number | null
    poisoned_on_day: number | null
    voted_out_on_day: number | null
    self_exploded_on_day: number | null
    shot_by_hunter_on_day: number | null
    killed_by_mechanic_hunter_on_day: number | null
    final_status: string
  }
}

interface NightEvent {
  day: number
  phase?: 'night' | 'sheriff_vote'  // night=夜晚, sheriff_vote=警上竞选
  wolf_kill_target: string
  witch_save_target: string
  witch_poison_target: string
  guard_target: string
  seer_or_medium_check: string
  mechanic_wolf_action?: string
  mechanic_wolf_learn?: string
  mechanic_wolf_kill?: string
  night_outcome_summary?: string
}

interface VoteTable {
  day: number
  votes: Record<string, string>
  voted_out: string
}

interface SheriffVoteTable {
  votes: Record<string, string>
  winner: string | null
}

interface Segment {
  type: 'sheriff_vote' | 'daytime' | 'night_commentary'
  day: number
  name: string
  start_anchor: string
  end_anchor: string
  contains_commentary: boolean
  for_stage2: boolean
  text?: string
  start_pos?: number
  end_pos?: number
}

interface Stage1Result {
  class_1_structured_facts?: {
    players?: Record<string, Player>
    night_events_by_day?: NightEvent[]
    day_vote_tables?: VoteTable[]
    sheriff_vote_table?: SheriffVoteTable
    global_result?: {
      winner: string
      fact_summary: string
    }
  }
  meta?: {
    game_name: string
    segments?: Segment[]
  }
}

const props = defineProps<{
  result: Stage1Result
}>()

const data = computed(() => props.result?.class_1_structured_facts)

const globalResult = computed(() => data.value?.global_result)

const sheriffVoteTable = computed(() => data.value?.sheriff_vote_table)
const winnerText = computed(() => {
  const winner = globalResult.value?.winner
  if (winner?.includes('狼')) return '狼人阵营获胜'
  if (winner?.includes('好人') || winner?.includes('平民')) return '好人阵营获胜'
  return winner || '未知'
})
const winnerType = computed(() => {
  const winner = globalResult.value?.winner
  if (winner?.includes('狼')) return 'danger'
  if (winner?.includes('好人') || winner?.includes('平民')) return 'success'
  return 'info'
})

const playerList = computed(() => {
  const players = data.value?.players || {}
  return Object.entries(players).map(([id, info]) => ({
    id,
    ...info
  }))
})
const playerCount = computed(() => playerList.value.length)

const nightEvents = computed(() => data.value?.night_events_by_day || [])

// 夜晚情况：只显示夜晚事件（过滤掉警上竞选），显示为第0夜、第1夜...
const nightEventsOnly = computed(() => {
  const nightEventsList = nightEvents.value
    .filter((e: any) => e.phase !== 'sheriff_vote')  // 过滤掉警上竞选
    .sort((a: any, b: any) => a.day - b.day)  // 按天数排序

  // 重新编号：第1夜显示为第0夜，第2夜显示为第1夜...
  return nightEventsList.map((e: any, index: number) => ({
    ...e,
    displayNightIndex: index  // 第0夜、第1夜...
  }))
})

// 对局分段
const segments = computed(() => props.result?.meta?.segments || [])
const segmentsList = computed(() => {
  return segments.value.map((seg: Segment) => ({
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

const voteTables = computed(() => data.value?.day_vote_tables || [])

// 上警玩家列表
const sheriffCandidates = computed(() => {
  return playerList.value.filter(p => p.police_badge?.went_for_sheriff === 'yes')
})

// 警下玩家列表
const sheriffVoters = computed(() => {
  return playerList.value.filter(p => p.police_badge?.went_for_sheriff !== 'yes')
})

// 警徽投票完整详情（表格用）
const sheriffVoteDetails = computed(() => {
  return playerList.value.map(p => ({
    id: p.id,
    wentForSheriff: p.police_badge?.went_for_sheriff === 'yes',
    voteTarget: sheriffVoteTable.value?.votes?.[p.id] || (p.police_badge?.went_for_sheriff === 'yes' ? '自投' : '未投')
  }))
})

function getRoleType(role: string): 'danger' | 'success' | 'warning' | 'info' {
  if (!role) return 'info'
  if (role.includes('狼')) return 'danger'
  if (role.includes('平民')) return 'success'
  if (['通灵师', '预言家', '女巫', '猎人', '守卫'].some(r => role.includes(r))) return 'warning'
  return 'info'
}

function getEliminationType(elimination: Player['elimination']): 'danger' | 'warning' | 'info' | 'success' {
  if (elimination?.night_killed_on_day) return 'danger'
  if (elimination?.voted_out_on_day) return 'warning'
  if (elimination?.poisoned_on_day) return 'danger'
  if (elimination?.self_exploded_on_day) return 'danger'
  if (elimination?.shot_by_hunter_on_day) return 'danger'
  if (elimination?.killed_by_mechanic_hunter_on_day) return 'danger'
  if (elimination?.final_status === '存活') return 'success'
  return 'info'
}

function getEliminationText(elimination: Player['elimination']): string {
  if (elimination?.night_killed_on_day) return `第${elimination.night_killed_on_day}天夜亡`
  if (elimination?.voted_out_on_day) return `第${elimination.voted_out_on_day}天放逐`
  if (elimination?.poisoned_on_day) return `第${elimination.poisoned_on_day}天毒杀`
  if (elimination?.self_exploded_on_day) return `第${elimination.self_exploded_on_day}天自爆`
  if (elimination?.shot_by_hunter_on_day) return `第${elimination.shot_by_hunter_on_day}天被猎人带走`
  if (elimination?.killed_by_mechanic_hunter_on_day) return `第${elimination.killed_by_mechanic_hunter_on_day}天被机械猎人带走`
  if (elimination?.final_status === '存活') return '存活'
  return elimination?.final_status || '未知'
}

function getTimelineType(event: NightEvent): 'danger' | 'warning' | 'primary' | 'success' | 'info' {
  if (event.witch_poison_target) return 'danger'
  if (event.wolf_kill_target && !event.witch_save_target) return 'danger'
  if (event.witch_save_target) return 'success'
  return 'primary'
}
</script>

<style scoped>
.stage1-result {
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

.winner-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
}

.winner-info .summary {
  margin: 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.player-table {
  margin-top: 8px;
}

.night-event {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.day-label {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.event-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.outcome-summary {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.vote-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vote-day {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.vote-day-header {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  font-size: 14px;
}

.vote-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.voted-out {
  font-size: 13px;
  color: #606266;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #dcdfe6;
}

/* Sheriff Vote Table */
.sheriff-votes {
  padding: 8px 0;
}

.vote-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

.vote-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
  font-size: 13px;
  transition: all 0.3s;
}

.vote-item:hover {
  background: #ecf5ff;
  transform: translateY(-2px);
}

.vote-item.self-vote {
  background: #fdf6ec;
}

.vote-item.winner-vote {
  background: #f0f9ff;
  border: 1px solid #a0cfff;
  font-weight: 500;
}

.vote-item .voter {
  color: #606266;
  min-width: 30px;
}

.vote-item .arrow {
  color: #c0c4cc;
  font-size: 12px;
}

.vote-item .target {
  color: #303133;
  font-weight: 500;
}

.vote-item.winner-vote .target {
  color: #409eff;
}

.badge-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.medal-icon {
  margin: 0 2px;
}

/* Sheriff Table Styles */
.sheriff-table {
  margin-bottom: 16px;
}

.sheriff-table .winner-text {
  color: #e6a23c;
  font-weight: 700;
}

.vote-target-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.vote-target {
  color: #606266;
}

.vote-target.is-winner {
  color: #409eff;
  font-weight: 600;
}

.sheriff-stats {
  display: flex;
  justify-content: space-around;
  padding-top: 16px;
  border-top: 1px dashed #dcdfe6;
}
</style>
