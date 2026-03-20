# 狼人杀分析系统 - 项目指南

## 📋 项目概述

这是一个三阶段狼人杀对局分析系统，通过 AI 自动分析游戏转录文本，提取结构化数据并推断玩家意图。

### 核心流程
```
转录文本 → Stage1(事实提取) → Stage2(发言整理) → Stage3(意图推断) → 可视化展示
```

---

## 🗂️ 文件结构总览

### 后端 (`backend/`)

#### ⭐ 核心文件（必须了解）

| 文件 | 作用 | 复杂度 | 说明 |
|------|------|--------|------|
| `main.py` | WebSocket 服务器入口 | ⭐⭐⭐ | 连接管理、消息路由、断点续传逻辑 |
| `analyzer.py` | AI 分析核心 | ⭐⭐⭐⭐ | 三阶段 pipeline、数据清洗、流式输出解析 |
| `database.py` | 数据库操作 | ⭐⭐ | SQLite 增删改查、分析记录管理 |
| `models.py` | 数据模型定义 | ⭐ | Pydantic 模型，定义请求/响应结构 |

#### 🧪 测试文件（可忽略）

| 文件 | 说明 |
|------|------|
| `test_integration.py` | 集成测试 |
| `test_json_parser.py` | JSON 解析测试 |

---

### 前端 (`frontend/src/`)

#### ⭐ 核心文件（必须了解）

| 文件 | 作用 | 复杂度 | 说明 |
|------|------|--------|------|
| `App.vue` | 主应用框架 | ⭐⭐ | 页面切换逻辑（上传/分析/结果） |
| `stores/analysis.ts` | 全局状态管理 | ⭐⭐⭐ | WebSocket 连接、任务状态、数据流 |
| `components/AnalysisProgress.vue` | 分析进度页 | ⭐⭐⭐ | 实时显示 AI 思考过程 |
| `components/ResultsView.vue` | 结果展示页 | ⭐⭐ | 三阶段结果汇总展示 |

#### 🔍 阶段视图组件（了解 Stage1/2/3 的输出格式）

| 文件 | 作用 | 说明 |
|------|------|------|
| `Stage1View.vue` | Stage1 输入表单 | 保留用于未来手动编辑 |
| `Stage1ResultView.vue` | Stage1 结果展示 | 显示夜晚事件、投票表等 |
| `Stage2View.vue` | Stage2 输入表单 | 保留用于未来手动编辑 |
| `Stage2ResultView.vue` | Stage2 结果展示 | 显示发言整理结果 |
| `Stage3View.vue` | Stage3 输入表单 | 保留用于未来手动编辑 |
| `Stage3ResultView.vue` | Stage3 结果展示 | 显示意图推断结果 |

#### 🎨 其他组件

| 文件 | 作用 | 说明 |
|------|------|------|
| `UploadSection.vue` | 文件上传页 | 选择版型、上传转录 |
| `PlayerComparisonView.vue` | 玩家对比 | 对比推断与真实身份 |
| `HistoryDialog.vue` | 历史记录弹窗 | 查看过往分析 |

#### 📝 配置文件

| 文件 | 作用 |
|------|------|
| `types/index.ts` | TypeScript 类型定义 |
| `main.ts` | 应用入口 |

---

### Prompt 模板 (`prompts/`)

| 文件 | 作用 | 重要程度 |
|------|------|----------|
| `v1_stage1_facts_prompt.txt` | Stage1 提示词 | ⭐⭐⭐⭐⭐ |
| `v1_stage2_speeches_prompt.txt` | Stage2 提示词 | ⭐⭐⭐⭐ |
| `v1_stage3_intent_prompt.txt` | Stage3 提示词 | ⭐⭐⭐⭐⭐ |
| `v1_organize_and_intent_prompt.txt` | 旧版整合提示词 | ⭐（已废弃）|

---

