# 狼人杀实时分析系统 - 前端

## 功能特性

- 📤 上传对局文本文件
- 🎨 选择狼人杀版型规则
- 🔄 实时三阶段分析（WebSocket）
- 🧠 深度思考内容实时展示
- 👥 Stage 3 玩家身份实时推断
- 📊 可视化结果展示（Stage 1/2/3 + 对比视图）
- 💾 分析结果持久化到 SQLite

## 技术栈

- Vue 3 + TypeScript
- Pinia (状态管理)
- Element Plus (UI组件)
- ECharts (图表)

## 安装与启动

```bash
# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

开发服务器将在 `http://localhost:5173` 启动。

## 构建生产版本

```bash
npm run build
```

构建产物将在 `dist/` 目录。

## 注意事项

- 确保后端服务在 `http://localhost:8000` 运行
- 首次使用需要在 `.env` 配置 DeepSeek API Key
