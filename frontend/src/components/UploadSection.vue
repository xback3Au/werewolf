<template>
  <div class="upload-section">
    <!-- 双文件上传卡片 -->
    <el-card class="upload-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <div class="icon-circle">
              <el-icon size="24"><Document /></el-icon>
            </div>
            <span>上传对局文件</span>
          </div>
        </div>
      </template>

      <!-- 正文上传（必填） -->
      <div class="upload-item">
        <div class="upload-label">
          <span class="label-text">① 游戏正文</span>
          <span class="label-required">（必填）</span>
          <el-tooltip content="从321天亮了开始到游戏结束前的文本，包含警上、白天发言、投票">
            <el-icon class="label-help"><Info-Filled /></el-icon>
          </el-tooltip>
        </div>
        <el-upload
          class="upload-area"
          drag
          action="/api/upload"
          :on-success="(res) => handleUploadSuccess(res, 'main')"
          :on-error="handleUploadError"
          :limit="1"
          accept=".txt"
          :disabled="!!uploadedFiles.main"
        >
          <div class="upload-content" v-if="!uploadedFiles.main">
            <div class="upload-icon-bg">
              <el-icon class="upload-icon" size="40"><Upload-filled /></el-icon>
            </div>
            <div class="upload-text">
              <p class="main-text">拖拽正文文件到此处，或 <em>点击上传</em></p>
              <p class="sub-text">包含警上、白天发言、投票等内容</p>
            </div>
          </div>
          <div v-else class="uploaded-content">
            <el-icon class="success-icon" size="32"><Circle-Check /></el-icon>
            <span class="uploaded-name">{{ uploadedFiles.main.filename }}</span>
            <el-button type="danger" link size="small" @click.stop="removeFile('main')">
              移除
            </el-button>
          </div>
        </el-upload>
      </div>

      <!-- 复盘上传（可选） -->
      <div class="upload-item">
        <div class="upload-label">
          <span class="label-text">② 赛后复盘</span>
          <span class="label-optional">（可选）</span>
          <el-tag type="warning" size="small" effect="light">强烈建议上传</el-tag>
          <el-tooltip content="包含真实身份公布、夜间行动详情的复盘文本，可大幅提高分析准确性">
            <el-icon class="label-help"><Info-Filled /></el-icon>
          </el-tooltip>
        </div>
        <el-upload
          class="upload-area"
          drag
          action="/api/upload"
          :on-success="(res) => handleUploadSuccess(res, 'postgame')"
          :on-error="handleUploadError"
          :limit="1"
          accept=".txt"
          :disabled="!!uploadedFiles.postgame"
        >
          <div class="upload-content" v-if="!uploadedFiles.postgame">
            <div class="upload-icon-bg small">
              <el-icon class="upload-icon" size="32"><Upload-filled /></el-icon>
            </div>
            <div class="upload-text">
              <p class="main-text">拖拽复盘文件到此处，或 <em>点击上传</em></p>
              <p class="sub-text">包含真实身份、夜间信息的复盘段</p>
            </div>
          </div>
          <div v-else class="uploaded-content">
            <el-icon class="success-icon" size="32"><Circle-Check /></el-icon>
            <span class="uploaded-name">{{ uploadedFiles.postgame.filename }}</span>
            <el-button type="danger" link size="small" @click.stop="removeFile('postgame')">
              移除
            </el-button>
          </div>
        </el-upload>
      </div>

      <!-- 使用已上传文件的选择 -->
      <div v-if="uploadedFiles.main" class="file-info">
        <el-alert
          :title="`已上传: ${uploadedFiles.main.filename} ${uploadedFiles.postgame ? '+ ' + uploadedFiles.postgame.filename : ''}`"
          type="success"
          :closable="false"
          show-icon
          effect="light"
        />
      </div>
    </el-card>

    <el-card ref="configCardRef" class="config-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <div class="icon-circle blue">
              <el-icon size="24"><Setting /></el-icon>
            </div>
            <span>分析配置</span>
          </div>
        </div>
      </template>

      <el-form :model="config" label-position="top">
        <el-form-item label="选择版型">
          <el-select
            v-model="config.formatPath"
            placeholder="请选择版型规则"
            style="width: 100%"
            size="large"
          >
            <el-option
              v-for="format in formats"
              :key="format.file_path"
              :label="format.name"
              :value="String(format.file_path)"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="对局名称">
          <el-input
            v-model="config.gameName"
            placeholder="输入对局名称（可选）"
            size="large"
          />
        </el-form-item>

        <el-form-item label="对局标签">
          <el-input
            v-model="config.label"
            placeholder="如：260312-第四局（可选，用于复用历史结果）"
            size="large"
          >
            <template #append>
              <el-tooltip content="填写标签后，如果之前分析过相同标签的对局，可直接使用历史结果">
                <el-icon><Info-Filled /></el-icon>
              </el-tooltip>
            </template>
          </el-input>
        </el-form-item>

        <!-- 起始阶段选择（当选中已有文件组时显示） -->
        <el-form-item v-if="selectedFileGroup" label="分析起始阶段">
          <el-select v-model="config.startStage" style="width: 100%" size="large">
            <el-option :label="startStageOptionText(1)" :value="1" />
            <el-option v-if="canStartFromStage(2)" :label="startStageOptionText(2)" :value="2" />
            <el-option v-if="canStartFromStage(3)" :label="startStageOptionText(3)" :value="3" />
          </el-select>
          <div v-if="config.startStage > 1 && selectedFileGroup" class="stage-hint">
            <el-text type="info" size="small">
              将保留阶段 1-{{ config.startStage - 1 }} 的结果，从阶段 {{ config.startStage }} 重新开始
            </el-text>
          </div>
        </el-form-item>

        <!-- 断点续传提示 -->
        <el-form-item v-if="canResume && config.startStage === 1">
          <el-alert
            :title="`该对局已完成 ${selectedFileGroup?.completed_stages.length} 个阶段的分析`"
            :description="resumeDescription"
            type="info"
            :closable="false"
            show-icon
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :disabled="!canStart"
            :loading="starting"
            @click="uploadedFiles.main ? startAnalysis() : startAnalysisWithSelected()"
            style="width: 100%"
            :icon="VideoPlay"
          >
            {{ uploadedFiles.main ? '开始分析' : analysisButtonText }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 已上传文件列表 -->
    <el-card class="files-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <div class="icon-circle orange">
              <el-icon size="24"><Folder /></el-icon>
            </div>
            <span>已上传文件</span>
          </div>
          <el-button
            type="primary"
            link
            size="small"
            :loading="loadingFiles"
            @click="loadUploadedFiles"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-if="uploadedFileList.length === 0" class="empty-files">
        <el-empty description="暂无已上传文件" :image-size="60" />
      </div>

      <div v-else class="files-list">
        <!-- 文件组列表 -->
        <div
          v-for="group in uploadedFileList"
          :key="group.group_id"
          class="file-group-item"
          :class="{ selected: selectedFileGroup?.group_id === group.group_id }"
          @click="selectFileGroup(group)"
        >
          <div class="group-header">
            <div class="group-main">
              <el-icon class="group-icon"><Folder /></el-icon>
              <!-- 标签或主文件名 -->
              <span class="group-name">{{ group.label || group.main_file?.filename || '未命名对局' }}</span>
              <!-- 分析状态标签 -->
              <el-tag
                v-if="group.analysis_status !== 'not_started'"
                :type="getStatusType(group.analysis_status)"
                size="small"
                class="status-tag"
              >
                {{ getStatusText(group.analysis_status) }}
              </el-tag>
              <el-tag v-if="group.postgame_file" type="success" size="small" effect="light">
                含复盘
              </el-tag>
            </div>
            <div class="group-actions">
              <el-button
                type="danger"
                link
                size="small"
                @click.stop="deleteFileGroup(group)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 文件详情 -->
          <div class="group-files">
            <div v-if="group.main_file" class="group-file main">
              <el-icon><Document /></el-icon>
              <span class="file-name">{{ group.main_file.filename }}</span>
              <span class="file-size">{{ formatFileSize(group.main_file.size) }}</span>
              <span class="file-type-tag">正文</span>
            </div>
            <div v-if="group.postgame_file" class="group-file postgame">
              <el-icon><Document /></el-icon>
              <span class="file-name">{{ group.postgame_file.filename }}</span>
              <span class="file-size">{{ formatFileSize(group.postgame_file.size) }}</span>
              <span class="file-type-tag postgame">复盘</span>
            </div>
          </div>

          <div class="group-meta">
            <span class="upload-time">{{ formatTime(group.uploaded_at) }}</span>
            <span v-if="group.completed_stages.length > 0" class="stage-info">
              已完成: {{ group.completed_stages.map(s => `阶段${s}`).join(', ') }}
            </span>
          </div>

          <!-- 选中状态的视觉指示 -->
          <div v-if="selectedFileGroup?.group_id === group.group_id" class="selected-indicator">
            <el-divider />
            <el-text type="primary" size="small">
              <el-icon><CircleCheck /></el-icon>
              已选择，请在上方配置分析选项
            </el-text>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, UploadFilled, Setting, VideoPlay, InfoFilled, Folder, Refresh, Delete, CircleCheck } from '@element-plus/icons-vue'