## 🔗 文件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户交互层                            │
├─────────────────────────────────────────────────────────────┤
│  App.vue                                                    │
│   ├── UploadSection.vue     ← 上传对局文件                  │
│   ├── AnalysisProgress.vue  ← 显示实时分析进度              │
│   └── ResultsView.vue       ← 展示最终结果                  │
│         ├── Stage1ResultView.vue                            │
│         ├── Stage2ResultView.vue                            │
│         └── Stage3ResultView.vue                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket 连接
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        状态管理层                            │
├─────────────────────────────────────────────────────────────┤
│  stores/analysis.ts                                         │
│   ├── 管理 WebSocket 连接                                    │
│   ├── 存储推理日志 (reasoningLog)                            │
│   ├── 存储任务状态 (currentTask)                             │
│   └── 提供计算属性 (isAnalyzing, hasResult)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        后端服务层                            │
├─────────────────────────────────────────────────────────────┤
│  main.py                                                    │
│   ├── WebSocket 路由 (/ws/analyze/{task_id})                │
│   ├── 断点续传逻辑 (检查已有记录)                            │
│   ├── 回调函数 (ws_callback) ← 实时发送消息给前端            │
│   └── 保存最终结果到数据库                                   │
│                                                             │
│  analyzer.py                                                │
│   ├── StreamingAnalyzer 类                                  │
│   │   ├── run_full_pipeline()    ← 运行三阶段               │
│   │   ├── run_stage1()                                      │
│   │   ├── run_stage2()                                      │
│   │   ├── run_stage3()           ← 数据清洗 + 意图推断       │
│   │   ├── _sanitize_for_blind_inference()                   │
│   │   └── _send()                ← 发送 WebSocket 消息       │
│   │                                                         │
│   └── extract_player_inferences_realtime()                  │
│       ← 从流式输出实时解析玩家推断                           │
│                                                             │
│  database.py                                                │
│   ├── save_analysis()        ← 保存分析结果                  │
│   ├── get_analysis()                                        │
│   ├── get_analysis_by_file_id()                             │
│   └── delete_analysis()      ← 用于"重新分析"                │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ SQL
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        数据层                                │
├─────────────────────────────────────────────────────────────┤
│  analysis.db (SQLite)                                       │
│   ├── analyses 表: 存储分析记录                              │
│   │   ├── id, game_name, format_name                        │
│   │   ├── stage1_result (JSON)                              │
│   │   ├── stage2_result (JSON)                              │
│   │   ├── stage3_result (JSON)                              │
│   │   └── pipeline_result (完整结果)                         │
│   └── uploads 表: 存储上传记录                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        AI 交互层                             │
├─────────────────────────────────────────────────────────────┤
│  prompts/                                                   │
│   ├── v1_stage1_facts_prompt.txt                            │
│   │   ← 输入: 版型规则 + 转录文本                            │
│   │   ← 输出: 结构化事实 (玩家、夜晚事件、投票)               │
│   │                                                         │
│   ├── v1_stage2_speeches_prompt.txt                         │
│   │   ← 输入: 版型规则 + 转录文本                            │
│   │   ← 输出: 发言整理 (摘要、完整文本、立场)                │
│   │                                                         │
│   └── v1_stage3_intent_prompt.txt                           │
│       ← 输入: Stage1结果(清洗后) + Stage2结果(清洗后)        │
│       ← 输出: 盲推推断 + 验证对比 + 意图时间线               │
│       ← 关键: 隐藏 fact_role, night_events详情, 胜负结果     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ API 调用 (DeepSeek)
                              ▼
                        DeepSeek LLM
```

---

## 🎯 关键数据流

### 1. 分析流程（正常路径）

```
用户上传文件
    ↓
App.vue 调用 store.startAnalysis()
    ↓
analysis.ts 建立 WebSocket 连接
    ↓
main.py 接收连接，创建 StreamingAnalyzer
    ↓
analyzer.run_full_pipeline()
    ├── run_stage1() → 调用 DeepSeek → 解析 JSON → 发送 stage_complete
    ├── run_stage2() → 调用 DeepSeek → 解析 JSON → 发送 stage_complete
    └── run_stage3() → 数据清洗 → 调用 DeepSeek → 实时解析推断 → 发送 stage_complete
    ↓
