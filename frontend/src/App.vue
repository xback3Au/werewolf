<template>
  <div class="app">
    <el-container>
      <el-header class="app-header">
        <div class="header-content">
          <div class="logo">
            <span class="title">狼人杀分析系统</span>
          </div>
          <div class="actions">
            <el-tag v-if="isConnected" type="success">已连接</el-tag>
            <el-tag v-else type="info">未连接</el-tag>
          </div>
        </div>
      </el-header>

      <el-main class="app-main">
        <UploadSection v-if="!isAnalyzing && !hasResult" @start-analysis="startAnalysis" />
        <AnalysisProgress
          v-else-if="isAnalyzing || (hasResult && !showResultsView)"
          @view-results="showResultsView = true"
        />
        <ResultsView v-else-if="hasResult && showResultsView" @new-analysis="resetAnalysis" />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAnalysisStore } from '@/stores/analysis'
import UploadSection from '@/components/UploadSection.vue'
import AnalysisProgress from '@/components/AnalysisProgress.vue'
import ResultsView from '@/components/ResultsView.vue'

const store = useAnalysisStore()
const { isConnected, isAnalyzing, hasResult, currentTask } = storeToRefs(store)

// 控制是否显示 ResultsView（分析完成后默认显示 AnalysisProgress）
const showResultsView = ref(false)

// Debug: 跟踪状态变化
watch(isAnalyzing, (val) => console.log('[App] isAnalyzing changed:', val))
watch(hasResult, (val) => console.log('[App] hasResult changed:', val))
watch(() => currentTask.value?.status, (val) => console.log('[App] task status changed:', val))

