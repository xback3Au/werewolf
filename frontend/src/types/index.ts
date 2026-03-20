// WebSocket message types
export interface WSMessage {
  type: 'stage_start' | 'stage_complete' | 'day_progress' | 'reasoning' | 'content' | 'player_update' | 'progress' | 'error' | 'saved' | 'analysis_complete'
  task_id?: string
  data: any
  timestamp?: number
}

// Analysis stage
export interface StageInfo {
  stage: number
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: number
  result?: any
}

// Segment for Stage 1 text segmentation
export interface Segment {
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

// Player inference (real-time from Stage 3)
export interface PlayerInference {
  player_id: string
  day: number
  role_guess: string
  wolf_probability: number
  good_probability: number
  specific_role_guess?: string
  reason: string
  confidence: number
  timestamp: string
}

// Analysis task
export interface AnalysisTask {
  id: string
  gameName: string
  formatName: string
  label?: string
  status: 'idle' | 'analyzing' | 'completed' | 'error'
  stages: Record<number, StageInfo>
  reasoning_log: ReasoningEntry[]
  player_inferences: Record<string, PlayerInference[]>
  current_stage?: number
  error_message?: string
}

export interface ReasoningEntry {
  stage: number
  content: string
  timestamp: number
  delta?: string  // 本次新增的内容（增量）
}

// Format info
export interface FormatInfo {
  name: string
  file_path: string
  size: number
}

// 单个文件信息
export interface FileInfo {
  file_id: string
  filename: string
  file_path: string
  size: number
  uploaded_at: string
}

// 文件组（一组相关的文件：正文+复盘）
export interface FileGroup {
  group_id: string
  label?: string
  main_file: FileInfo | null
  postgame_file: FileInfo | null
  total_files: number
  uploaded_at: string
  analysis_status: 'not_started' | 'stage1' | 'stage2' | 'stage3' | 'completed'
  completed_stages: number[]
  has_analysis: boolean
  analysis_id?: string
  format_name?: string
}

// 兼容旧代码
export type UploadedFile = FileGroup

// Saved analysis
export interface SavedAnalysis {
  id: string
  label?: string
  game_name: string
  format_name: string
  created_at: string
  updated_at: string
}

// Stage results
export interface Stage1Result {
  meta: {
    game_name: string
    version?: string
    segments?: Segment[]  // 新的分段信息
    segmentation?: {
      segment_1_noise: { summary: string }
      segment_2_gameplay: { summary: string }
      segment_3_postgame: { summary: string }
    }
  }
  class_1_structured_facts: {
    players: Record<string, PlayerFact>
    night_events_by_day: NightEvent[]
    day_vote_tables: DayVoteTable[]
    sheriff_vote_table?: SheriffVoteTable
    global_result: GlobalResult
  }
}

export interface PlayerFact {
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
  day_votes: DayVote[]
}

export interface DayVote {
  day: number
  target: string
  round: string
}

export interface NightEvent {
  day: number
  phase: 'night' | 'sheriff_vote'  // night=夜晚, sheriff_vote=警上竞选
  wolf_kill_target: string
  witch_save_target: string
  witch_poison_target: string
  guard_target: string
  seer_or_medium_check: string
  mechanic_wolf_action?: string
  mechanic_wolf_learn?: string  // 机械狼学习的目标
  mechanic_wolf_kill?: string   // 机械狼开刀目标
  night_outcome_summary?: string
}

export interface DayVoteTable {
  day: number
  votes: Record<string, string>
  voted_out: string
}

export interface SheriffVoteTable {
  votes: Record<string, string>
  winner: string | null
  evidence?: string[]
}

export interface GlobalResult {
  winner: string
  fact_summary: string
}

export interface Stage2Result {
  class_2_daytime_speeches: Speech[]
  class_3_commentator_content: {
    segments: CommentatorSegment[]
  }
}

export interface Speech {
  day: number
  speaker: number
  speech_order: number | string
  text_summary: string       // 精炼摘要，用于快速浏览
  text_full?: string         // 完整发言原文，用于深度分析
  claims: string[]
  stance: {
    supports: string[]
    attacks: string[]
    neutral_mentions: string[]
  }
  intent_tags: string[]
}

export interface CommentatorSegment {
  phase: string
  summary: string
  useful_for_intent_analysis: string
  why_useful: string
}

export interface Stage3Result {
  intent_analysis_engine: {
    phase_A_blind_inference: {
      description?: string
      analysis_method?: string
      key_players?: string[]
      per_day_updates: DayInference[]
    }
    phase_B_reveal_validation: {
      compare_with_truth: ValidationItem[]
      overall_accuracy: {
        role_accuracy: number
        camp_accuracy: number
      }
      lesson_learned?: string
    }
    phase_C_refined_intents: Record<string, PlayerIntent>
  }
}

export interface DayInference {
  day: number
  player_inference: Record<string, {
    role_probabilities: {
      wolf: number
      good: number
      specific_role_guess: string
    }
    reason: string
    is_key_player?: boolean
    depth_analysis?: string
  }>
}

export interface ValidationItem {
  player: string
  blind_guess: string
  truth: string
  is_correct: boolean
  error_type: string
  missed_signals?: string[]
  wrong_logic?: string
  fix_suggestion: string
}

export interface PlayerIntent {
  final_role: string
  intent_timeline: IntentTimelineItem[]
  key_turning_points: string[]
}

export interface IntentTimelineItem {
  day: number
  main_intent: string
  sub_intents: string[]
  confidence: number
  evidence: string[]
}