import type { FormatInfo, FileGroup, FileInfo } from '@/types'

const emit = defineEmits<{
  startAnalysis: [config: {
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
  }]
}>()

// 双文件上传状态
const uploadedFiles = ref<{
  main: { file_id: string; filename: string; file_path: string } | null
  postgame: { file_id: string; filename: string; file_path: string } | null
}>({ main: null, postgame: null })

// 从列表选择的文件组
const selectedFileGroup = ref<FileGroup | null>(null)

// 已上传文件组列表
const uploadedFileList = ref<FileGroup[]>([])
const selectedFile = ref<FileGroup | null>(null)  // 兼容旧代码
const formats = ref<FormatInfo[]>([])
const starting = ref(false)
const loadingFiles = ref(false)

const config = ref({
  formatPath: '',
  gameName: '',
  label: '',
  startStage: 1 // 默认从第一阶段开始
})

// 配置卡片ref，用于选择文件后滚动
const configCardRef = ref<HTMLElement | null>(null)

const canStart = computed(() => {
  // 检查是否有主文件（新上传的或从列表选择的）和版型
  const hasMainFile = uploadedFiles.value.main || selectedFileGroup.value?.main_file
  return hasMainFile && config.value.formatPath
})

// 是否可以断点续传
const canResume = computed(() => {
  return selectedFileGroup.value &&
    selectedFileGroup.value.completed_stages.length > 0 &&
    selectedFileGroup.value.completed_stages.length < 3
})