发送 analysis_complete → 前端显示"查看结果"按钮
    ↓
保存到数据库
```

### 2. 断点续传流程

```
用户点击"重新分析"
    ↓
前端发送 DELETE /api/analyses/by-file/{file_id}
    ↓
删除数据库记录
    ↓
重新开始完整分析流程
```

### 3. 实时消息类型

```
stage_start    → 阶段开始，显示"进行中"
reasoning      → AI 思考内容，追加到推理日志
content        → AI 正式输出（JSON），尝试解析玩家推断
stage_complete → 阶段完成，更新进度条
analysis_complete → 全部完成，启用"查看结果"按钮
saved          → 结果已保存到数据库
error          → 出错，显示错误信息
```

---

## 🚫 可以忽略的文件

### 1. 依赖文件
- `frontend/node_modules/` - npm 依赖，不要修改
- `backend/__pycache__/` - Python 缓存
- `package.json`, `package-lock.json` - 依赖配置，一般不需要看

### 2. 测试文件（除非你在调试）
- `backend/test_*.py` - 单元测试

### 3. 旧版本文件
- `prompts/v1_organize_and_intent_prompt.txt` - 已废弃的整合提示词

### 4. 配置/工具文件
- `vite.config.ts` - Vite 配置，一般不改
- `tsconfig.json` - TypeScript 配置，一般不改
- `.gitignore` - Git 忽略规则

---

## 📚 推荐阅读顺序

### 如果你想了解整体架构
1. `prompts/v1_stage1_facts_prompt.txt` - 了解 Stage1 输出什么
2. `prompts/v1_stage2_speeches_prompt.txt` - 了解 Stage2 输出什么
3. `prompts/v1_stage3_intent_prompt.txt` - 了解 Stage3 如何推断
4. `backend/analyzer.py` - 了解 pipeline 如何串联
5. `frontend/src/stores/analysis.ts` - 了解数据如何流转到前端

### 如果你想优化某个 Stage
1. 先看对应的 `prompts/v1_stageX_*.txt`
2. 再看 `backend/analyzer.py` 中的 `run_stageX()`
3. 最后看 `frontend/src/components/StageXResultView.vue` 了解如何展示

### 如果你想改进 UI
1. `frontend/src/App.vue` - 看整体布局
2. `frontend/src/components/AnalysisProgress.vue` - 分析进度页
3. `frontend/src/components/ResultsView.vue` - 结果展示页

---

## 💡 关键设计决策

### 1. 数据清洗（盲推）
- **位置**: `analyzer.py` → `_sanitize_for_blind_inference()`
- **目的**: 让 Stage3 在不知道真实身份的情况下推断
- **隐藏**: fact_role, night_events 详情, global_result, commentator_content

### 2. 流式解析
- **位置**: `analyzer.py` → `extract_player_inferences_realtime()`
- **目的**: 从 AI 流式输出中实时提取玩家推断
- **注意**: 当前实现是在 Stage3 完成后解析，不是真正实时

### 3. 断点续传
- **位置**: `main.py` → WebSocket 处理逻辑
- **逻辑**: 检查已有记录 → 从下一阶段开始 → 复用已完成结果

---

## 🔧 常用调试方法

### 查看 AI 原始输出
在 `backend/analyzer.py` 中搜索 `print`，可以看到：
- `[Stage X] Sending request` - 发送给 AI 的提示词
- `[Stage X] Received response` - AI 的原始返回
- `[Stage X] Response content` - 解析后的 JSON

### 查看 WebSocket 消息
在前端浏览器控制台可以看到：
- `[WS] Received message type: xxx` - 收到的消息类型
- 点击可以展开查看完整消息内容

### 查看数据库
```bash
cd backend
sqlite3 analysis.db
.tables
SELECT id, game_name, stage1_result IS NOT NULL as has_s1 FROM analyses;
```

---

*文档版本: 2026-03-18*
*作者: xback3Au*
