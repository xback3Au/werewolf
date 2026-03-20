#!/usr/bin/env python3
"""
狼人杀分析系统 - 自动化测试脚本
运行: python test_system.py
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg): print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
def print_error(msg): print(f"{Colors.RED}✗{Colors.RESET} {msg}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")
def print_info(msg): print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")

class SystemTester:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.project_root = Path(__file__).parent

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("狼人杀分析系统 - 自动化测试")
        print("="*60 + "\n")

        # 1. 环境检查
        self.test_environment()

        # 2. 文件结构检查
        self.test_file_structure()

        # 3. 后端代码检查
        self.test_backend_code()

        # 4. 前端代码检查
        self.test_frontend_code()

        # 5. JSON解析测试
        asyncio.run(self.test_json_parsing())

        # 6. 配置文件检查
        self.test_configuration()

        # 7. 依赖检查
        self.test_dependencies()

        # 打印总结
        self.print_summary()

    def test_environment(self):
        """测试环境配置"""
        print_info("检查环境配置...")

        # 检查Python版本
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            print_success(f"Python版本: {version.major}.{version.minor}.{version.micro}")
        else:
            print_error(f"Python版本过低: {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)")
            self.errors.append("Python版本过低")

        # 检查API Key
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if api_key and api_key.startswith("sk-"):
            print_success("DEEPSEEK_API_KEY 已设置")
        else:
            # 检查.env文件
            env_file = self.project_root / "backend" / ".env"
            if env_file.exists():
                content = env_file.read_text()
                if "DEEPSEEK_API_KEY=sk-" in content:
                    print_success("DEEPSEEK_API_KEY 在.env文件中已设置")
                else:
                    print_error(".env文件中没有有效的DEEPSEEK_API_KEY")
                    self.errors.append("API Key未设置")
            else:
                print_error("未找到backend/.env文件，且环境变量未设置")
                self.errors.append("API Key未设置")

    def test_file_structure(self):
        """测试文件结构"""
        print_info("检查文件结构...")

        required_dirs = [
            "backend",
            "frontend/src",
            "prompts",
            "formats",
            "outputs",
            "uploads"
        ]

        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if full_path.exists():
                print_success(f"目录存在: {dir_path}")
            else:
                print_warning(f"目录不存在: {dir_path}")
                self.warnings.append(f"缺少目录: {dir_path}")

        # 检查关键文件
        required_files = {
            "backend/main.py": "FastAPI主服务",
            "backend/analyzer.py": "分析引擎",
            "backend/requirements.txt": "后端依赖",
            "frontend/package.json": "前端依赖",
            "frontend/vite.config.ts": "Vite配置",
            "prompts/v1_stage1_facts_prompt.txt": "Stage1 Prompt",
            "prompts/v1_stage2_speeches_prompt.txt": "Stage2 Prompt",
            "prompts/v1_stage3_intent_prompt.txt": "Stage3 Prompt",
        }

        for file_path, desc in required_files.items():
            full_path = self.project_root / file_path
            if full_path.exists():
                print_success(f"文件存在: {file_path} ({desc})")
            else:
                print_error(f"文件不存在: {file_path} ({desc})")
                self.errors.append(f"缺少文件: {file_path}")

    def test_backend_code(self):
        """测试后端代码"""
        print_info("检查后端代码...")

        # 检查analyzer.py
        analyzer_path = self.project_root / "backend" / "analyzer.py"
        if analyzer_path.exists():
            content = analyzer_path.read_text(encoding="utf-8")

            # 检查关键函数
            required_funcs = [
                "load_dotenv",
                "extract_json_text",
                "normalize_json",
                "try_repair_json",
                "call_deepseek_streaming",
                "StreamingAnalyzer"
            ]

            for func in required_funcs:
                if func in content:
                    print_success(f"函数/类存在: {func}")
                else:
                    if func == "load_dotenv":
                        # load_dotenv 应该在 main.py 中
                        pass
                    else:
                        print_error(f"函数/类不存在: {func}")
                        self.errors.append(f"analyzer.py缺少: {func}")

            # 检查错误处理
            if "try_repair_json" in content:
                print_success("已添加JSON修复功能")
            else:
                print_warning("缺少JSON修复功能")
                self.warnings.append("建议添加try_repair_json函数")

        # 检查main.py
        main_path = self.project_root / "backend" / "main.py"
        if main_path.exists():
            content = main_path.read_text(encoding="utf-8")

            if "load_dotenv" in content:
                print_success("main.py已加载.env文件")
            else:
                print_error("main.py未加载.env文件")
                self.errors.append("main.py缺少load_dotenv")

            if "WebSocket" in content:
                print_success("WebSocket端点已配置")
            else:
                print_error("WebSocket端点未配置")
                self.errors.append("缺少WebSocket支持")

    def test_frontend_code(self):
        """测试前端代码"""
        print_info("检查前端代码...")

        # 检查package.json
        pkg_path = self.project_root / "frontend" / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                deps = pkg.get("dependencies", {})

                required_deps = ["vue", "element-plus", "pinia"]
                for dep in required_deps:
                    if dep in deps:
                        print_success(f"依赖已安装: {dep}@{deps[dep]}")
                    else:
                        print_error(f"依赖未安装: {dep}")
                        self.errors.append(f"缺少前端依赖: {dep}")
            except json.JSONDecodeError:
                print_error("package.json格式错误")
                self.errors.append("package.json格式错误")

        # 检查关键组件
        components = [
            "App.vue",
            "components/UploadSection.vue",
            "components/AnalysisProgress.vue",
            "components/ResultsView.vue",
            "stores/analysis.ts"
        ]

        for comp in components:
            comp_path = self.project_root / "frontend" / "src" / comp
            if comp_path.exists():
                print_success(f"组件存在: {comp}")
            else:
                print_error(f"组件不存在: {comp}")
                self.errors.append(f"缺少组件: {comp}")

        # 检查TypeScript配置
        tsconfig_path = self.project_root / "frontend" / "tsconfig.json"
        tsconfig_node_path = self.project_root / "frontend" / "tsconfig.node.json"

        if tsconfig_path.exists():
            print_success("tsconfig.json存在")
        else:
            print_error("tsconfig.json不存在")
            self.errors.append("缺少tsconfig.json")

        if tsconfig_node_path.exists():
            print_success("tsconfig.node.json存在")
        else:
            print_error("tsconfig.node.json不存在")
            self.errors.append("缺少tsconfig.node.json")

    async def test_json_parsing(self):
        """测试JSON解析"""
        print_info("测试JSON解析功能...")

        try:
            from analyzer import extract_json_text, normalize_json, try_repair_json

            # 测试1: 标准JSON
            test_cases = [
                ('{"key": "value"}', "标准JSON"),
                ('```json\n{"key": "value"}\n```', "Markdown代码块"),
                ('Some text {"key": "value"} more text', "嵌入文本的JSON"),
                ('{"key": "value",}', "带尾部逗号的JSON"),
                ('{"key": "value"', "不完整的JSON（缺少})"),
                ('[1, 2, 3,]', "带尾部逗号的数组"),
            ]

            for test_input, desc in test_cases:
                try:
                    extracted = extract_json_text(test_input)
                    normalized = normalize_json(extracted)
                    repaired = try_repair_json(normalized)
                    parsed = json.loads(repaired)
                    print_success(f"解析成功: {desc}")
                except Exception as e:
                    print_error(f"解析失败: {desc} - {e}")
                    self.errors.append(f"JSON解析测试失败: {desc}")

        except ImportError as e:
            print_error(f"无法导入analyzer模块: {e}")
            self.errors.append("analyzer模块导入失败")

    def test_configuration(self):
        """测试配置文件"""
        print_info("检查配置文件...")

        # 检查vite.config.ts代理配置
        vite_config = self.project_root / "frontend" / "vite.config.ts"
        if vite_config.exists():
            content = vite_config.read_text()
            if "proxy" in content and "/api" in content:
                print_success("Vite代理配置正确")
            else:
                print_warning("Vite代理配置可能不完整")
                self.warnings.append("检查Vite代理配置")

        # 检查数据库初始化
        db_path = self.project_root / "backend" / "database.py"
        if db_path.exists():
            content = db_path.read_text()
            if "CREATE TABLE IF NOT EXISTS" in content:
                print_success("数据库表结构定义正确")
            else:
                print_warning("数据库表结构定义可能不完整")

    def test_dependencies(self):
        """测试依赖安装"""
        print_info("检查依赖安装...")

        # 检查Python依赖
        backend_reqs = self.project_root / "backend" / "requirements.txt"
        if backend_reqs.exists():
            required_packages = [
                "fastapi",
                "uvicorn",
                "websockets",
                "aiohttp",
                "aiosqlite",
                "pydantic",
                "python-dotenv"
            ]

            content = backend_reqs.read_text()
            for pkg in required_packages:
                if pkg in content.lower():
                    print_success(f"后端依赖声明: {pkg}")
                else:
                    print_warning(f"后端可能缺少依赖: {pkg}")
                    self.warnings.append(f"检查依赖: {pkg}")

        # 尝试导入关键模块
        try:
            import fastapi
            print_success("FastAPI已安装")
        except ImportError:
            print_error("FastAPI未安装")
            self.errors.append("运行: pip install fastapi")

        try:
            import aiohttp
            print_success("aiohttp已安装")
        except ImportError:
            print_error("aiohttp未安装")
            self.errors.append("运行: pip install aiohttp")

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)

        if not self.errors and not self.warnings:
            print_success("所有检查通过！系统看起来正常。")
        else:
            if self.errors:
                print_error(f"发现 {len(self.errors)} 个错误:")
                for err in self.errors:
                    print(f"  - {err}")

            if self.warnings:
                print_warning(f"发现 {len(self.warnings)} 个警告:")
                for warn in self.warnings:
                    print(f"  - {warn}")

        print("\n" + "="*60)

        # 给出修复建议
        if self.errors:
            print("\n修复建议:")
            print("1. 确保所有依赖已安装:")
            print("   cd backend && pip install -r requirements.txt")
            print("   cd frontend && npm install")
            print("\n2. 确保.env文件配置正确:")
            print("   cd backend")
            print("   echo DEEPSEEK_API_KEY=sk-xxx > .env")
            print("\n3. 重启服务:")
            print("   cd backend && uvicorn main:app --reload --port 8000")
            print("   cd frontend && npm run dev")

if __name__ == "__main__":
    tester = SystemTester()
    tester.run_all_tests()