// 断点续传描述
const resumeDescription = computed(() => {
  if (!selectedFileGroup.value) return ''
  const completed = selectedFileGroup.value.completed_stages
  const nextStage = completed.length + 1
  return `已完成阶段: ${completed.join(', ')}，将从阶段${nextStage}继续分析`
})

// 分析按钮文字
const analysisButtonText = computed(() => {
  if (!selectedFileGroup.value) return '分析选中对局'

  const completed = selectedFileGroup.value.completed_stages
  const startStage = config.value.startStage

  // 如果用户明确选择了从某个阶段开始（且前序阶段已完成）
  if (startStage > 1 && canStartFromStage(startStage)) {
    return `从阶段 ${startStage} 开始分析`
  }

  const status = selectedFileGroup.value.analysis_status
  if (status === 'completed') return '重新分析'
  if (status === 'not_started') return '开始分析'
  return `继续分析 (阶段${completed.length + 1})`
})

// 判断是否可以从此阶段开始（需要前序阶段已完成）
function canStartFromStage(stage: number): boolean {
  if (!selectedFileGroup.value) return stage === 1
  const completed = selectedFileGroup.value.completed_stages
  // 要能从阶段N开始，需要阶段1到N-1都已完成
  for (let i = 1; i < stage; i++) {
    if (!completed.includes(i)) return false
  }
  return true
}

