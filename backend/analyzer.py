"""
狼人杀 AI 分析引擎（Streaming Analyzer）

【文件定位】
这是核心的 AI 分析模块，负责与 DeepSeek API 交互，完成三阶段分析。

【核心功能】
1. 三阶段 Pipeline：Stage1 → Stage2 → Stage3
2. 流式处理：实时接收 AI 输出，边接收边解析
3. 数据清洗：Stage3 前隐藏敏感信息实现"盲推"
4. 错误处理：JSON 解析失败时自动尝试修复

【关键类】
- StreamingAnalyzer: 主分析器类，管理三阶段分析流程

【调用方式】
```python
analyzer = StreamingAnalyzer(task_id, callback)
result = await analyzer.run_full_pipeline(
    transcript=转录文本,
    format_rules=版型规则,
    game_name=游戏名
)
```

【关于流式输出】
DeepSeek Reasoner 模型返回两种内容：
- reasoning_content: AI 的思考过程（我们展示给用户看）
- content: AI 的正式输出（JSON 格式，需要解析）
"""
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Callable, Dict, Any, Optional, Awaitable, Union, List, Tuple

import aiohttp
from models import AnalysisStatus, StageProgress, StageStatus, PlayerInference

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
print(f"[DEBUG] DEEPSEEK_API_KEY loaded: {'Yes (masked)' if DEEPSEEK_API_KEY else 'No'}")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-reasoner"

PROJECT_ROOT = Path(__file__).parent.parent