async function startAnalysis(config: {
  mainFilePath: string
  postgameFilePath?: string
  formatPath: string
  gameName: string
  label?: string
  mainFileId: string
  postgameFileId?: string
  completedStages: number[]
  hasExistingAnalysis: boolean
  startStage?: number
}) {
  const completedStages = config.completedStages || []
  const userStartStage = config.startStage || 1

  console.log(`[App] startAnalysis called with startStage: ${config.startStage}, userStartStage: ${userStartStage}, completedStages:`, completedStages)

  // 如果用户指定了从某个阶段开始（不是从第1阶段开始），跳过询问逻辑
  const isExplicitStartStage = userStartStage > 1

  // 如果已经完成了所有阶段，询问是否重新分析（仅在用户没有明确指定起始阶段时）
  if (!isExplicitStartStage && completedStages.length === 3) {
    const reanalyze = await ElMessageBox.confirm(
      '该文件已完成全部3个阶段的分析，是否重新分析？',
      '分析已完成',
      {
        confirmButtonText: '重新分析',
        cancelButtonText: '查看结果',
        type: 'info'
      }
    ).then(() => true).catch(() => false)

    if (!reanalyze) {
      // 加载已有结果
      try {
        const response = await fetch(`/api/analyses/${config.mainFileId}`)
        if (response.ok) {
          const historyData = await response.json()
          store.loadHistoryResult(historyData)
          ElMessage.success('已加载分析结果')
          return
        }
      } catch (e) {
        console.error('加载历史结果失败:', e)
      }
    } else {
      // 选择重新分析，删除后端已有记录
      try {
        const response = await fetch(`/api/analyses/by-file?file_id=${config.mainFileId}`, {
          method: 'DELETE'
        })
        if (!response.ok) {
          console.error('删除已有分析失败')
        } else {
          console.log('已删除旧分析记录，将重新开始')
        }
      } catch (e) {
        console.error('删除已有分析失败:', e)
      }
      completedStages.length = 0
    }
  }

  // 如果用户明确指定了起始阶段，删除从该阶段开始的所有数据
  if (isExplicitStartStage && completedStages.length >= userStartStage - 1) {
    try {
      // 调用后端API删除指定阶段及之后的数据
      const response = await fetch(
        `/api/analyses/by-file?file_id=${config.mainFileId}&from_stage=${userStartStage}`,
        { method: 'DELETE' }
      )
      if (!response.ok) {
        console.error(`删除阶段${userStartStage}及之后的数据失败`)
      } else {
        console.log(`已删除阶段${userStartStage}及之后的数据，将从阶段${userStartStage}重新开始`)
      }
    } catch (e) {
      console.error('删除已有分析数据失败:', e)
    }
    // 更新completedStages，只保留用户指定阶段之前的
    const newCompletedStages = completedStages.filter(s => s < userStartStage)
    completedStages.length = 0
    completedStages.push(...newCompletedStages)
    ElMessage.info(`将从阶段${userStartStage}开始重新分析，保留前${userStartStage - 1}个阶段的结果`)
  }

  // 如果已完成部分阶段且用户没有明确指定起始阶段，询问是否继续
  if (!isExplicitStartStage && completedStages.length > 0 && completedStages.length < 3) {
    const nextStage = completedStages.length + 1
    const useResume = await ElMessageBox.confirm(
      `该文件已完成 ${completedStages.length} 个阶段的分析，是否从阶段${nextStage}继续？`,
      '发现未完成分析',
      {
        confirmButtonText: '继续分析',
        cancelButtonText: '重新分析',
        type: 'info'
      }
    ).then(() => true).catch(() => false)

    if (!useResume) {
      // 重新分析，删除后端已有记录
      try {
        const response = await fetch(`/api/analyses/by-file?file_id=${config.mainFileId}`, {
          method: 'DELETE'
        })
        if (!response.ok) {
          console.error('删除已有分析失败')
        } else {
          console.log('已删除旧分析记录，将重新开始')
        }
      } catch (e) {
        console.error('删除已有分析失败:', e)
      }
      completedStages.length = 0
    }
  }

  // 重置结果显示状态
  showResultsView.value = false

  const taskId = Date.now().toString()
  store.initTask(taskId, config.gameName, config.formatPath, config.label)

  // 如果有已完成的阶段，加载它们的结果
  if (completedStages.length > 0) {
    try {
      const response = await fetch(`/api/analyses/${config.mainFileId}`)
      if (response.ok) {
        const historyData = await response.json()
        // 预填充已完成的阶段结果
        if (completedStages.includes(1)) {
          store.completeStage(1, historyData.stage1_result)
        }
        if (completedStages.includes(2)) {
          store.completeStage(2, historyData.stage2_result)
        }
        if (completedStages.includes(3)) {
          store.completeStage(3, historyData.stage3_result)
        }
      }
    } catch (e) {
      console.error('加载已完成阶段失败:', e)
    }
  }

  // 确定实际开始的阶段：优先使用用户指定的起始阶段，否则自动计算下一个阶段
  const actualStartStage = isExplicitStartStage
    ? userStartStage
    : completedStages.length + 1

  console.log(`[App] actualStartStage: ${actualStartStage}, isExplicitStartStage: ${isExplicitStartStage}, completedStages after filter:`, completedStages)

  try {
    await store.connectWebSocket(
      taskId,
      config.mainFilePath,
      config.formatPath,
      config.gameName,
      config.label,
      config.mainFileId,
      actualStartStage,  // 使用确定的起始阶段
      config.postgameFilePath,
      config.postgameFileId
    )
  } catch (error: any) {
    ElMessage.error(error.message || '连接失败')
  }
}

function resetAnalysis() {
  store.disconnect()
  // 手动重置状态（setup 语法的 Pinia store 不支持 $reset）
  store.currentTask = null
  store.reasoningLog = []
  store.contentLog = []
  store.playerInferences = {}
  showResultsView.value = false
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  background-color: #f5f7fa;
}
</style>

<style scoped>
.app {
  min-height: 100vh;
}
.app-header {
  background: white;
  border-bottom: 1px solid #dcdfe6;
  padding: 0 20px;
}
.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}
.title {
  font-size: 20px;
  font-weight: bold;
}
.app-main {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