// 起始阶段选项文字
function startStageOptionText(stage: number): string {
  if (!selectedFileGroup.value) {
    if (stage === 1) return '从第一阶段开始（完整分析）'
    return `从第${stage}阶段开始（需先完成前序阶段）`
  }

  const completed = selectedFileGroup.value.completed_stages
  const hasCompleted = stage === 1 || completed.includes(stage - 1)

  if (stage === 1) return '从第一阶段开始（完整分析）'
  if (hasCompleted) return `从第${stage}阶段开始（已保存阶段1-${stage-1}结果）`
  return `从第${stage}阶段开始（需先完成阶段1-${stage-1}）`
}

onMounted(async () => {
  try {
    const response = await fetch('/api/formats')
    formats.value = await response.json()
  } catch (error) {
    ElMessage.error('加载版型列表失败')
  }
  await loadUploadedFiles()
})

async function loadUploadedFiles() {
  loadingFiles.value = true
  try {
    const response = await fetch('/api/uploads')
    if (response.ok) {
      uploadedFileList.value = await response.json()
    }
  } catch (error) {
    console.error('加载已上传文件失败:', error)
  } finally {
    loadingFiles.value = false
  }
}

// 选择文件组并滚动到配置区域
function selectAndAnalyze(group: FileGroup) {
  selectFileGroup(group)
  // 滚动到配置卡片
  configCardRef.value?.$el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function selectFileGroup(group: FileGroup) {
  selectedFileGroup.value = group
  selectedFile.value = group  // 兼容旧代码

  // 使用标签或主文件名作为游戏名
  const baseName = group.label || group.main_file?.filename.replace('.txt', '') || '未命名对局'
  config.value.gameName = baseName

  // 如果有标签，直接使用；否则从主文件名提取
  if (group.label) {
    config.value.label = group.label
  } else if (group.main_file) {
    const autoLabel = extractLabelFromFilename(group.main_file.filename)
    config.value.label = autoLabel !== baseName ? autoLabel : ''
  }
}

// 状态类型映射
function getStatusType(status: string): string {
  const typeMap: Record<string, string> = {
    'not_started': 'info',
    'stage1': 'warning',
    'stage2': 'warning',
    'stage3': 'warning',
    'completed': 'success'
  }
  return typeMap[status] || 'info'
}

// 状态文字映射
function getStatusText(status: string): string {
  const textMap: Record<string, string> = {
    'not_started': '未分析',
    'stage1': '阶段1完成',
    'stage2': '阶段2完成',
    'stage3': '阶段3完成',
    'completed': '已完成'
  }
  return textMap[status] || status
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(isoTime: string): string {
  const date = new Date(isoTime)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function deleteFileGroup(group: FileGroup) {
  try {
    const fileNames = [group.main_file?.filename, group.postgame_file?.filename]
      .filter(Boolean)
      .join(' 和 ')
    const confirmed = await ElMessageBox.confirm(
      `确定要删除对局 "${group.label || fileNames}" 吗？`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    ).catch(() => false)
    if (!confirmed) return

    // 删除组内的所有文件
    const filesToDelete = [group.main_file, group.postgame_file].filter(Boolean) as FileInfo[]
    let successCount = 0

    for (const file of filesToDelete) {
      const response = await fetch(`/api/uploads/${file.file_id}`, { method: 'DELETE' })
      if (response.ok) {
        successCount++
      }
    }

    if (successCount === filesToDelete.length) {
      ElMessage.success('删除成功')
      if (selectedFileGroup.value?.group_id === group.group_id) {
        selectedFileGroup.value = null
        selectedFile.value = null
      }
      await loadUploadedFiles()
    } else {
      ElMessage.error('部分文件删除失败')
    }
  } catch (error) {
    console.error('删除文件失败:', error)
  }
}

function startAnalysisWithSelected() {
  // 使用从列表选择的文件组
  if (!selectedFileGroup.value?.main_file || !config.value.formatPath) return

  const group = selectedFileGroup.value
  starting.value = true
  emit('startAnalysis', {
    mainFilePath: group.main_file.file_path,
    postgameFilePath: group.postgame_file?.file_path,
    formatPath: config.value.formatPath,
    gameName: config.value.gameName || group.main_file.filename,
    label: config.value.label.trim() || undefined,
    mainFileId: group.main_file.file_id,
    postgameFileId: group.postgame_file?.file_id,
    completedStages: group.completed_stages,
    hasExistingAnalysis: group.has_analysis,
    startStage: config.value.startStage
  })
}

// 从文件名自动提取标签
function extractLabelFromFilename(filename: string): string {
  // 移除 .txt 后缀
  const nameWithoutExt = filename.replace(/\.txt$/i, '')

  // 尝试匹配常见模式:
  // 1. 日期-局数 格式: 260312-第四局, 20260312-第四局（支持连字符或空格分隔）
  // 2. 包含 "第X局" 或 "局数" 的模式
  const patterns = [
    /(\d{6,8}[-\s]第[一二三四五六七八九十\d]+局)/,  // 260312-第四局 或 20260317 第三局
    /(\d{6,8}[-\s]第?\d+局?)/,                     // 260312-4局 或 20260317 3局
    /(第[一二三四五六七八九十\d]+局)/,              // 第四局
    /([^/\\]+)$/                                    // 默认：整个文件名（不含路径）
  ]

  for (const pattern of patterns) {
    const match = nameWithoutExt.match(pattern)
    if (match) {
      let label = match[1] || match[0]
      // 将空格统一替换为连字符，保持格式一致
      label = label.replace(/\s+/g, '-')
      return label
    }
  }

  return nameWithoutExt
}

function handleUploadSuccess(response: any, type: 'main' | 'postgame') {
  // 清除之前选择的文件组（从新上传开始）
  selectedFileGroup.value = null
  selectedFile.value = null

  uploadedFiles.value[type] = {
    file_id: response.file_id,
    filename: response.filename,
    file_path: response.file_path
  }

  // 如果是主文件，自动提取游戏名和标签
  if (type === 'main') {
    const baseName = response.filename.replace('.txt', '')
    config.value.gameName = baseName

    // 自动从文件名提取标签
    const autoLabel = extractLabelFromFilename(response.filename)
    if (autoLabel && autoLabel !== baseName) {
      config.value.label = autoLabel
      ElMessage.success(`主文件上传成功，已自动识别标签: "${autoLabel}"`)
    } else {
      ElMessage.success('主文件上传成功')
    }
  } else {
    ElMessage.success('复盘文件上传成功')
  }

  // 刷新文件列表
  loadUploadedFiles()
}

function removeFile(type: 'main' | 'postgame') {
  uploadedFiles.value[type] = null
}

function handleUploadError() {
  ElMessage.error('上传失败')
}

function startAnalysis() {
  // 优先使用新上传的文件对，否则使用从列表选择的文件组
  const mainFile = uploadedFiles.value.main || selectedFileGroup.value?.main_file
  const postgameFile = uploadedFiles.value.postgame || selectedFileGroup.value?.postgame_file

  if (!mainFile || !config.value.formatPath) return

  starting.value = true
  emit('startAnalysis', {
    mainFilePath: mainFile.file_path,
    postgameFilePath: postgameFile?.file_path,
    formatPath: config.value.formatPath,
    gameName: config.value.gameName || mainFile.filename,
    label: config.value.label.trim() || undefined,
    mainFileId: mainFile.file_id,
    postgameFileId: postgameFile?.file_id,
    completedStages: uploadedFiles.value.main ? [] : (selectedFileGroup.value?.completed_stages || []),
    hasExistingAnalysis: selectedFileGroup.value?.has_analysis || false,
    startStage: config.value.startStage
  })
}
</script>

<style scoped>
.upload-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.upload-card,
.config-card {
  background: white;
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.icon-circle {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.icon-circle.blue {
  background: linear-gradient(135deg, #409eff 0%, #79bbff 100%);
}

.upload-area {
  :deep(.el-upload-dragger) {
    background: #f5f7fa;
    border: 2px dashed #dcdfe6;
    border-radius: 12px;
    padding: 40px 20px;
    transition: all 0.3s;

    &:hover {
      border-color: #409eff;
      background: #ecf5ff;
    }
  }
}

/* 双文件上传样式 */
.upload-item {
  margin-bottom: 24px;
}

.upload-item:last-child {
  margin-bottom: 0;
}

.upload-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
}

.label-text {
  font-weight: 600;
  color: #303133;
}

.label-required {
  color: #f56c6c;
  font-size: 12px;
}

.label-optional {
  color: #909399;
  font-size: 12px;
}

.label-help {
  color: #909399;
  cursor: help;
  font-size: 14px;
}

.upload-icon-bg.small {
  width: 60px;
  height: 60px;
}

.uploaded-content {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px;
  background: #f0f9ff;
  border-radius: 8px;
  border: 1px solid #a0cfff;
}

.success-icon {
  color: #67c23a;
}

.uploaded-name {
  flex: 1;
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.upload-icon-bg {
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  color: #409eff;
}

.upload-text {
  text-align: center;
}

.main-text {
  font-size: 16px;
  color: #606266;
  margin: 0 0 8px 0;
}

.main-text em {
  color: #409eff;
  font-style: normal;
  font-weight: 600;
}

.sub-text {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.file-info {
  margin-top: 16px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
}

/* 文件列表样式 */
.files-card {
  grid-column: 1 / -1;
  background: white;
  border-radius: 12px;
}

.icon-circle.orange {
  background: linear-gradient(135deg, #e6a23c 0%, #f0c78a 100%);
}

.empty-files {
  padding: 20px 0;
}

.files-list {
  max-height: 400px;
  overflow-y: auto;
}

.file-item {
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  margin-bottom: 8px;

  &:hover {
    background: #f5f7fa;
  }

  &.selected {
    background: #ecf5ff;
    border-color: #409eff;
  }
}

.file-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.file-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #909399;
  font-size: 16px;
}

.file-name {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.file-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-meta {
  font-size: 12px;
  color: #909399;
  padding-left: 24px;
}

.file-meta .stage-info {
  color: #67c23a;
  margin-left: 12px;
}

.status-tag {
  margin-left: 8px;
}

/* 文件组样式 */
.file-group-item {
  padding: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  background: #f5f7fa;
  margin-bottom: 12px;

  &:hover {
    background: #e4e7ed;
  }

  &.selected {
    background: #ecf5ff;
    border-color: #409eff;
  }
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.group-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-icon {
  color: #409eff;
  font-size: 20px;
}

.group-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.group-files {
  margin: 12px 0;
  padding-left: 30px;
}

.group-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;

  &.main {
    border-left: 3px solid #409eff;
  }

  &.postgame {
    border-left: 3px solid #67c23a;
  }
}

.group-file .file-name {
  flex: 1;
  font-size: 13px;
  color: #606266;
}

.group-file .file-size {
  color: #909399;
  font-size: 12px;
}

.file-type-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: #ecf5ff;
  color: #409eff;

  &.postgame {
    background: #f0f9ff;
    color: #67c23a;
  }
}

.group-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-left: 30px;
  font-size: 12px;
  color: #909399;
}

.group-meta .stage-info {
  color: #67c23a;
}

.stage-hint {
  margin-top: 8px;
  padding: 4px 0;
}

.selected-indicator {
  margin-top: 12px;
  padding: 8px;
  background-color: var(--el-color-primary-light-9);
  border-radius: 4px;
  text-align: center;
}

@media (max-width: 768px) {
  .upload-section {
    grid-template-columns: 1fr;
  }

  .file-info-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .file-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
