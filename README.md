# 狼人杀发言意图分析 Agent（V2.0）

这是一个基于 AI 的狼人杀对局分析工具，可以自动分析游戏文本，提取关键信息、整理发言、推断玩家身份和意图。

## 功能介绍

### 核心功能
- 📤 **拖拽上传**对局文本文件
- 🎨 **版型规则**选择（如机械狼通灵师）
- 🔄 **三阶段实时分析**：
  - Stage 1: 事实抽取（玩家状态、夜间事件）
  - Stage 2: 发言整理（时间线、立场关系）
  - Stage 3: 意图分析（AI 实时推理玩家身份）
- 🧠 **实时思考展示**：观看 AI 的思考过程
- 👥 **动态身份推断**：实时显示每个玩家的好人/狼人概率
- 📊 **可视化结果**：表格、时间线、概率条等多种展示
- 💾 **历史记录**：自动保存分析结果到本地数据库

### 系统架构
- **后端**：Python + FastAPI（提供 API 和 WebSocket 实时通信）
- **前端**：Vue 3 + TypeScript（可视化界面）
- **AI 引擎**：DeepSeek API（流式推理分析）

---

## 零基础部署教程

> 本教程面向完全没有开发经验的用户，请按照步骤一步步操作。

### 第一步：安装必要软件

#### 1.1 安装 Python（后端运行需要）

1. 打开浏览器，访问 https://www.python.org/downloads/
2. 点击页面上方的黄色按钮 **Download Python 3.11.x**
3. 下载完成后双击运行安装程序
4. **重要**：在安装界面底部，勾选 **"Add Python to PATH"**（添加到环境变量）
5. 点击 **Install Now** 开始安装
6. 安装完成后，按 `Win + R` 键，输入 `cmd` 回车打开命令行
7. 输入以下命令验证安装：
   ```bash
   python --version
   ```
   如果显示类似 `Python 3.11.x` 的版本号，说明安装成功

#### 1.2 安装 Node.js（前端运行需要）

1. 打开浏览器，访问 https://nodejs.org/
2. 点击左侧绿色按钮 **LTS**（推荐版本）下载
3. 下载完成后双击运行安装程序
4. 一直点击 **Next** 直到安装完成（使用默认设置即可）
5. 安装完成后，在命令行中输入以下命令验证：
   ```bash
   node --version
   npm --version
   ```
   如果显示版本号（如 `v20.x.x` 和 `10.x.x`），说明安装成功

---

### 第二步：获取 DeepSeek API Key

本项目需要调用 DeepSeek AI 接口进行分析，你需要一个 API Key。

1. 打开浏览器，访问 https://platform.deepseek.com/
2. 点击右上角 **注册** 或 **登录**（可以用手机号注册）
3. 登录后，点击左侧菜单的 **API Keys**
4. 点击 **创建 API Key** 按钮
5. 输入一个名称（如 `werewolf`），点击 **创建**
6. **重要**：创建成功后立即复制显示的 API Key（以 `sk-` 开头），**关闭后将无法再次查看**
7. 将复制的内容保存到一个文本文件中，稍后需要用到


---

### 第三步：下载项目代码

#### 方式一：使用 Git 下载（推荐，如果你已安装 Git）

1. 在项目文件夹空白处右键，选择 **Git Bash Here**
2. 输入以下命令：
   ```bash
   git clone https://github.com/xback3AU/werewolf.git
   cd werewolf
   ```

#### 方式二：直接下载压缩包

1. 在浏览器中打开项目页面（如 GitHub）
2. 点击绿色的 **Code** 按钮，选择 **Download ZIP**
3. 下载完成后解压到任意文件夹
4. 解压后的文件夹就是项目根目录

---

### 第四步：配置后端服务

#### 4.1 进入后端目录

1. 打开命令行（按 `Win + R`，输入 `cmd` 回车）
2. 使用 `cd` 命令进入项目目录（根据你的实际路径调整）：
   ```bash
   cd /d D:\你的文件夹路径\werewolf\backend
   ```
   例如：
   ```bash
   cd /d D:\Projects\werewolf\backend
   ```

#### 4.2 创建虚拟环境（推荐）

**什么是虚拟环境？**
虚拟环境就像是一个"隔离的房间"，把项目需要的依赖包都装在这个房间里，不会影响电脑上的其他 Python 项目。


**方案 A：使用 Python 内置 venv**

在 backend 目录下，依次执行以下命令：