def read_text(path: Path) -> str:
    """读取文本文件"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030")


def load_prompt(template_path: Path, **kwargs) -> str:
    """加载并填充 prompt 模板"""
    text = read_text(template_path)
    for key, value in kwargs.items():
        placeholder = f"{{{{{key}}}}}"
        text = text.replace(placeholder, value)
    return text


def normalize_whitespace(text: str) -> str:
    """归一化空白字符：将换行符替换为空格，便于文本匹配"""
    if not text:
        return ""
    # 1. 将换行符替换为空格
    # 2. 将逗号、句号后的多个空格替换为单个空格
    # 3. 将多个连续空格替换为单个空格
    text = re.sub(r'[\n\r]+', ' ', text)
    text = re.sub(r'([，。、！？.,!?])[ ]+', r'\1', text)  # 标点后的空格去掉
    text = re.sub(r'[ ]+', ' ', text)  # 多个空格合并为一个
    return text.strip()


def extract_json_text(text: str) -> str:
    """从模型输出中提取 JSON"""
    stripped = text.strip()

    # 去掉 Reasoner 的思考过程标签 <think>...</think>
    if stripped.startswith("<think>"):
        # 找到 </think> 标签并去掉其前面的内容
        think_end = stripped.find("</think>")
        if think_end != -1:
            stripped = stripped[think_end + len("</think>"):].strip()

    # 检查是否是纯JSON对象或数组（允许不完整，由 try_repair_json 修复）
    if stripped.startswith("{"):
        return stripped
    if stripped.startswith("["):
        return stripped

    # 尝试提取 markdown 代码块中的 JSON 对象
    md_match = re.search(r"```(?:json)?\s*(\{.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if md_match:
        return md_match.group(1).strip()

    # 尝试提取 markdown 代码块中的 JSON 数组
    md_match_array = re.search(r"```(?:json)?\s*(\[.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if md_match_array:
        return md_match_array.group(1).strip()

    # 尝试提取花括号对象
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return stripped[first_brace:last_brace+1].strip()

    # 尝试提取中括号数组
    first_bracket = stripped.find("[")
    last_bracket = stripped.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return stripped[first_bracket:last_bracket+1].strip()

    # 如果没有找到，返回原字符串
    return stripped


def normalize_json(text: str) -> str:
    """清洗 JSON 字符串"""
    # 替换中文引号
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")

    # 移除所有控制字符（保留换行和制表符用于后续处理）
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)

    # 修复尾部逗号问题 (在 } 或 ] 之前的逗号)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # 修复对象和数组之间的逗号问题
    text = re.sub(r"}\s*{", "},{", text)
    text = re.sub(r"]\s*\[", "],[", text)
    text = re.sub(r"}\s*\[", "},[", text)
    text = re.sub(r"]\s*{", "],{", text)

    # 修复布尔值和 null 的常见错误格式
    text = text.replace("True", "true").replace("False", "false").replace("None", "null")

    return text


def try_repair_json(text: str) -> str:
    """尝试修复不完整的 JSON"""
    # 计算未闭合的括号
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    # 添加缺失的闭合括号
    if open_braces > 0:
        text += '}' * open_braces
    if open_brackets > 0:
        text += ']' * open_brackets

    # 如果字符串以逗号结尾，移除它
    text = text.rstrip().rstrip(',')

    return text


async def call_deepseek_streaming(
    prompt: str,
    max_tokens: int = 8192,
    temperature: float = 0.0,
    on_reasoning: Optional[Callable[[str], Awaitable[None]]] = None,
    on_content: Optional[Callable[[str], Awaitable[None]]] = None,
    model: str = None
) -> Dict[str, Any]:
    """流式调用 DeepSeek API"""

    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set")

    # 使用指定的模型或默认模型
    model_to_use = model or DEFAULT_MODEL

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Connection": "keep-alive",
    }
    payload = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": "你是严谨的数据抽取与推理引擎，必须输出合法 JSON。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,  # 启用流式输出
        "stream_options": {"include_usage": True}
    }

    # 初始化累积变量（在函数开头定义，确保最终返回时可用）
    full_content = ""
    full_reasoning = ""

    # 重试机制
    max_retries = 3
    retry_delay = 5  # 初始重试延迟5秒

    for attempt in range(max_retries):
        # 每次重试时清空累积内容，防止重复追加
        full_content = ""
        full_reasoning = ""

        try:
            # 创建客户端会话，使用更宽松的设置
            timeout = aiohttp.ClientTimeout(
                total=3600,      # 总超时1小时
                connect=60,      # 连接超时60秒
                sock_read=300    # 读取超时5分钟（允许长期间无数据）
            )
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                enable_cleanup_closed=True,
                force_close=False,  # 允许连接复用
            )

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        # 如果是服务器错误，尝试重试
                        if resp.status >= 500 and attempt < max_retries - 1:
                            print(f"API 服务器错误 {resp.status}，{retry_delay}秒后重试...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                        raise RuntimeError(f"API error {resp.status}: {error_text}")

                    async for line in resp.content:
                        if not line:
                            continue
                        try:
                            line_str = line.decode('utf-8').strip()
                        except UnicodeDecodeError:
                            continue

                        if not line_str or not line_str.startswith('data: '):
                            continue

                        data_str = line_str[6:]  # Remove 'data: '
                        if data_str == '[DONE]':
                            print(f"[DONE] Total reasoning: {len(full_reasoning)} chars, content: {len(full_content)} chars")
                            return {
                                "content": full_content,
                                "reasoning_content": full_reasoning
                            }

                        try:
                            data = json.loads(data_str)

                            # 检查是否有错误
                            if data.get('error'):
                                raise RuntimeError(f"Stream error: {data['error']}")

                            delta = data.get('choices', [{}])[0].get('delta', {})

                            # 处理推理内容 - DeepSeek Reasoner 使用 reasoning_content 字段
                            reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')
                            if reasoning:
                                full_reasoning += reasoning
                                if on_reasoning:
                                    await on_reasoning(reasoning)

                            # 处理正式内容
                            content = delta.get('content', '')
                            if content:
                                full_content += content
                                if on_content:
                                    await on_content(content)

                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"Error processing chunk: {e}")
                            continue

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                print(f"API 调用超时，{retry_delay}秒后重试...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise RuntimeError("API 调用超时（1小时），请检查网络连接或稍后重试")

        except aiohttp.ClientError as e:
            error_str = str(e)
            # 连接被重置，尝试重试
            if "Connection reset" in error_str or "Connection closed" in error_str or "Not enough data" in error_str:
                if attempt < max_retries - 1:
                    print(f"连接中断，{retry_delay}秒后重试... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
            raise RuntimeError(f"网络连接错误: {e}")

        # 成功完成，跳出重试循环
        break

    return {
        "content": full_content,
        "reasoning_content": full_reasoning
    }


class StreamingAnalyzer:
    """流式分析器，支持实时推送"""

    def __init__(self, task_id: str, websocket_callback: Callable):
        self.task_id = task_id
        self.ws_callback = websocket_callback
        self.reasoning_buffer = []
        self.player_inferences = {}
        self.current_stage = 0

    async def send(self, msg_type: str, data: Dict) -> bool:
        """发送 WebSocket 消息，返回是否成功"""
        try:
            print(f"[Analyzer] Sending {msg_type}")
            await self.ws_callback({
                "type": msg_type,
                "task_id": self.task_id,
                "data": data,
                "timestamp": time.time()
            })
            return True
        except Exception as e:
            # WebSocket 可能已关闭，静默失败
            print(f"[Analyzer] Failed to send {msg_type}: {e}")
            return False

    async def on_reasoning_chunk(self, chunk: str) -> None:
        """处理推理内容片段 - 实时发送到前端"""
        self.reasoning_buffer.append(chunk)

        # 累积内容，每100字符或包含换行时发送（平衡实时性和频率）
        buffer_text = "".join(self.reasoning_buffer)
        last_sent = getattr(self, '_last_sent_reasoning_length', 0)

        should_send = (
            len(buffer_text) - last_sent >= 100 or  # 累积100字符
            '\n' in chunk or  # 遇到换行
            len(chunk) > 50  # 单次内容较长
        )

        if should_send:
            success = await self.send("reasoning", {
                "stage": self.current_stage,
                "content": buffer_text,
                "delta": chunk
            })
            if success:
                self._last_sent_reasoning_length = len(buffer_text)

        # Stage 3: 实时提取玩家推断
        if self.current_stage == 3:
            await self._extract_player_inferences_from_chunk(chunk)

    async def _extract_player_inferences_from_chunk(self, chunk: str) -> None:
        """从单个 reasoning chunk 中实时提取玩家推断"""
        # 检测天数变化
        if not hasattr(self, '_current_inference_day'):
            self._current_inference_day = 1

        day_match = re.search(r'[第\s]*(\d+|[一二三四五六七八九十]+)[天\s]', chunk)
        if day_match:
            day_str = day_match.group(1)
            try:
                if day_str.isdigit():
                    self._current_inference_day = int(day_str)
                else:
                    cn_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                               '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                    self._current_inference_day = cn_nums.get(day_str, self._current_inference_day)
            except:
                pass

        # 提取玩家推断 - 匹配 "X号玩家" 或 "玩家X号" 模式
        player_patterns = [
            r'["\']?(\d+)["\']?\s*号(?:玩家)?[:：\s]+([^\n]{10,300})',
            r'玩家\s*(\d+)\s*号?[:：\s]+([^\n]{10,300})',
        ]

        for pattern in player_patterns:
            matches = re.findall(pattern, chunk)
            for player_id, inference_text in matches:
                # 提取概率
                wolf_prob = None
                prob_match = re.search(r'狼人.*?(?:概率|置信度|confidence).*?([\d.]+)', inference_text, re.I)
                if prob_match:
                    try:
                        wolf_prob = float(prob_match.group(1))
                        if wolf_prob > 1:
                            wolf_prob = wolf_prob / 100
                    except:
                        wolf_prob = 0.5

                # 提取角色猜测
                role_guess = "unknown"
                if re.search(r'狼人|wolf', inference_text, re.I):
                    role_guess = "狼人"
                elif re.search(r'平民|villager|good', inference_text, re.I):
                    role_guess = "平民"
                elif re.search(r'通灵师|预言家|seer', inference_text, re.I):
                    role_guess = "通灵师"
                elif re.search(r'女巫|witch', inference_text, re.I):
                    role_guess = "女巫"
                elif re.search(r'猎人|hunter', inference_text, re.I):
                    role_guess = "猎人"
                elif re.search(r'守卫|guard', inference_text, re.I):
                    role_guess = "守卫"

                inference = {
                    "player_id": player_id,
                    "day": self._current_inference_day,
                    "role_guess": role_guess,
                    "wolf_probability": wolf_prob or 0.5,
                    "good_probability": 1 - (wolf_prob or 0.5),
                    "reason": inference_text[:200],
                    "confidence": wolf_prob or 0.5,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
                }

                if player_id not in self.player_inferences:
                    self.player_inferences[player_id] = []
                self.player_inferences[player_id].append(inference)

                # 发送实时更新 - 修复格式以匹配前端期望
                await self.send("player_update", {
                    "inference": inference
                })

    async def on_content_chunk(self, chunk: str) -> None:
        """处理正式输出内容片段 - 实时发送到前端"""
        if not hasattr(self, 'content_buffer'):
            self.content_buffer = []
        self.content_buffer.append(chunk)

        # 累积内容，每50字符或包含重要标记时发送
        buffer_text = "".join(self.content_buffer)
        last_sent = getattr(self, '_last_sent_content_length', 0)

        should_send = (
            len(buffer_text) - last_sent >= 50 or  # 累积50字符
            '{' in chunk or  # JSON 开始
            '}' in chunk or  # JSON 结束
            '"' in chunk     # 关键标记
        )

        if should_send:
            success = await self.send("content", {
                "stage": self.current_stage,
                "content": buffer_text,
                "delta": chunk
            })
            if success:
                self._last_sent_content_length = len(buffer_text)

    async def run_stage1(self, main_transcript: str, format_rules: str, postgame_transcript: str = None) -> Dict:
        """运行 Stage 1：事实抽取（双文件版本）

        Args:
            main_transcript: 对局正文（从321天亮了开始）
            format_rules: 版型规则
            postgame_transcript: 赛后复盘（包含真实身份，可选）

        Returns:
            Dict containing 'meta', 'class_1_structured_facts', and 'day_boundaries'
        """
        self.current_stage = 1

        await self.send("stage_start", {
            "stage": 1,
            "name": "事实抽取",
            "status": "running"
        })

        # 发送测试消息，确认前端能正常接收
        await self.send("reasoning", {
            "stage": 1,
            "content": "[系统] 开始调用 DeepSeek API 进行事实抽取分析...",
            "delta": "[系统] 开始调用 DeepSeek API 进行事实抽取分析..."
        })

        # 【双文件版本】构建输入
        if postgame_transcript:
            # 有复盘文件：正文+复盘分开输入
            transcript_input = f"""【游戏正文】（从321天亮了开始到游戏结束前）
{main_transcript}

