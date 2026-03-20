<template>
  <el-dialog
    v-model="visible"
    title="📚 历史分析记录"
    width="800px"
    destroy-on-close
  >
    <el-table :data="analyses" style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="game_name" label="对局名称" min-width="200" />
      <el-table-column prop="format_name" label="版型" width="120" />
      <el-table-column prop="created_at" label="分析时间" width="160">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="loadAnalysis(row.id)">
            加载
          </el-button>
          <el-button type="danger" size="small" @click="deleteAnalysis(row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="refreshList">刷新</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAnalysisStore } from '@/stores/analysis'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const store = useAnalysisStore()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const analyses = ref<any[]>([])
const loading = ref(false)

watch(visible, (val) => {
  if (val) refreshList()
})

async function refreshList() {
  loading.value = true
  try {
    const response = await fetch('/api/analyses')
    analyses.value = await response.json()
  } catch (error) {
    ElMessage.error('加载历史记录失败')
  } finally {
    loading.value = false
  }
}

async function loadAnalysis(id: string) {
  try {
    const response = await fetch(`/api/analyses/${id}`)
    const data = await response.json()

    // Load into store
    store.currentTask = {
      id: data.id,
      game_name: data.game_name,
      format_name: data.format_name,
      status: 'completed',
      stages: {
        1: { stage: 1, name: '事实抽取', status: 'completed', result: data.stage1_result },
        2: { stage: 2, name: '发言整理', status: 'completed', result: data.stage2_result },
        3: { stage: 3, name: '意图分析', status: 'completed', result: data.stage3_result }
      },
      reasoning_log: [],
      player_inferences: {}
    }

    visible.value = false
    ElMessage.success('加载成功')
  } catch (error) {
    ElMessage.error('加载失败')
  }
}

async function deleteAnalysis(id: string) {
  try {
    await ElMessageBox.confirm('确定删除这条记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await fetch(`/api/analyses/${id}`, { method: 'DELETE' })
    ElMessage.success('删除成功')
    refreshList()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>
