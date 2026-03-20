# 狼人杀自主学习 Agent

一个能**自己看对局、自己复盘、自己总结战术、越用越强**的狼人杀 AI 教练。

> 当前版本：三阶段分析流水线已完成，正在向自主学习 Agent 演进。

---

## 项目愿景

普通的 AI 工具只能查固定知识点，回答预设问题。

这个项目的目标是做一个**真正会学习的狼人杀教练**：

- 丢进去一局对局文本，它自己分析每个人的发言逻辑、推断身份、找出矛盾
- 你告诉它"你这里判断错了，5号其实是狼"，它修正认知，生成经验规则
- 下一局，它自动调用历史经验，不再犯同样的错误
- 多局积累后，形成完整的战术知识库：狼人怎么倒钩、好人怎么表水、神职怎么藏身份

核心能力链：**自主推理 → 接受纠正 → 更新记忆 → 越学越强**

---

## 开发路线图

### 已完成

- [x] 三阶段分析流水线（事实提取 / 发言整理 / 意图推断）
- [x] DeepSeek 实时流式推理 + 思考过程可视化
- [x] 动态身份推断（好人/狼人/神职概率）
- [x] WebSocket 实时通信
- [x] 历史记录管理

### Phase 1 — 数据结构化（RAG 底座）

> 把现有 JSON 输出转成关系型表，为 Agent 的工具和记忆打基础

- [ ] 建立结构化表：speeches / votes / timeline_events / inference_chains / knowledge_chunks
- [ ] Stage2/3 双写（JSON 给前端展示 + 结构化数据入库供查询）
- [ ] 实现 GameState 类（追踪局内状态：存活、身份、票型、立场关系图）

### Phase 2 — 工具层（Tool Calling）

> 先写工具、逐个测试，全部通过后再串进 Agent

- [ ] `game_parser_tool`：对局文本 → 结构化 JSON
- [ ] `logic_checker_tool`：检测玩家发言前后矛盾
- [ ] `identity_inference_tool`：推断身份概率（核心工具）
- [ ] `tactic_summarizer_tool`：归纳本局战术要点
- [ ] `feedback_parser_tool`：解析用户的自然语言纠正（"5号是狼，他在倒钩"）
- [ ] `memory_update_tool`：将纠正转化为经验规则存入知识库

### Phase 3 — Agent 主体（ReAct 规划）

- [ ] Agent 自主规划循环：接收对局 → 调工具 → 多轮推理 → 输出学习报告
- [ ] 用户纠正分支：接收纠正 → 修正本局认知 → 生成跨局经验
- [ ] 短期记忆（单局上下文）+ 长期记忆（跨局经验库）

### Phase 4 — 越学越强

- [ ] 向量语义检索（RAG），新局分析前自动调用历史经验
- [ ] 跨局统计（打法胜率、高频模式、个人风格画像）
- [ ] 前端对话复盘界面

---

## 当前功能

基于三阶段流水线，上传一局对局文本后自动完成：

- **Stage 1 — 事实提取**：玩家状态、夜间事件、投票记录
- **Stage 2 — 发言整理**：发言时间线、立场关系、完整文本
- **Stage 3 — 意图推断**：AI 盲推每个玩家身份概率，实时展示思考过程

---

## 项目结构

```
werewolf/
├── backend/
│   ├── main.py          # WebSocket 服务入口
│   ├── analyzer.py      # AI 分析引擎（三阶段 pipeline）
│   ├── database.py      # 数据库操作
│   ├── models.py        # 数据模型
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/  # 各阶段结果展示组件
│       ├── stores/      # 状态管理（WebSocket 连接）
│       └── App.vue
├── prompts/             # AI 提示词模板
├── formats/             # 版型规则定义
└── start.bat            # Windows 一键启动
```

---

## 技术栈

- **后端**：Python、FastAPI、WebSocket、SQLite
- **前端**：Vue 3、TypeScript、Element Plus、ECharts
- **AI**：DeepSeek API（deepseek-reasoner，流式推理）
- **Agent 层（规划中）**：ReAct 循环、Tool Calling、向量检索（Chroma）

---

## 使用方法

### 1. 准备对局文本

从玩家对局视频中提取字幕文本（可附带复盘内容）。

### 2. 上传分析

1. 打开 http://localhost:5173
2. 拖入或选择对局文本文件
3. 选择版型规则（如机械狼通灵师）
4. 点击 **开始分析**，观看实时推理过程
5. 查看三阶段分析结果

---

## API 文档

启动后端后访问 http://localhost:8000/docs 查看自动生成的接口文档。

---

## 部署教程

### 环境要求

- Python 3.11+
- Node.js 18+（LTS）
- DeepSeek API Key（访问 https://platform.deepseek.com 注册获取）

### 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/xback3AU/werewolf.git
cd werewolf

# 2. 后端
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt

# 复制并填写 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx

uvicorn main:app --reload --port 8000

# 3. 前端（新开一个终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

### 详细安装步骤

<details>
<summary>第一步：安装 Python</summary>

1. 访问 https://www.python.org/downloads/ 下载 Python 3.11.x
2. 安装时**务必勾选 "Add Python to PATH"**
3. 验证：`python --version`

</details>

<details>
<summary>第二步：安装 Node.js</summary>

1. 访问 https://nodejs.org/ 下载 LTS 版本
2. 默认安装即可
3. 验证：`node --version` 和 `npm --version`

</details>

<details>
<summary>第三步：获取 DeepSeek API Key</summary>

1. 访问 https://platform.deepseek.com 注册/登录
2. 左侧菜单选择 **API Keys** → **创建 API Key**
3. 复制以 `sk-` 开头的 Key（**关闭弹窗后无法再次查看**）

</details>

<details>
<summary>第四步：配置虚拟环境（可选 Conda）</summary>

**Conda 方式：**
```bash
conda create -n werewolf python=3.11
conda activate werewolf
```

</details>

---

## 常见问题

**`'python' 不是内部或外部命令`**
安装 Python 时未勾选 "Add Python to PATH"，重新安装并勾选。

**`pip install` 速度很慢**
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**`npm install` 速度很慢**
```bash
npm config set registry https://registry.npmmirror.com
npm install
```

**虚拟环境激活失败（PowerShell）**
```powershell
Set-ExecutionPolicy RemoteSigned  # 管理员身份运行
```

**`No module named 'xxx'`**
检查虚拟环境是否激活（命令行前有 `(venv)` 或 `(werewolf)`），再执行 `pip install -r requirements.txt`。

**前端提示"无法连接到后端"**
检查后端是否正在运行，确认 8000 端口未被占用。

**API Key 错误**
检查 `backend/.env` 文件存在且 Key 完整（以 `sk-` 开头，无多余空格），修改后需重启后端。

**WebSocket 连接失败**
关闭防火墙或将 Python 加入白名单；尝试用 `localhost` 替代 `127.0.0.1`。

---