【赛后复盘】（包含真实身份和夜间信息）
{postgame_transcript}"""
        else:
            # 无复盘文件：只用正文（兼容旧模式）
            transcript_input = main_transcript

        # 加载 prompt
        prompt_path = PROJECT_ROOT / "prompts" / "v1_stage1_facts_prompt.txt"
        prompt = load_prompt(
            prompt_path,
            FORMAT_RULES=format_rules,
            RAW_TRANSCRIPT=transcript_input
        )

        # 流式调用 - Stage 1 使用 Reasoner 模型（更准确的分段和事实提取）
        result = await call_deepseek_streaming(
            prompt,
            max_tokens=16000,
            on_reasoning=lambda chunk: asyncio.create_task(self.on_reasoning_chunk(chunk)),
            on_content=lambda chunk: asyncio.create_task(self.on_content_chunk(chunk)),
            model="deepseek-reasoner"
        )

        # Flush 剩余 content
        await self._flush_content()

        # 尝试解析 JSON，如果失败则尝试修复
        raw_content = result["content"]

        # 【调试】保存原始输出到文件
        debug_dir = Path(__file__).parent / "debug_outputs"
        debug_dir.mkdir(exist_ok=True)
        debug_file = debug_dir / f"stage1_raw_{self.task_id or 'unknown'}.txt"
        debug_file.write_text(raw_content, encoding="utf-8")
        print(f"[Stage 1] 原始输出已保存到: {debug_file}")

        try:
            json_text = extract_json_text(raw_content)
            json_text = normalize_json(json_text)
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            # 尝试修复
            repaired = try_repair_json(json_text)
            try:
                parsed = json.loads(repaired)
            except:
                # 保存失败内容供调试
                error_file = debug_dir / f"stage1_error_{self.task_id or 'unknown'}.txt"
                error_file.write_text(
                    f"=== 原始输出 ===\n{raw_content}\n\n"
                    f"=== 提取的 JSON ===\n{json_text}\n\n"
                    f"=== 尝试修复后 ===\n{repaired}",
                    encoding="utf-8"
                )
                print(f"[Stage 1] 解析失败内容已保存到: {error_file}")
                raise RuntimeError(f"Stage 1 JSON 解析失败，调试文件: {error_file}")
        except Exception as e:
            raise RuntimeError(f"Stage 1 JSON 解析失败: {e}")

        # Flush 剩余推理内容
        await self._flush_reasoning()

        # 【提取segments供后续Stage使用】
        segments = parsed.get("meta", {}).get("segments", [])
        print(f"[Stage 1] Extracted {len(segments)} segments")

        # 【不再提取text字段，减少输出体积】
        # segments 只保留锚点信息，Stage 2 使用时从原始文件提取
        segments_without_text = []
        for seg in segments:
            seg_clean = {
                "type": seg.get("type"),
                "day": seg.get("day"),
                "name": seg.get("name"),
                "start_anchor": seg.get("start_anchor"),
                "end_anchor": seg.get("end_anchor"),
                "contains_commentary": seg.get("contains_commentary", False),
                "for_stage2": seg.get("for_stage2", True)
            }
            segments_without_text.append(seg_clean)

        print(f"[Stage 1] Segments prepared (without text field): {len(segments_without_text)}")

        # 将segments放到meta中，便于前端访问
        if "meta" not in parsed:
            parsed["meta"] = {}
        parsed["meta"]["segments"] = segments_without_text

        await self.send("stage_complete", {
            "stage": 1,
            "name": "事实抽取",
            "status": "completed",
            "result": parsed
        })

        # 【新增】保存正常输出到 outputs/（便于查看）
        outputs_dir = PROJECT_ROOT / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_file = outputs_dir / f"stage1_{self.task_id or 'unknown'}.json"
        output_file.write_text(
            json.dumps({
                "meta": parsed.get("meta"),
                "class_1_structured_facts": parsed.get("class_1_structured_facts"),
                "segments": segments_without_text
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[Stage 1] Output saved to: {output_file}")

        # 返回完整结果
        return {
            "meta": parsed.get("meta"),
            "class_1_structured_facts": parsed.get("class_1_structured_facts"),
            "segments": segments_without_text
        }

    def _extract_segment_by_anchors(self, full_transcript: str, segment: Dict) -> Optional[Dict]:
        """根据锚点文本在原文中提取段落内容

        匹配策略：
        1. 先尝试精确匹配
        2. 精确失败时记录警告，尝试模糊匹配（降低阈值）
        3. 如果都找不到，返回None供上层处理

        Args:
            full_transcript: 完整转写文本
            segment: 包含 start_anchor 和 end_anchor 的分段配置

        Returns:
            包含提取文本的segment字典，如果提取失败则返回None
        """
        start_anchor = segment.get("start_anchor", "")
        end_anchor = segment.get("end_anchor", "")
        seg_name = segment.get('name', 'unknown')

        if not start_anchor:
            print(f"[WARN] Segment {seg_name} has no start_anchor")
            return None

        # 【归一化】处理换行符：将锚点和原文中的换行都替换为空格
        # 这样即使原文有换行而锚点没有（或反之），也能匹配成功
        norm_anchor = normalize_whitespace(start_anchor)
        norm_transcript = normalize_whitespace(full_transcript)

        # Step 1: 尝试精确匹配（使用归一化后的文本）
        start_pos = norm_transcript.find(norm_anchor)
        match_method = "exact"

        # Step 2: 精确失败，尝试标准模糊匹配（使用归一化文本）
        if start_pos == -1:
            print(f"[WARN] Segment {seg_name}: 精确匹配失败，尝试模糊匹配...")
            start_pos = self._fuzzy_find(norm_transcript, norm_anchor, min_ratio=0.85)
            match_method = "fuzzy(0.85)"

        # Step 3: 仍然失败，尝试更宽松的模糊匹配
        if start_pos == -1:
            print(f"[WARN] Segment {seg_name}: 标准模糊匹配失败，尝试宽松匹配...")
            start_pos = self._fuzzy_find(norm_transcript, norm_anchor, min_ratio=0.70)
            match_method = "fuzzy(0.70)"

        # Step 4: 还是失败，返回None
        if start_pos == -1:
            print(f"[ERROR] Segment {seg_name}: 无法匹配起始锚点: {start_anchor[:40]}...")
            return None

        print(f"[Segment] {seg_name}: 起始锚点匹配成功 ({match_method})")

        # 查找结束位置（同样的策略，使用归一化文本）
        end_pos = -1
        if end_anchor:
            norm_end_anchor = normalize_whitespace(end_anchor)
            # 先精确匹配
            end_pos = norm_transcript.find(norm_end_anchor, start_pos + len(norm_anchor))
            if end_pos == -1:
                end_pos = self._fuzzy_find(norm_transcript, norm_end_anchor, start_pos + len(norm_anchor), min_ratio=0.85)
            if end_pos == -1:
                end_pos = self._fuzzy_find(norm_transcript, norm_end_anchor, start_pos + len(norm_anchor), min_ratio=0.70)

        # 注意：所有匹配都在归一化文本上进行，因此从归一化文本提取
        # 这样即使换行符被替换为空格，内容也是一致的
        if end_pos == -1:
            # 找不到结束锚点，就用归一化文本的结束
            end_pos = len(norm_transcript)
            print(f"[WARN] Segment {seg_name}: 未找到结束锚点，使用全文结束")
        else:
            # 找到end_anchor，包含它本身的长度
            norm_end_anchor = normalize_whitespace(end_anchor) if end_anchor else ""
            end_pos += len(norm_end_anchor)

        # 从归一化文本中提取（确保位置对应）
        extracted_text = norm_transcript[start_pos:end_pos].strip()

        if not extracted_text:
            print(f"[WARN] Empty text extracted for segment {segment.get('name', 'unknown')}")
            return None

        print(f"[Segment] {segment.get('name', 'unknown')}: extracted {len(extracted_text)} chars")

        # 返回包含文本的完整segment
        return {
            **segment,
            "text": extracted_text,
            "start_pos": start_pos,
            "end_pos": end_pos
        }

    def _fuzzy_find(self, text: str, pattern: str, start: int = 0, min_ratio: float = 0.85) -> int:
        """模糊查找文本位置（优化版本）

        Args:
            text: 原文
            pattern: 要查找的模式
            start: 开始搜索的位置
            min_ratio: 最小相似度阈值

        Returns:
            找到的位置，-1表示未找到
        """
        from difflib import SequenceMatcher

        if not pattern or not text:
            return -1

        # 先尝试精确匹配
        exact_pos = text.find(pattern, start)
        if exact_pos != -1:
            return exact_pos

        # 精确匹配失败，用模糊匹配
        # 取pattern的前30字作为搜索key（减少计算量）
        search_key = pattern[:30] if len(pattern) > 30 else pattern
        key_len = len(search_key)

        # 如果文本太长，采样搜索而不是逐字符滑动（提升性能）
        text_len = len(text)
        step = 1 if text_len < 10000 else 3  # 长文本时每隔3字符检查一次

        best_ratio = 0
        best_pos = -1

        # 滑动窗口搜索
        search_end = min(start + 5000, text_len - key_len + 1)  # 限制搜索范围，避免全文扫描
        for i in range(start, search_end, step):
            window = text[i:i + key_len]
            ratio = SequenceMatcher(None, search_key, window).quick_ratio()  # 使用quick_ratio更快
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = i

        # 如果找到高相似度位置，在附近进行精细搜索
        if best_pos != -1 and best_ratio >= min_ratio * 0.9:  # 放宽一点阈值来触发精细搜索
            fine_start = max(start, best_pos - 10)
            fine_end = min(search_end, best_pos + 10)
            for i in range(fine_start, fine_end):
                if i == best_pos:
                    continue
                window = text[i:i + key_len]
                ratio = SequenceMatcher(None, search_key, window).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pos = i

        if best_ratio >= min_ratio:
            print(f"  [Fuzzy] Found match at {best_pos} with ratio {best_ratio:.2f}")
            return best_pos

        return -1

    async def _flush_reasoning(self):
        """发送剩余的推理内容"""
        buffer_text = "".join(self.reasoning_buffer)
        last_sent = getattr(self, '_last_sent_reasoning_length', 0)
        if len(buffer_text) > last_sent:
            await self.send("reasoning", {
                "stage": self.current_stage,
                "content": buffer_text,
                "delta": buffer_text[last_sent:]
            })
            self._last_sent_reasoning_length = len(buffer_text)

    async def _flush_content(self):
        """发送剩余的正式输出内容"""
        if not hasattr(self, 'content_buffer'):
            return
        buffer_text = "".join(self.content_buffer)
        last_sent = getattr(self, '_last_sent_content_length', 0)
        if len(buffer_text) > last_sent:
            await self.send("content", {
                "stage": self.current_stage,
                "content": buffer_text,
                "delta": buffer_text[last_sent:]
            })
            self._last_sent_content_length = len(buffer_text)

    async def run_stage2_single_day(
        self,
        transcript: str,
        format_rules: str,
        day_num: int,
        day_description: str,
        day_context: str = "",
        send_progress: bool = True
    ) -> Dict:
        """运行 Stage 2 单日处理：整理特定白天的发言

        Args:
            transcript: 该白天的转写文本
            format_rules: 版型规则
            day_num: 天数编号（0=警上竞选, 1=第一天, 2=第二天...）
            day_description: 天数描述（用于prompt）
            day_context: 前文上下文（用于理解当前天数的背景）
            send_progress: 是否发送进度消息（分批处理时只由 batch 函数发送一次）
        """
        self.current_stage = 2

        # 发送 Stage 2 开始消息（仅在单天处理且不是由 batch 函数调用时）
        if send_progress:
            await self.send("stage_start", {
                "stage": 2,
                "name": "发言整理",
                "status": "running"
            })

        # 构建day_type描述
        if day_num == 0:
            day_type = "警上竞选环节"
        else:
            day_type = f"第{day_num}天白天"

        # 发送进度消息（让前端知道正在处理第几天）
        if send_progress:
            await self.send("day_progress", {
                "stage": 2,
                "day": day_num,
                "day_type": day_type,
                "status": "processing",
                "message": f"正在处理 {day_type}..."
            })

        # 构建上下文信息
        context_text = ""
        if day_context:
            context_text = f"\n【前文背景】\n{day_context}\n"

        prompt_path = PROJECT_ROOT / "prompts" / "v1_stage2_speeches_prompt.txt"
        prompt = load_prompt(
            prompt_path,
            FORMAT_RULES=format_rules,
            RAW_TRANSCRIPT=transcript,
            DAY_DESCRIPTION=day_description,
            DAY_TYPE=day_type,
            DAY_CONTEXT=context_text
        )

        # 流式调用 - Stage 2 使用 Reasoner 模型进行发言分析
        # 增加 max_tokens 避免长对局被截断
        result = await call_deepseek_streaming(
            prompt,
            max_tokens=24000,
            on_reasoning=lambda chunk: asyncio.create_task(self.on_reasoning_chunk(chunk)),
            on_content=lambda chunk: asyncio.create_task(self.on_content_chunk(chunk)),
            model="deepseek-reasoner"
        )

        # Flush 剩余 content
        await self._flush_content()

        # 尝试解析 JSON，如果失败则尝试修复
        raw_content = result["content"]
        try:
            json_text = extract_json_text(raw_content)
            json_text = normalize_json(json_text)
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            print(f"[DEBUG] Initial JSON parse failed, attempting repair")
            # 尝试修复
            repaired = try_repair_json(json_text)
            try:
                parsed = json.loads(repaired)
                print("[DEBUG] JSON repaired and parsed successfully")
            except:
                # 保存失败的 JSON 供调试（统一放到 debug_outputs）
                error_path = PROJECT_ROOT / "debug_outputs" / f"error_stage2_{int(time.time())}.txt"
                error_path.parent.mkdir(exist_ok=True)
                error_path.write_text(f"Original:\n{raw_content}\n\nExtracted:\n{json_text}\n\nRepaired:\n{repaired}", encoding="utf-8")
                print(f"[DEBUG] Failed content saved to: {error_path}")
                raise RuntimeError(f"Stage 2 JSON 解析失败，内容已保存到: {error_path}")
        except Exception as e:
            raise RuntimeError(f"Stage 2 JSON 解析失败: {e}")

        # Flush 剩余推理内容
        await self._flush_reasoning()

        # 发送完成进度（非 stage_complete，只是日进度）
        if send_progress:
            await self.send("day_progress", {
                "stage": 2,
                "day": day_num,
                "day_type": day_type,
                "status": "completed",
                "message": f"{day_type} 处理完成"
            })

        # 添加day标记到结果
        parsed["_day"] = day_num
        parsed["_day_type"] = day_type

        return parsed

    def _extract_day_transcript(
        self,
        full_transcript: str,
        day_boundary: Dict,
        next_day_boundary: Dict = None
    ) -> str:
        """根据day_boundary从完整转写中提取特定白天的文本

        Args:
            full_transcript: 完整转写文本
            day_boundary: 当前天的边界信息（包含start_marker和end_marker）
            next_day_boundary: 下一天的边界信息（用于确定end位置，可选）

        Returns:
            该白天的转写文本
        """
        start_marker = day_boundary.get("start_marker", "")
        end_marker = day_boundary.get("end_marker", "")

        if not start_marker:
            return ""

        # 提取起始标记的关键部分（前15-30字）
        start_key = start_marker[:30] if len(start_marker) > 30 else start_marker

        # 查找起始位置
        start_pos = full_transcript.find(start_key)
        if start_pos == -1:
            # 尝试更短的匹配
            start_key = start_marker[:15] if len(start_marker) > 15 else start_marker
            start_pos = full_transcript.find(start_key)

        if start_pos == -1:
            print(f"[WARN] Cannot find start marker: {start_key[:20]}...")
            return ""

        # 确定结束位置
        if next_day_boundary and next_day_boundary.get("start_marker"):
            # 使用下一天的start_marker作为当前天的结束
            next_start_key = next_day_boundary["start_marker"][:30]
            end_pos = full_transcript.find(next_start_key, start_pos + len(start_key))
            if end_pos == -1:
                end_pos = len(full_transcript)
        elif end_marker:
            # 使用当前天的end_marker
            end_key = end_marker[:30] if len(end_marker) > 30 else end_marker
            end_pos = full_transcript.find(end_key, start_pos + len(start_key))
            if end_pos == -1:
                end_pos = len(full_transcript)
            else:
                end_pos += len(end_key)
        else:
            end_pos = len(full_transcript)

        return full_transcript[start_pos:end_pos].strip()

    async def run_stage2_batch(
        self,
        main_transcript: str,
        format_rules: str,
        segments: List[Dict],
        stage1_facts: Dict = None
    ) -> Dict:
        """运行 Stage 2 批量处理：按段落处理所有白天的发言

        Args:
            main_transcript: 对局正文（完整转写，备用）
            format_rules: 版型规则
            segments: 分段列表（从Stage 1获取，包含已提取的文本）
            stage1_facts: Stage 1提取的事实（用于提供上下文）

        Returns:
            合并后的Stage 2结果
        """
        all_speeches = []
        all_commentator_segments = []

        # 只处理 for_stage2=true 的段落（白天发言，不含夜间解说）
        stage2_segments = [s for s in segments if s.get("for_stage2", True)]

        if not stage2_segments:
            print("[WARN] No segments for Stage 2, processing as single batch")
            return await self.run_stage2_single_day(
                main_transcript, format_rules, 1, "完整对局", ""
            )

        print(f"[Stage 2] Processing {len(stage2_segments)} segments (skipped {len(segments) - len(stage2_segments)} commentary segments)")

        # 发送 Stage 2 开始消息（只发送一次）
        await self.send("stage_start", {
            "stage": 2,
            "name": "发言整理",
            "status": "running",
            "total_segments": len(stage2_segments)
        })

        # 构建前文上下文（用于理解背景）
        context_parts = []
        if stage1_facts:
            players = stage1_facts.get("players", {})
            # 添加关键信息到上下文
            for player_id, player_data in players.items():
                badge_info = player_data.get("police_badge", {})
                if badge_info.get("won_badge") == "yes":
                    context_parts.append(f"{player_id}号当选警长")

        # 按段落处理
        processed_count = 0
        for i, segment in enumerate(stage2_segments):
            seg_type = segment.get("type", "daytime")
            day_num = segment.get("day", i)
            seg_name = segment.get("name", f"第{day_num}天")

            # 【修改】根据锚点从原始文本提取内容（不再使用 segment.text）
            seg_result = self._extract_segment_by_anchors(main_transcript, segment)
            seg_text = seg_result.get("text", "") if seg_result else ""

            if not seg_text:
                print(f"[WARN] Cannot extract text for segment {seg_name}, skipping")
                # 标记提取失败
                segment["_extracted"] = False
                continue

            # 标记提取成功
            segment["_extracted"] = True

            # 截断过长的文本（避免token超限）
            if len(seg_text) > 15000:
                print(f"[WARN] Segment {seg_name} too long ({len(seg_text)} chars), truncating")
                seg_text = seg_text[:15000] + "\n...[内容截断]"

            # 构建上下文
            day_context = "\n".join(context_parts)

            # 发送进度消息
            await self.send("day_progress", {
                "stage": 2,
                "segment_index": i,
                "segment_name": seg_name,
                "segment_type": seg_type,
                "status": "processing",
                "message": f"正在处理 {seg_name}..."
            })

            print(f"[Stage 2] Processing {seg_name}: {len(seg_text)} chars")

            try:
                # 处理该段落（使用 segment 的名称作为描述）
                day_result = await self.run_stage2_single_day(
                    seg_text,
                    format_rules,
                    day_num,
                    seg_name,
                    day_context,
                    send_progress=False
                )

                # 合并结果
                speeches = day_result.get("class_2_daytime_speeches", [])
                all_speeches.extend(speeches)

                commentator = day_result.get("class_3_commentator_content", {})
                if commentator and commentator != "[HIDDEN]":
                    segs = commentator.get("segments", [])
                    all_commentator_segments.extend(segs)

                # 更新上下文（添加当前段落的关键信息）
                for speech in speeches:
                    if speech.get("day") == day_num and "放逐" in str(speech.get("text_summary", "")):
                        context_parts.append(f"第{day_num}天: {speech.get('text_summary', '')[:50]}...")

                processed_count += 1

                # 【新增】保存每天的结果到 outputs/
                outputs_dir = PROJECT_ROOT / "outputs"
                outputs_dir.mkdir(exist_ok=True)
                day_output_file = outputs_dir / f"stage2_day{day_num}_{self.task_id or 'unknown'}.json"
                day_output_file.write_text(
                    json.dumps({
                        "day": day_num,
                        "segment_name": seg_name,
                        "class_2_daytime_speeches": speeches,
                        "class_3_commentator_content": commentator if commentator != "[HIDDEN]" else {}
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"[Stage 2] Day {day_num} output saved to: {day_output_file}")

                # 发送完成进度
                await self.send("day_progress", {
                    "stage": 2,
                    "segment_index": i,
                    "segment_name": seg_name,
                    "segment_type": seg_type,
                    "status": "completed",
                    "message": f"{seg_name} 处理完成"
                })

                # 短暂暂停，避免API限流
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[ERROR] Failed to process segment {seg_name}: {e}")
                # 继续处理下一段
                continue

        # ═══════════════════════════════════════════════════════════════════════
        # 【新增】检测因锚点匹配失败而缺失的段落
        # 注意：狼人自爆跳过白天是正常游戏规则，不算缺失
        # 这里只检测那些 for_stage2=True 但因锚点匹配失败而未处理的段落
        # ═══════════════════════════════════════════════════════════════════════
        expected_days = set(seg.get("day", 0) for seg in stage2_segments if seg.get("for_stage2", True))
        actually_processed_days = set(seg.get("day", 0) for seg in stage2_segments
                                      if seg.get("for_stage2", True) and seg.get("_extracted", False))
        failed_extractions = expected_days - actually_processed_days

        if failed_extractions:
            warning_msg = f"[WARN] 以下天数因锚点匹配失败未能提取文本: {sorted(failed_extractions)}"
            print(warning_msg)
            await self.send("warning", {
                "stage": 2,
                "type": "extraction_failed",
                "message": f"第 {sorted(failed_extractions)} 天文本提取失败，已尝试模糊匹配",
                "expected_days": sorted(expected_days),
                "failed_days": sorted(failed_extractions)
            })
        # ═══════════════════════════════════════════════════════════════════════

        # 合并所有结果
        merged_result = {
            "class_2_daytime_speeches": all_speeches,
            "class_3_commentator_content": {
                "segments": all_commentator_segments
            }
        }

        print(f"[Stage 2] Completed: {len(all_speeches)} speeches from {processed_count} segments")

        # 发送 Stage 2 完成消息（只发送一次，包含合并后的结果）
        await self.send("stage_complete", {
            "stage": 2,
            "name": "发言整理",
            "status": "completed",
            "total_segments": len(stage2_segments),
            "processed_segments": processed_count,
            "result": merged_result
        })

        return merged_result

    def _sanitize_for_blind_inference(self, stage1_result: Dict, stage2_result: Dict) -> Tuple[Dict, Dict]:
        """
        清洗数据用于盲推阶段（phase_A）

        保留公开信息：
        - 票型（警长投票、白天放逐投票）
        - 昨夜死亡信息（白天宣布的死亡）
        - 发言内容和立场

        隐藏信息：
        - 真实身份
        - 详细夜晚行动（狼刀目标、女巫解药/毒药等）
        - 胜负结果
        - 解说内容
        """
        import copy

        # 深拷贝避免修改原始数据
        s1 = copy.deepcopy(stage1_result)
        s2 = copy.deepcopy(stage2_result)

        # === 清洗 Stage 1 ===
        if "class_1_structured_facts" in s1:
            facts = s1["class_1_structured_facts"]

            # 1. 隐藏玩家真实身份（fact_role）
            # 但保留公开行为：警徽操作、死亡状态（白天看到的）、投票行为
            if "players" in facts:
                for player_id, player_data in facts["players"].items():
                    # 隐藏真实身份
                    if "fact_role" in player_data:
                        player_data["fact_role"] = "[HIDDEN]"

                    # 保留 elimination 中的公开信息（死亡是白天宣布的）
                    # 但标记为"公开可见"
                    if "elimination" in player_data:
                        elim = player_data["elimination"]
                        # 这些是公开的：白天宣布谁死了、被放逐了
                        # 保留：night_killed_on_day（昨夜死亡是公开的）
                        # 保留：poisoned_on_day（女巫毒药死是公开的）
                        # 保留：voted_out_on_day（白天放逐是公开的）
                        # 保留：final_status（最终是否存活是公开的）
                        pass  # 保留 elimination 信息

            # 2. 隐藏详细夜晚事件（暴露狼刀、女巫解药/毒药、守卫守护、通灵师查验等）
            # 这些只有上帝视角能看到
            if "night_events_by_day" in facts:
                # 只保留夜晚结果摘要（如果有的话），隐藏详细行动
                night_events = facts["night_events_by_day"]
                sanitized_events = []
                for event in night_events:
                    # 只保留：是否有死亡（公开信息）
                    sanitized_event = {
                        "day": event.get("day"),
                        "phase": event.get("phase"),
                        # 只暴露：谁死了（白天宣布的）
                        "night_outcome_summary": event.get("night_outcome_summary", "[HIDDEN]")
                    }
                    # 显式隐藏所有夜晚敏感信息
                    # wolf_kill_target, witch_save_target, witch_poison_target, guard_target
                    # seer_or_medium_check（查验结果是核心敏感信息！）
                    # mechanic_wolf_learn, mechanic_wolf_kill
                    sanitized_events.append(sanitized_event)
                facts["night_events_by_day"] = sanitized_events

            # 3. 隐藏全局胜负结果
            if "global_result" in facts:
                facts["global_result"] = "[HIDDEN]"

        # === 清洗 Stage 2 ===
        # 保留 class_2_daytime_speeches（玩家发言是公开的）
        # 隐藏 class_3_commentator_content（解说可能剧透）
        if "class_3_commentator_content" in s2:
            s2["class_3_commentator_content"] = "[HIDDEN]"

        return s1, s2

    async def run_stage3(self, stage1_result: Dict, stage2_result: Dict) -> Dict:
        """运行 Stage 3：意图分析（支持实时解析）"""
        self.current_stage = 3

        await self.send("stage_start", {
            "stage": 3,
            "name": "意图分析",
            "status": "running"
        })

        # Stage 3：传入完整数据（包含真实身份），AI 在 phase_A 盲推，phase_B 验证
        # 注意：不再使用 _sanitize_for_blind_inference，依靠 prompt 规则约束 AI
        s1_full = stage1_result
        s2_full = stage2_result

        prompt_path = PROJECT_ROOT / "prompts" / "v1_stage3_intent_prompt.txt"
        prompt = load_prompt(
            prompt_path,
            STAGE1_JSON=json.dumps(s1_full, ensure_ascii=False),
            STAGE2_JSON=json.dumps(s2_full, ensure_ascii=False)
        )

        # Stage 3 的特殊处理：实时解析玩家推断
        content_buffer = []

        async def on_content_chunk_local(chunk: str):
            content_buffer.append(chunk)
            # 同时发送到前端
            await self.on_content_chunk(chunk)

        # 流式调用 - Stage 3 使用 Reasoner 模型进行意图推理
        # 增加 max_tokens 避免复杂对局的意图分析被截断
        result = await call_deepseek_streaming(
            prompt,
            max_tokens=16000,
            on_reasoning=lambda chunk: asyncio.create_task(self.on_reasoning_chunk(chunk)),
            on_content=on_content_chunk_local,
            model="deepseek-reasoner"
        )

        # Flush 剩余 content
        await self._flush_content()

        # 尝试实时提取玩家推断更新
        await self.extract_player_inferences_realtime(result["reasoning_content"])

        # 尝试解析 JSON，如果失败则尝试修复
        raw_content = result["content"]
        try:
            json_text = extract_json_text(raw_content)
            json_text = normalize_json(json_text)
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            print(f"[DEBUG] Stage 3 JSON parse failed, attempting repair")
            # 尝试修复
            repaired = try_repair_json(json_text)
            try:
                parsed = json.loads(repaired)
                print("[DEBUG] Stage 3 JSON repaired successfully")
            except:
                # 保存失败的 JSON 供调试（统一放到 debug_outputs）
                error_path = PROJECT_ROOT / "debug_outputs" / f"error_stage3_{int(time.time())}.txt"
                error_path.parent.mkdir(exist_ok=True)
                error_path.write_text(f"Original:\n{raw_content}\n\nExtracted:\n{json_text}\n\nRepaired:\n{repaired}", encoding="utf-8")
                print(f"[DEBUG] Stage 3 failed content saved to: {error_path}")
                raise RuntimeError(f"Stage 3 JSON 解析失败，内容已保存到: {error_path}")
        except Exception as e:
            raise RuntimeError(f"Stage 3 JSON 解析失败: {e}")

        # Flush 剩余推理内容
        await self._flush_reasoning()

        await self.send("stage_complete", {
            "stage": 3,
            "name": "意图分析",
            "status": "completed",
            "result": parsed
        })

        # 【新增】保存正常输出到 outputs/
        outputs_dir = PROJECT_ROOT / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_file = outputs_dir / f"stage3_{self.task_id or 'unknown'}.json"
        output_file.write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[Stage 3] Output saved to: {output_file}")

        return parsed

    async def extract_player_inferences_realtime(self, reasoning: str):
        """
        从 Stage 3 的 reasoning 中实时提取玩家身份推断
        并发送给前端
        """
        # 按天分割推理内容
        day_sections = re.split(r'(第[一二三四五六七八九十]+天|Day\s*\d+)', reasoning)

        current_day = 1
        for i, section in enumerate(day_sections):
            # 检测天数标记
            day_match = re.search(r'[第\s]*(\d+|[一二三四五六七八九十]+)[天\s]', section)
            if day_match:
                day_str = day_match.group(1)
                try:
                    if day_str.isdigit():
                        current_day = int(day_str)
                    else:
                        cn_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                                   '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                        current_day = cn_nums.get(day_str, current_day)
                except:
                    pass
                continue

            # 提取玩家推断
            # 模式："X号玩家" + 推断内容
            player_patterns = [
                r'["\']?(\d+)["\']?\s*号(?:玩家)?[:：\s]+([^\n]{10,200})',
                r'玩家\s*(\d+)\s*号?[:：\s]+([^\n]{10,200})',
            ]

            for pattern in player_patterns:
                matches = re.findall(pattern, section)
                for player_id, inference_text in matches:
                    # 提取概率
                    wolf_prob = None
                    prob_match = re.search(r'狼人.*?(?:概率|置信度|confidence).*?([\d.]+)', inference_text, re.I)
                    if prob_match:
                        wolf_prob = float(prob_match.group(1))
                        if wolf_prob > 1:
                            wolf_prob = wolf_prob / 100

                    # 提取角色猜测
                    role_guess = "unknown"
                    if re.search(r'狼人|wolf', inference_text, re.I):
                        role_guess = "狼人"
                    elif re.search(r'平民|villager|good', inference_text, re.I):
                        role_guess = "平民"
                    elif re.search(r'通灵师|预言家|seer', inference_text, re.I):
                        role_guess = "通灵师"
                    elif re.search(r'女巫|witch', inference_text, re.I):
                        role_guess = "女巫"
                    elif re.search(r'猎人|hunter', inference_text, re.I):
                        role_guess = "猎人"
                    elif re.search(r'守卫|guard', inference_text, re.I):
                        role_guess = "守卫"

                    inference = PlayerInference(
                        player_id=player_id,
                        day=current_day,
                        role_guess=role_guess,
                        wolf_probability=wolf_prob or 0.5,
                        good_probability=1 - (wolf_prob or 0.5),
                        reason=inference_text[:200],  # 截取前200字符
                        confidence=wolf_prob or 0.5
                    )

                    if player_id not in self.player_inferences:
                        self.player_inferences[player_id] = []
                    self.player_inferences[player_id].append(inference)

                    # 注意：推断已在实时流中发送，这里不再重复发送
                    # 这个方法仅用于最终整理和归档

    async def run_full_pipeline(
        self,
        main_transcript: str,
        format_rules: str,
        game_name: str,
        start_stage: int = 1,
        existing_results: Dict = None,
        postgame_transcript: str = None
    ) -> Dict:
        """运行完整的三阶段流水线，支持断点续传（双文件版本）

        Args:
            main_transcript: 对局正文（从321天亮了开始）
            format_rules: 版型规则
            game_name: 对局名称
            start_stage: 从第几阶段开始（1-3，用于断点续传）
            existing_results: 已有的阶段结果（用于断点续传）
            postgame_transcript: 赛后复盘文本（可选，包含真实身份）
        """
        try:
            stage1_result = None
            stage2_result = None
            stage3_result = None
            segments = None  # 存储分段信息（包含白天和解说段落）

            # Stage 1（双文件版本）
            if start_stage <= 1:
                stage1_full = await self.run_stage1(main_transcript, format_rules, postgame_transcript)
                # 提取segments供Stage 2使用（包含已提取的文本内容）
                segments = stage1_full.get("segments", [])
                stage1_result = {
                    "meta": stage1_full.get("meta"),
                    "class_1_structured_facts": stage1_full.get("class_1_structured_facts")
                }
                await asyncio.sleep(0.5)
            elif existing_results and existing_results.get("stage1_result"):
                stage1_result = existing_results["stage1_result"]
                # 尝试从existing_results中获取segments
                segments = existing_results.get("segments", [])
                await self.send("stage_complete", {
                    "stage": 1,
                    "result": stage1_result
                })
                await asyncio.sleep(0.1)

            # Stage 2（按段落分批处理）
            if start_stage <= 2:
                # 使用segments进行分批处理（只处理for_stage2=true的段落）
                stage1_facts = stage1_result.get("class_1_structured_facts", {}) if stage1_result else {}
                stage2_result = await self.run_stage2_batch(
                    main_transcript, format_rules, segments or [], stage1_facts
                )
                await asyncio.sleep(0.5)
            elif existing_results and existing_results.get("stage2_result"):
                stage2_result = existing_results["stage2_result"]
                await self.send("stage_complete", {
                    "stage": 2,
                    "result": stage2_result
                })
                await asyncio.sleep(0.1)

            # Stage 3 (需要 Stage 1 和 2 的结果)
            if start_stage <= 3:
                # 确保 Stage 1 和 2 有结果
                if not stage1_result:
                    raise ValueError("Stage 3 requires Stage 1 result")
                if not stage2_result:
                    raise ValueError("Stage 3 requires Stage 2 result")
                stage3_result = await self.run_stage3(stage1_result, stage2_result)
            elif existing_results and existing_results.get("stage3_result"):
                stage3_result = existing_results["stage3_result"]
                await self.send("stage_complete", {
                    "stage": 3,
                    "result": stage3_result
                })
                await asyncio.sleep(0.1)

            # 合并结果
            pipeline_result = {
                **(stage1_result or {}),
                **(stage2_result or {}),
                **(stage3_result or {}),
                "segments": segments,  # 包含所有分段信息（白天+解说）
                "pipeline_meta": {
                    "mode": "pipeline",
                    "stage1_model": "deepseek-reasoner",
                    "stage2_model": "deepseek-reasoner",
                    "stage2_processing": "segment_by_segment",  # 标记为按段落分批处理
                    "stage3_model": "deepseek-reasoner",
                    "created_at": int(time.time()),
                    "game_name": game_name
                }
            }

            await self.send("analysis_complete", {
                "status": "completed",
                "result": pipeline_result
            })

            return pipeline_result

        except Exception as e:
            await self.send("error", {
                "message": str(e),
                "stage": self.current_stage
            })
            raise