```bash
# 创建虚拟环境（venv 是环境名称，可以自定义）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

激活成功后，命令行前面会出现 `(venv)` 字样，像这样：

```
(venv) D:\werewolf\backend>
```

**如何退出虚拟环境？**

输入 `deactivate` 即可退出。

**方案 B：使用 Conda（如果你已安装 Anaconda/Miniconda）**

如果你已经安装了 Conda（Anaconda 或 Miniconda），可以使用 Conda 创建环境：

```bash
# 创建虚拟环境（python 版本可根据需要调整）
conda create -n werewolf python=3.11

# 激活虚拟环境
conda activate werewolf
```

激活成功后，命令行前面会出现 `(werewolf)` 字样。

**如何退出虚拟环境？**

输入 `conda deactivate` 即可退出。


#### 4.3 安装 Python 依赖

**确保虚拟环境已激活**（看到命令行前面有 `(venv)`），然后执行：

```bash
pip install -r requirements.txt
```

等待安装完成，看到 `Successfully installed ...` 表示成功。

> 如果安装速度很慢，可以使用国内镜像源：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

#### 4.3 配置环境变量

1. 在 backend 文件夹中，找到 `.env.example` 文件
2. 选中该文件，复制粘贴
3. 将粘贴出来的副本重命名为 `.env`（删除 `.example` 后缀）
4. 将文件中 `DEEPSEEK_API_KEY=` 后面的内容替换为你刚才复制的 API Key：
   ```
   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```


---

### 第五步：配置前端服务

#### 5.1 进入前端目录

打开一个新的命令行窗口（不要关闭之前的），执行：

```bash
cd /d D:\你的文件夹路径\werewolf\frontend
```

#### 5.2 安装前端依赖

在 frontend 目录下，执行以下命令：

```bash
npm install
```

等待安装完成，这可能需要几分钟时间。看到 `added xxx packages` 表示成功。

> 如果安装速度很慢，可以使用国内镜像源：
> ```bash
> npm config set registry https://registry.npmmirror.com
> npm install
> ```

---

### 第六步：启动服务

**需要同时运行后端和前端两个服务**。

#### 6.1 启动后端服务

1. 在 backend 目录的命令行中，**确保虚拟环境已激活**
2. 根据你使用的环境类型，选择对应的激活命令：

   **如果使用的是 venv：**
   ```bash
   venv\Scripts\activate
   ```

   **如果使用的是 Conda：**
   ```bash
   conda activate werewolf
   ```

3. 确认环境已激活（看到命令行前面有 `(venv)` 或 `(werewolf)`），然后启动服务：
   ```bash
   uvicorn main:app --reload --port 8000
   ```

如果看到类似以下的输出，表示后端启动成功：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**保持这个窗口运行，不要关闭！**

#### 6.2 启动前端服务

打开一个新的命令行窗口，在 frontend 目录中执行：

```bash
npm run dev
```

如果看到类似以下的输出，表示前端启动成功：

```
VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  press h + enter to show help
```

**保持这个窗口运行，不要关闭！**

---

### 第七步：访问系统

1. 打开浏览器（推荐使用 Chrome 或 Edge）
2. 在地址栏输入：http://localhost:5173 访问，即可看到狼人杀分析系统的界面！

---



## 使用方法

### 1. 准备对局文本

直接使用玩家对局的视频字幕提取（和对应的复盘内容）

### 2. 上传分析

1. 在网页中点击 **选择文件** 或直接将文件拖入上传区域
2. 选择对应的 **版型规则**
3. 点击 **开始分析** 按钮
4. 等待分析完成，观看实时推理过程
5. 查看三个阶段的分析结果

---

## 常见问题

### Q1: 提示 "'python' 不是内部或外部命令"
**原因**：Python 没有正确添加到环境变量。
**解决**：安装 Python，**务必勾选 "Add Python to PATH"**。若已安装检查是否添加环境变量

### Q2: pip install 时报错或速度很慢
**解决**：使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3: npm install 报错或卡住
**解决**：
1. 使用国内镜像源：
   ```bash
   npm config set registry https://registry.npmmirror.com
   npm install
   ```
2. 或者删除 `node_modules` 文件夹后重试：
   ```bash
   rmdir /s /q node_modules
   npm install
   ```


### Q4: 虚拟环境创建或激活失败

**venv 方案：**
**原因**：可能是 PowerShell 执行策略限制。
**解决**：
1. 以管理员身份运行 PowerShell，执行：
   ```powershell
   Set-ExecutionPolicy RemoteSigned
   ```
   输入 `Y` 确认
2. 或者使用 CMD 而不是 PowerShell

**Conda 方案：**
**原因**：Conda 没有正确初始化。
**解决**：
1. 确保 Conda 已正确安装
2. 如果提示找不到 `conda` 命令，尝试先执行：
   ```bash
   conda init
   ```
3. 关闭命令行窗口重新打开

### Q5: 启动后端时提示 "No module named 'xxx'"
**原因**：依赖没有安装完整，或者虚拟环境未激活。
**解决**：
1. 检查是否激活了虚拟环境（看命令行前面是否有 `(venv)` 或 `(werewolf)`）
2. 根据环境类型选择激活命令：
   - venv 环境：`venv\Scripts\activate`
   - Conda 环境：`conda activate werewolf`
3. 重新执行 `pip install -r requirements.txt`

### Q6: 前端页面显示 "无法连接到后端"
**原因**：后端服务没有启动，或者端口被占用。
**解决**：
1. 检查后端命令行窗口是否还在运行
2. 检查是否有其他程序占用了 8000 端口
3. 尝试重启后端服务

### Q7: 分析时提示 API Key 错误
**原因**：`.env` 文件配置不正确。
**解决**：
1. 检查 `.env` 文件是否存在于 backend 目录
2. 检查 API Key 是否复制完整（以 `sk-` 开头）
3. 检查是否有多余的空格
4. 重启后端服务使配置生效

### Q8: WebSocket 连接失败
**原因**：防火墙阻止了 WebSocket 连接。
**解决**：
1. 关闭防火墙或将 Python 添加到防火墙白名单
2. 尝试使用 `localhost` 而不是 `127.0.0.1` 访问

---

## 项目结构

```
werewolf/
├── backend/                    # 后端服务
│   ├── main.py                # 主程序（API 和 WebSocket）
│   ├── analyzer.py            # AI 分析引擎
│   ├── database.py            # 数据库操作
│   ├── models.py              # 数据模型
│   ├── requirements.txt       # Python 依赖列表
│   └── .env                   # 配置文件（需自己创建）
├── frontend/                   # 前端界面
│   ├── src/
│   │   ├── components/        # 页面组件
│   │   ├── stores/            # 状态管理
│   │   └── App.vue            # 主页面
│   └── package.json           # Node.js 依赖列表
├── prompts/                    # AI 提示词模板
├── data/                       # 示例对局文件
├── formats/                    # 版型规则定义
└── start.bat                   # Windows 一键启动脚本
```

---

## API 文档

启动后端后，可以访问 http://localhost:8000/docs 查看自动生成的 API 文档。

---

## 技术栈

- **后端**：Python、FastAPI、WebSocket、SQLite
- **前端**：Vue 3、TypeScript、Element Plus、ECharts
- **AI**：DeepSeek API

---

## 开发计划

### 已完成
- [x] 基础三阶段分析（事实提取 / 发言整理 / 意图推断）
- [x] 实时 WebSocket 通信 + 流式推理展示
- [x] 动态身份推断（好人/狼人概率）
- [x] 历史记录管理

### 下一阶段：自主学习 Agent

本项目下一步将从"被动分析工具"进化为**会主动学习的狼人杀 AI 教练**。

**Phase 1 — 数据结构化（RAG 底座）**
- [ ] 建立关系型表：speeches / votes / timeline_events / inference_chains / knowledge_chunks
- [ ] Stage2/3 双写（JSON 给前端 + 结构化数据入库）
- [ ] 实现 GameState 类（追踪局内状态：存活、身份、票型、立场）

**Phase 2 — 工具层（Tool Calling）**
- [ ] game_parser_tool：对局文本 → 结构化 JSON
- [ ] logic_checker_tool：检测玩家发言前后矛盾
- [ ] identity_inference_tool：推断身份概率（核心）
- [ ] tactic_summarizer_tool：归纳本局战术要点
- [ ] feedback_parser_tool：解析用户的自然语言纠正
- [ ] memory_update_tool：将纠正转化为经验存入知识库

**Phase 3 — Agent 主体（ReAct 规划）**
- [ ] Agent 自主规划循环：接收对局 → 调工具 → 推理 → 输出报告
- [ ] 用户纠正分支：告知 Agent 判断错误 → Agent 修正认知 → 生成经验
- [ ] 短期记忆（单局上下文）+ 长期记忆（跨局经验库）

**Phase 4 — 越学越强**
- [ ] 向量语义检索（RAG），新局自动调用历史经验
- [ ] 跨局统计分析（打法胜率、高频模式）
- [ ] 前端对话复盘界面

### 其他可视化功能
- [ ] 投票热力图
- [ ] 玩家关系图

---

## License

MIT

---

