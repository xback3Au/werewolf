/**
 * 【文件定位】
 * 前端全局状态管理（Pinia Store）
 *
 * 【核心职责】
 * 1. 管理 WebSocket 连接（建立/断开/重连）
 * 2. 存储当前分析任务状态（currentTask）
 * 3. 存储实时推理日志（reasoningLog）- AI的思考过程
 * 4. 存储正式输出（contentLog）- AI的JSON输出
 * 5. 存储玩家推断历史（playerInferences）- 目前未使用
 *
 * 【数据流】
 * 用户操作 → 调用 store 方法 → 更新 state → 组件响应式更新 → UI变化
 *
 * 【与后端的通信】
 * 通过 WebSocket 接收消息类型：
 * - stage_start: 阶段开始，更新当前阶段状态
 * - stage_complete: 阶段完成，保存结果
 * - reasoning: AI思考内容，追加到日志
 * - content: AI正式输出，解析并保存
 * - analysis_complete: 全部完成
 * - saved: 结果已保存到数据库
 * - error: 出错
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnalysisTask, StageInfo, PlayerInference, ReasoningEntry, WSMessage } from '@/types'

export const useAnalysisStore = defineStore('analysis', () => {
  // ═══════════════════════════════════════════════════════════
  // State（状态）
  // ═══════════════════════════════════════════════════════════

  /** 当前分析任务，包含三阶段状态、结果等 */
  const currentTask = ref<AnalysisTask | null>(null)

  /** WebSocket 连接实例 */
  const wsConnection = ref<WebSocket | null>(null)

  /** 是否已连接到 WebSocket */
  const isConnected = ref(false)

  /** 推理日志：存储 AI 的思考过程（reasoning_content） */
  const reasoningLog = ref<ReasoningEntry[]>([])

  /** 正式输出日志：存储 AI 的正式输出（content） */
  const contentLog = ref<ReasoningEntry[]>([])

  /** 玩家推断历史：每天每个玩家的推断（目前未使用） */
  const playerInferences = ref<Record<string, PlayerInference[]>>({})

  // ═══════════════════════════════════════════════════════════
  // Computed（计算属性）
  // ═══════════════════════════════════════════════════════════

  /** 当前正在运行的阶段 */
  const currentStage = computed(() => {
    if (!currentTask.value) return null
    const stages = Object.values(currentTask.value.stages)
    // 找到 running 的阶段，如果没有则返回最后一个
    return stages.find(s => s.status === 'running') || stages[stages.length - 1]
  })

  /** 是否正在分析中 */
  const isAnalyzing = computed(() => {
    return currentTask.value?.status === 'analyzing'
  })

  /** 是否有分析结果（已完成） */
  const hasResult = computed(() => {
    return currentTask.value?.status === 'completed'
  })

  const stage1Result = computed(() => {
    return currentTask.value?.stages[1]?.result
  })

  const stage2Result = computed(() => {
    return currentTask.value?.stages[2]?.result
  })

  const stage3Result = computed(() => {
    return currentTask.value?.stages[3]?.result
  })

  // Actions
  function initTask(taskId: string, gameName: string, formatName: string, label?: string) {
    currentTask.value = {
      id: taskId,
      gameName,
      formatName,
      label,
      status: 'analyzing',
      stages: {
        1: { stage: 1, name: '事实抽取', status: 'pending' },
        2: { stage: 2, name: '发言整理', status: 'pending' },
        3: { stage: 3, name: '意图分析', status: 'pending' }
      },
      reasoning_log: [],
      player_inferences: {}
    }
    reasoningLog.value = []
    contentLog.value = []
    playerInferences.value = {}
  }

  function loadHistoryResult(data: any) {
    currentTask.value = {
      id: data.id,
      gameName: data.game_name,
      formatName: data.format_name,
      label: data.label,
      status: 'completed',
      stages: {
        1: { stage: 1, name: '事实抽取', status: 'completed', result: data.stage1_result },
        2: { stage: 2, name: '发言整理', status: 'completed', result: data.stage2_result },
        3: { stage: 3, name: '意图分析', status: 'completed', result: data.stage3_result }
      },
      reasoning_log: [],
      player_inferences: {}
    }
  }

  // ═══════════════════════════════════════════════════════════
  // Actions（操作）
  // ═══════════════════════════════════════════════════════════

  /**
   * 初始化新任务
   * 在点击"开始分析"时调用
   */
  function initTask(taskId: string, gameName: string, formatName: string, label?: string) {
    currentTask.value = {
      id: taskId,
      gameName,
      formatName,
      label,
      status: 'analyzing',
      stages: {
        1: { stage: 1, name: '事实抽取', status: 'pending' },
        2: { stage: 2, name: '发言整理', status: 'pending' },
        3: { stage: 3, name: '意图分析', status: 'pending' }
      },
      reasoning_log: [],
      player_inferences: {}
    }
    reasoningLog.value = []
    contentLog.value = []
    playerInferences.value = {}
  }

  /**
   * 加载历史分析结果
   * 在查看过往分析时调用
   */
  function loadHistoryResult(data: any) {
    currentTask.value = {
      id: data.id,
      gameName: data.game_name,
      formatName: data.format_name,
      label: data.label,
      status: 'completed',
      stages: {
        1: { stage: 1, name: '事实抽取', status: 'completed', result: data.stage1_result },
        2: { stage: 2, name: '发言整理', status: 'completed', result: data.stage2_result },
        3: { stage: 3, name: '意图分析', status: 'completed', result: data.stage3_result }
      },
      reasoning_log: [],
      player_inferences: {}
    }
  }

  /**
   * 开始某个阶段
   * 收到后端 stage_start 消息时调用
   */
  function startStage(stageNum: number) {
    if (!currentTask.value) return
    currentTask.value.stages[stageNum].status = 'running'
  }

  /**
   * 完成某个阶段
   * 收到后端 stage_complete 消息时调用
   * 保存该阶段的分析结果
   */
  function completeStage(stageNum: number, result: any) {
    if (!currentTask.value) return
    const stage = currentTask.value.stages[stageNum]
    if (!stage) return
    stage.status = 'completed'
    stage.result = result
  }

  /**
   * 添加推理日志
   * 收到后端 reasoning 消息时调用
   * @param stage 当前阶段 1/2/3
   * @param content 完整内容
   * @param delta 新增的内容片段（流式）
   */
  function addReasoning(stage: number, content: string, delta?: string) {
    const entry: ReasoningEntry = {
      stage,
      content,
      timestamp: Date.now(),
      delta
    }
    reasoningLog.value.push(entry)
    // 限制日志长度，防止内存溢出
    if (reasoningLog.value.length > 500) {
      reasoningLog.value = reasoningLog.value.slice(-500)
    }
  }

  /**
   * 添加正式输出内容
   * 收到后端 content 消息时调用
   * 这是 AI 的正式输出（JSON），与 reasoning 不同
   */
  function addContent(stage: number, content: string, delta?: string) {
    const entry: ReasoningEntry = {
      stage,
      content,
      timestamp: Date.now(),
      delta
    }
    contentLog.value.push(entry)
    if (contentLog.value.length > 500) {
      contentLog.value = contentLog.value.slice(-500)
    }
  }

  /**
   * 更新玩家推断（目前未使用）
   */
  function updatePlayerInference(inference: PlayerInference) {
    if (!playerInferences.value[inference.player_id]) {
      playerInferences.value[inference.player_id] = []
    }
    playerInferences.value[inference.player_id].push(inference)
  }

  /**
   * 标记任务完成
   * 收到后端 analysis_complete 消息时调用
   */
  function completeTask() {
    if (!currentTask.value) return
    currentTask.value.status = 'completed'
  }

  /**
   * 设置错误状态
   * 收到后端 error 消息或 WebSocket 断开时调用
   */
  function setError(message: string) {
    if (!currentTask.value) return
    // 如果任务已经完成，不覆盖状态（防止 WebSocket 关闭时覆盖已完成状态）
    if (currentTask.value.status === 'completed') {
      console.log('[Store] Ignoring error because task is already completed:', message)
      return
    }
    currentTask.value.status = 'error'
    currentTask.value.error_message = message
  }

  /**
   * 断开 WebSocket 连接
   */
  function disconnect() {
    wsConnection.value?.close()
    wsConnection.value = null
    isConnected.value = false
  }

  // ═══════════════════════════════════════════════════════════
  // WebSocket 连接管理
  // ═══════════════════════════════════════════════════════════

  /**
   * 建立 WebSocket 连接并开始分析（双文件版本）
   *
   * 【流程】
   * 1. 创建 WebSocket 连接到后端
   * 2. 连接成功后发送配置（双文件路径、游戏名等）
   * 3. 后端开始分析，通过 onmessage 接收实时消息
   *
   * 【参数】
   * @param taskId 任务ID
   * @param mainTranscriptPath 正文文件路径（相对于项目根目录）
   * @param formatPath 版型规则文件路径
   * @param gameName 游戏名称
   * @param label 可选标签，如 "260312-第四局"
   * @param mainFileId 主文件ID，用于关联数据库记录
   * @param resumeFromStage 断点续传：从第几阶段开始（1/2/3）
   * @param postgameTranscriptPath 复盘文件路径（可选）
   * @param postgameFileId 复盘文件ID（可选）
   */
  async function connectWebSocket(
    taskId: string,
    mainTranscriptPath: string,
    formatPath: string,
    gameName: string,
    label?: string,
    mainFileId?: string,
    resumeFromStage?: number,
    postgameTranscriptPath?: string,
    postgameFileId?: string
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://localhost:8000/ws/analyze/${taskId}`)

      // 连接建立
      ws.onopen = () => {
        isConnected.value = true
        wsConnection.value = ws

        // 发送分析配置给后端（双文件版本）
        const config: any = {
          main_transcript_path: mainTranscriptPath,
          format_path: formatPath,
          game_name: gameName
        }
        if (label) config.label = label
        if (mainFileId) config.main_file_id = mainFileId
        if (resumeFromStage) config.start_stage = resumeFromStage
        console.log(`[WebSocket] Connecting with start_stage: ${resumeFromStage}, config:`, config)
        // 双文件支持
        if (postgameTranscriptPath) config.postgame_transcript_path = postgameTranscriptPath
        if (postgameFileId) config.postgame_file_id = postgameFileId

        ws.send(JSON.stringify(config))
        resolve()
      }

      // 接收消息
      ws.onmessage = (event) => {
        const msg: WSMessage = JSON.parse(event.data)
        handleWebSocketMessage(msg)
      }

      // 连接错误
      ws.onerror = (error) => {
        isConnected.value = false
        console.error('WebSocket error:', error)
        reject(new Error('连接失败，请检查后端服务是否运行'))
      }

      // 连接关闭
      ws.onclose = (event) => {
        isConnected.value = false
        wsConnection.value = null
        console.log(`[WebSocket] Closed with code: ${event.code}`)

        // 如果任务已经完成或出错，忽略关闭事件
        if (currentTask.value?.status === 'completed' || currentTask.value?.status === 'error') {
          console.log('[WebSocket] Task already in final state, ignoring close event')
          return
        }

        // 非正常关闭（code 1000=正常关闭, 1001=离开页面）
        if (event.code !== 1000 && event.code !== 1001) {
          console.error(`WebSocket closed unexpectedly: ${event.code}`)
          setError(`连接意外断开 (code: ${event.code})，请刷新页面重试`)
        }
      }
    })
  }

  /**
   * 处理 WebSocket 消息
   * 根据消息类型分发到不同的处理函数
   */
  /**
   * 处理 WebSocket 消息
   * 根据消息类型分发到不同的处理函数
   *
   * 【消息类型】
   * - stage_start: 某个阶段开始
   * - stage_complete: 某个阶段完成，包含结果
   * - day_progress: 某一天的处理进度（Stage 2 分批处理时使用）
   * - reasoning: AI 思考内容（流式）
   * - content: AI 正式输出（流式）
   * - player_update: 玩家推断更新（目前未使用）
   * - analysis_complete: 所有阶段完成
   * - saved: 结果已保存到数据库
   * - error: 出错
   */
  function handleWebSocketMessage(msg: WSMessage) {
    console.log('[WS] Received message type:', msg.type)

    switch (msg.type) {
      case 'stage_start':
        // 阶段开始，更新状态为 running
        startStage(msg.data.stage)
        break

      case 'stage_complete':
        // 阶段完成，保存结果
        completeStage(msg.data.stage, msg.data.result)
        break

      case 'day_progress':
        // Stage 2 某天处理进度（仅记录日志，不修改阶段状态）
        console.log(`[Day Progress] Stage ${msg.data.stage}, Day ${msg.data.day}: ${msg.data.message}`)
        break

      case 'reasoning':
        // AI 思考内容（DeepSeek 的 reasoning_content）
        // content = 累积的完整内容, delta = 本次新增
        addReasoning(msg.data.stage, msg.data.content, msg.data.delta)
        break

      case 'content':
        // AI 正式输出（JSON 格式的分析结果）
        addContent(msg.data.stage, msg.data.content, msg.data.delta)
        break

      case 'player_update':
        // 玩家推断更新（预留功能，目前未使用）
        updatePlayerInference(msg.data.inference)
        break

      case 'analysis_complete':
        // 所有阶段分析完成
        completeTask()
        break

      case 'saved':
        // 结果已保存到数据库
        console.log('[WebSocket] Analysis saved:', msg.data)
        break

      case 'error':
        // 后端报错
        setError(msg.data.message)
        break

      default:
        console.warn('[WS] Unknown message type:', msg.type)
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 导出的状态和方法（供组件使用）
  // ═══════════════════════════════════════════════════════════
  return {
    // State（响应式数据）
    currentTask,      // 当前任务
    isConnected,      // WebSocket 连接状态
    reasoningLog,     // AI 思考日志
    contentLog,       // AI 正式输出日志
    playerInferences, // 玩家推断历史

    // Computed（计算属性）
    currentStage,     // 当前运行的阶段
    isAnalyzing,      // 是否正在分析
    hasResult,        // 是否有结果
    stage1Result,     // Stage1 结果
    stage2Result,     // Stage2 结果
    stage3Result,     // Stage3 结果

    // Actions（方法）
    initTask,         // 初始化任务
    connectWebSocket, // 连接 WebSocket
    disconnect,       // 断开连接
    loadHistoryResult // 加载历史结果
  }
})
