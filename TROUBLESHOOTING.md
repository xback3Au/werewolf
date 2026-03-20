# 故障排除指南

## 快速诊断

运行测试脚本：
```bash
# 在项目根目录
python test_system.py

# 在backend目录测试JSON解析
python test_json_parser.py
```

## 常见问题

### 1. 后端启动错误

#### ImportError: No module named 'xxx'
```bash
cd backend
pip install -r requirements.txt
```

#### DEEPSEEK_API_KEY not set
检查：
1. `backend/.env` 文件是否存在
2. 内容格式：`DEEPSEEK_API_KEY=sk-xxxxx`
3. 没有空格，没有引号

### 2. 前端启动错误

#### Cannot find module
```bash
cd frontend
npm install
```

#### TSConfckParseError
确保 `tsconfig.node.json` 存在

### 3. WebSocket连接失败

症状：
- 前端显示"未连接"
- 分析开始后立即断开

检查：
1. 后端是否运行：`http://localhost:8000/api/check`
2. 前端vite.config.ts代理配置
3. 浏览器控制台报错

### 4. JSON解析错误

症状：
```
Error in task xxx: Stage X JSON 解析失败
```

解决方案：
1. 查看 `outputs/error_stageX_xxx.txt` 文件
2. 检查模型输出是否完整
3. 增加 max_tokens 参数
4. 在 prompt 中强调"输出合法JSON"

### 5. 文件上传成功但分析失败

症状：
- 上传成功
- 开始分析后报错
- 错误：文件不存在

原因：前端传的是 file_id 而不是 file_path
解决：确保前端传递 `file_path` 字段（包含 `uploads/` 前缀）

### 6. 推理内容显示不完整

症状：
- 深度思考窗口只显示"好人"

原因：
1. 模型输出被截断
2. 或者输出的是摘要而非完整推理

解决：
- 检查模型输出的 `reasoning_content` 字段
- 后端增加日志查看原始输出

## 调试技巧

### 查看后端日志

在 `backend/analyzer.py` 中添加：
```python
print(f"[DEBUG] Raw content: {result['content'][:200]}")
print(f"[DEBUG] Reasoning: {result.get('reasoning_content', '')[:200]}")
```

### 查看前端状态

浏览器控制台：
```javascript
// 查看当前任务状态
JSON.parse(localStorage.getItem('analysis-store'))
```

### 测试单个阶段

使用命令行版本：
```bash
cd backend
python -c "
from analyzer import StreamingAnalyzer
# 测试单个阶段
"
```

## 性能优化

### API调用慢

- 检查网络连接
- 考虑使用更快的模型（如 deepseek-chat）
- 减少 max_tokens 如果不需要长输出

### 内存占用高

- 清理 reasoning_log（限制在500条）
- 定期重启后端服务
- 清理 outputs 目录旧文件

## 获取帮助

如果问题无法解决：

1. 收集信息：
   - 后端完整错误日志
   - 前端浏览器控制台日志
   - 测试脚本输出 (`python test_system.py`)

2. 检查：
   - Python版本 >= 3.8
   - Node.js版本 >= 16
   - 所有依赖已安装

3. 尝试：
   - 清除数据库：`rm backend/analysis.db`
   - 清除上传文件：`rm uploads/*`
   - 重新启动服务
