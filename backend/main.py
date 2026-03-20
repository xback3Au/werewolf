"""
FastAPI backend with WebSocket support for real-time analysis

【文件定位】
这是后端服务的入口文件，负责：
1. 提供 REST API（文件上传、分析记录管理）
2. 提供 WebSocket 服务（实时分析通信）
3. 协调 analyzer.py 进行 AI 分析

【关键概念】
- 任务(task): 一次完整的三阶段分析，用 task_id 标识
- 阶段(stage): 1=事实提取, 2=发言整理, 3=意图推断
- 断点续传: 如果分析中断，下次可以从断点继续
- WebSocket 回调: analyzer 通过回调实时发送消息给前端

【数据流】
前端(上传文件) → WebSocket连接 → StreamingAnalyzer → DeepSeek API → 流式返回 → 前端实时显示
"""
import asyncio
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load environment variables from .env file (包含 DEEPSEEK_API_KEY)
load_dotenv()

# 【内部模块】
from models import AnalysisStatus, SavedAnalysis
from database import (
    init_db, save_analysis, get_analysis, get_analysis_by_label, get_analysis_by_file_id,
    list_analyses, delete_analysis, save_speeches, save_votes,
    save_day_segments, get_day_segments,
    save_inference_chains, save_timeline_events, save_operation_strategies, save_knowledge_chunks
)
from analyzer import StreamingAnalyzer, read_text, PROJECT_ROOT

app = FastAPI(title="狼人杀分析系统", version="1.0.0")

# CORS 配置（开发环境允许所有）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储活动连接和任务
active_connections: Dict[str, WebSocket] = {}
active_tasks: Dict[str, StreamingAnalyzer] = {}

# 上传目录
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
async def startup():
    """启动时初始化数据库"""
    await init_db()
    print("Database initialized")


@app.get("/")
async def root():
    """返回前端页面"""
    frontend_path = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "狼人杀分析系统 API 运行中", "docs": "/docs"}


@app.get("/api/formats")
async def get_formats() -> List[dict]:
    """获取所有可用的版型规则"""
    formats_dir = PROJECT_ROOT / "formats"
    formats = []
    if formats_dir.exists():
        for file in formats_dir.glob("*.txt"):
            formats.append({
                "name": file.stem,
                "file_path": str(file.relative_to(PROJECT_ROOT)),
                "size": file.stat().st_size
            })
    return formats


def extract_base_name(filename: str) -> str:
    """
    提取文件的基础名称用于分组匹配
    从文件名中提取日期(20260102格式)和局数(第X局/第X天)作为标签

    支持格式：
    - "20260317第三局.txt" -> "20260317_第三局"
    - "20260317第三局复盘.txt" -> "20260317_第三局"
    - "20260317-第三局-机械狼.txt" -> "20260317_第三局"
    - "20260317第3局.txt" -> "20260317_第3局"
    """
    # 移除扩展名
    name = filename
    if name.lower().endswith('.txt'):
        name = name[:-4]

    # 移除复盘相关后缀（支持 -复盘、_复盘、复盘 等格式）
    # 匹配分隔符(-或_) + 复盘关键词，或直接以复盘关键词结尾
    pattern = r'[-_\s]?((?:复盘|postgame|赛后|身份))$'
    name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # 提取日期格式 (8位数字，如 20260317)
    date_match = re.search(r'(\d{8})', name)
    date_part = date_match.group(1) if date_match else ""

    # 提取局数（第X局 或 第X天，X可以是汉字或数字）
    # 支持：第1局、第一局、第3天、第三天 等
    round_match = re.search(r'第[一二三四五六七八九十1234567890]+[局天]', name)
    round_part = round_match.group(0) if round_match else ""

    # 组合标签：日期_局数
    if date_part and round_part:
        return f"{date_part}_{round_part}"
    elif date_part:
        return date_part
    elif round_part:
        return round_part
    else:
        # 如果都没匹配到，返回去掉复盘后缀后的原始名称
        return name


def is_postgame_file(filename: str) -> bool:
    """判断是否为复盘文件（包含复盘相关关键词）"""
    fname = filename.lower()
    return any(keyword in fname for keyword in ["复盘", "postgame", "赛后", "身份"])


@app.get("/api/uploads")
async def get_uploaded_files() -> List[dict]:
    """获取已上传的文件列表，按文件组（对局）组织

    分组策略（按优先级）：
    1. 相同 label 的文件归为一组
    2. 文件名匹配：基础名称相同的正文文件和复盘文件归为一组
       例如："20260317第三局.txt" 和 "20260317第三局复盘.txt"
    3. 单个文件独立成组
    """
    # 先收集所有文件
    all_files = []
    if UPLOAD_DIR.exists():
        for file in UPLOAD_DIR.glob("*.txt"):
            stat = file.stat()
            file_name = file.name

            # 提取原始文件名：移除ID前缀（如 "02af0d4c_原始文件名.txt"）
            original_name = file_name
            file_id = file.stem.split('_')[0] if '_' in file_name else file.stem
            if '_' in file_name and len(file_name.split('_')[0]) == 8:
                # 移除UUID前缀，恢复原始文件名
                original_name = '_'.join(file_name.split('_')[1:])
                if not original_name:
                    original_name = file_name

            # 从文件名提取标签（用于分组显示）
            extracted_label = extract_base_name(original_name)

            file_data = {
                "file_id": file_id,
                "filename": original_name,
                "file_path": str(file.relative_to(PROJECT_ROOT)),
                "size": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extracted_label": extracted_label,  # 从文件名提取的标签
            }

            print(f"[DEBUG] Found file: {file_name} -> original_name={original_name}, file_id={file_id}, size={stat.st_size}, extracted_label={extracted_label}")

            # 查找关联的分析记录（通过 file_id）
            analysis = await get_analysis_by_file_id(file_id)
            if analysis:
                file_data["label"] = analysis.get("label")  # 用户自定义标签（优先级低）
                file_data["format_name"] = analysis.get("format_name")

            # 防止重复添加同一文件（基于 file_path 和 file_id 双重检查）
            file_path_str = str(file.relative_to(PROJECT_ROOT))
            is_duplicate = any(f["file_path"] == file_path_str or f["file_id"] == file_id for f in all_files)
            if not is_duplicate:
                all_files.append(file_data)
                print(f"[DEBUG] Added file to all_files: {original_name} (id={file_id}, path={file_path_str})")
            else:
                print(f"[DEBUG] Skipped duplicate file: {original_name} (id={file_id})")

    # 分组策略：
    # 1. 有相同 label 的文件归为一组
    # 2. 按基础文件名分组（正文+复盘自动配对）
    groups = {}
    ungrouped_files = []

    for file in all_files:
        # 优先使用从文件名提取的标签（更准确），其次用用户自定义标签
        label = file.get("extracted_label") or file.get("label")
        if label:
            # 有标签，按标签分组
            if label not in groups:
                groups[label] = {"label": label, "files": []}
            groups[label]["files"].append(file)
            print(f"[DEBUG] File '{file['filename']}' (id={file['file_id']}) has label '{label}', added to labeled group")
        else:
            # 没有标签，按文件名分组
            ungrouped_files.append(file)
            print(f"[DEBUG] File '{file['filename']}' (id={file['file_id']}) has no label, added to ungrouped")

    # 处理无标签文件：尝试匹配到有标签的组，或按基础文件名分组
    for file in ungrouped_files:
        base_name = extract_base_name(file["filename"])

        # 首先尝试匹配到有标签的组（检查该组的文件是否有相同base_name）
        found_group = False
        for group_key, group in list(groups.items()):
            if group.get("label") is not None:  # 有标签的组
                for existing_file in group.get("files", []):
                    existing_base = extract_base_name(existing_file["filename"])
                    if existing_base == base_name:
                        group["files"].append(file)
                        found_group = True
                        print(f"[DEBUG] Added file '{file['filename']}' to labeled group '{group_key}' (matched base_name)")
                        break
                if found_group:
                    break

        if not found_group:
            # 尝试匹配到无标签的组
            for group_key, group in list(groups.items()):
                if group.get("label") is None:  # 无标签的组
                    existing_file = group["files"][0] if group.get("files") else None
                    if existing_file:
                        existing_base = extract_base_name(existing_file["filename"])
                        if existing_base == base_name:
                            group["files"].append(file)
                            found_group = True
                            print(f"[DEBUG] Added file '{file['filename']}' to unlabeled group '{group_key}'")
                            break

        if not found_group:
            # 创建新组，使用基础文件名作为key
            group_key = f"_auto_{base_name}_"
            groups[group_key] = {"label": None, "files": [file]}
            print(f"[DEBUG] Created new group '{group_key}' for file '{file['filename']}'")

    # 调试日志
    print(f"[DEBUG] Total groups: {len(groups)}")
    for group_key, group in groups.items():
        print(f"[DEBUG] Group '{group_key}': {len(group['files'])} files")
        for f in group['files']:
            print(f"[DEBUG]   - {f['filename']} (id={f['file_id']}, size={f['size']})")

    # 构建返回结果
    result = []
    for group_key, group in groups.items():
        files = group["files"]
        if not files:
            continue

        # 按上传时间排序
        files.sort(key=lambda x: x["uploaded_at"])

        # 判断哪个是正文，哪个是复盘
        # 策略：文件名包含"复盘"等关键词的是复盘文件，其余是正文
        main_file = None
        postgame_file = None
        postgame_candidates = []
        main_candidates = []

        for f in files:
            if is_postgame_file(f["filename"]):
                postgame_candidates.append(f)
            else:
                main_candidates.append(f)

        # 如果有多个候选，选文件大小最大的
        if main_candidates:
            main_file = max(main_candidates, key=lambda x: x["size"])
        if postgame_candidates:
            postgame_file = max(postgame_candidates, key=lambda x: x["size"])

        # 如果没有主文件候选，但有复盘候选，把最大的复盘文件作为主文件（兜底）
        if main_file is None and postgame_candidates:
            main_file = postgame_candidates[0]
            if len(postgame_candidates) > 1:
                postgame_file = postgame_candidates[1]

        print(f"[DEBUG] Group result: main={main_file['filename'] if main_file else None}, postgame={postgame_file['filename'] if postgame_file else None}")

        # 获取组的分析状态（基于 main_file）
        analysis_status = "not_started"
        completed_stages = []
        has_analysis = False
        analysis_id = None
        format_name = None

        check_file = main_file or files[0]
        if check_file:
            analysis = await get_analysis_by_file_id(check_file["file_id"])
            if analysis:
                has_analysis = True
                analysis_id = analysis["id"]
                format_name = analysis.get("format_name")

                # 计算已完成的阶段
                if analysis.get("stage1_result"):
                    completed_stages.append(1)
                if analysis.get("stage2_result"):
                    completed_stages.append(2)
                if analysis.get("stage3_result"):
                    completed_stages.append(3)

                if len(completed_stages) == 3:
                    analysis_status = "completed"
                elif len(completed_stages) > 0:
                    analysis_status = f"stage{completed_stages[-1]}"

        # 确定显示用的 label
        display_label = group["label"]
        if not display_label and group_key.startswith("_auto_"):
            # 从自动分组 key 中提取标签，如 "_auto_20260317_第三局_" -> "20260317_第三局"
            display_label = group_key[6:-1]  # 去掉 "_auto_" 前缀和结尾的 "_"

        group_data = {
            "group_id": group_key if group["label"] else (main_file["file_id"] if main_file else files[0]["file_id"]),
            "label": display_label,
            "main_file": main_file,
            "postgame_file": postgame_file,
            "total_files": len(files),
            "uploaded_at": files[0]["uploaded_at"],  # 最早上传时间
            "analysis_status": analysis_status,
            "completed_stages": completed_stages,
            "has_analysis": has_analysis,
            "analysis_id": analysis_id,
            "format_name": format_name
        }

        result.append(group_data)

    # 按上传时间倒序排列
    result.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return result


@app.delete("/api/uploads/{file_id}")
async def delete_uploaded_file(file_id: str):
    """删除已上传的文件及相关数据

    支持两种格式：
    1. 有UUID前缀：abc12345_文件名.txt
    2. 无UUID前缀：文件名.txt（此时file_id就是文件名）

    同时会清理：
    - 数据库中的分析记录
    - outputs/ 目录下的输出文件
    - debug_outputs/ 目录下的调试文件
    """
    print(f"[DELETE] Attempting to delete file with ID: {file_id}")

    deleted_count = 0
    deleted_files = []

    # 先尝试精确匹配（无UUID前缀的文件）
    for file in UPLOAD_DIR.glob("*.txt"):
        stem = file.stem
        print(f"[DELETE] Checking file: {file.name}, stem: {stem}")

        # 检查是否是 UUID_文件名 格式
        if '_' in stem and len(stem.split('_')[0]) == 8:
            # 有UUID前缀格式：abc12345_文件名
            extracted_id = stem.split('_')[0]
            print(f"[DELETE]   UUID format detected, extracted_id: {extracted_id}")
            if extracted_id == file_id:
                print(f"[DELETE]   Match found! Deleting {file.name}")
                file.unlink()
                deleted_files.append(file.name)
                deleted_count += 1
        else:
            # 无UUID前缀格式：文件名就是file_id
            if stem == file_id or file.name == file_id:
                print(f"[DELETE]   Match found (no UUID)! Deleting {file.name}")
                file.unlink()
                deleted_files.append(file.name)
                deleted_count += 1

    # 如果没找到，再尝试模糊匹配（file_id可能是文件名的一部分）
    if deleted_count == 0:
        print(f"[DELETE] No exact match, trying fuzzy match...")
        for file in UPLOAD_DIR.glob("*.txt"):
            if file_id in file.name:
                print(f"[DELETE]   Fuzzy match found! Deleting {file.name}")
                file.unlink()
                deleted_files.append(file.name)
                deleted_count += 1

    if deleted_count == 0:
        print(f"[DELETE] File not found: {file_id}")
        raise HTTPException(status_code=404, detail="File not found")

    # ═══════════════════════════════════════════════════════════════════════════
    # 【新增】清理数据库记录和输出文件
    # ═══════════════════════════════════════════════════════════════════════════
    print(f"[DELETE] Cleaning up related data for file_id: {file_id}")

    # 判断是否是复盘文件（文件名包含复盘关键词）
    is_postgame = any(is_postgame_file(f) for f in deleted_files)

    # 如果是复盘文件，只删除文件本身，不清理数据库和输出
    if is_postgame:
        print(f"[DELETE]   Postgame file deleted, no need to clean analysis data")
        return {
            "message": "Postgame file deleted successfully",
            "deleted_files": deleted_files,
            "file_id": file_id
        }

    # 1. 删除数据库中的分析记录（仅主文件）
    try:
        analysis = await get_analysis_by_file_id(file_id)
        if analysis:
            analysis_id = analysis.get('id')
            await delete_analysis(analysis_id)
            print(f"[DELETE]   Deleted analysis record: {analysis_id}")
    except Exception as e:
        print(f"[DELETE]   Warning: Failed to delete analysis record: {e}")

    # 2. 删除 outputs/ 目录下的相关文件
    outputs_dir = PROJECT_ROOT / "outputs"
    if outputs_dir.exists():
        for output_file in outputs_dir.glob(f"*{file_id}*"):
            try:
                output_file.unlink()
                print(f"[DELETE]   Deleted output file: {output_file.name}")
            except Exception as e:
                print(f"[DELETE]   Warning: Failed to delete {output_file.name}: {e}")

    # 3. 删除 debug_outputs/ 目录下的相关文件
    debug_dir = PROJECT_ROOT / "backend" / "debug_outputs"
    if debug_dir.exists():
        for debug_file in debug_dir.glob(f"*{file_id}*"):
            try:
                debug_file.unlink()
                print(f"[DELETE]   Deleted debug file: {debug_file.name}")
            except Exception as e:
                print(f"[DELETE]   Warning: Failed to delete {debug_file.name}: {e}")

    print(f"[DELETE] Successfully deleted {deleted_count} file(s) and related data")
    return {
        "message": "File and related data deleted successfully",
        "deleted_files": deleted_files,
        "file_id": file_id
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    """上传对局文本文件"""
    file_id = str(uuid.uuid4())[:8]
    original_name = file.filename or "unknown.txt"

    # 清理文件名：移除危险字符，保留中文、数字、字母、下划线、连字符
    safe_name = "".join(c for c in original_name if c.isalnum() or c in "._-\u4e00-\u9fff")
    if not safe_name or safe_name == ".txt":
        safe_name = f"game_{file_id}.txt"

    # 确保有 .txt 后缀
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"

    # 用原始文件名（前缀加上ID避免重名）
    file_path = UPLOAD_DIR / f"{file_id}_{safe_name}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "file_id": file_id,
        "filename": original_name,  # 返回原始文件名用于显示
        "file_path": str(file_path.relative_to(PROJECT_ROOT)),
        "size": file_path.stat().st_size,
        "uploaded_at": datetime.now().isoformat()
    }


@app.websocket("/ws/analyze/{task_id}")
async def analyze_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket 端点：实时分析
    【双文件输入版本】
    流程：
    1. 客户端连接后发送配置（main_transcript_path, postgame_transcript_path, format_path, game_name）
    2. 服务端开始三阶段分析，实时推送进度
    3. Stage 1 使用双文件提取结构化信息（含分段边界）
    4. Stage 2 使用分段边界按天分批处理
    5. Stage 3 进行意图推断
    """
    await websocket.accept()
    active_connections[task_id] = websocket

    try:
        # 等待客户端发送配置
        config = await websocket.receive_json()

        # 【双文件支持】接收正文和复盘两个文件路径
        main_transcript_path = PROJECT_ROOT / config["main_transcript_path"]
        postgame_transcript_path = config.get("postgame_transcript_path")
        if postgame_transcript_path:
            postgame_transcript_path = PROJECT_ROOT / postgame_transcript_path

        format_path = PROJECT_ROOT / config["format_path"]
        game_name = config.get("game_name", "unknown_game")
        label = config.get("label")  # 可选的标签，如 "260312-第四局"
        main_file_id = config.get("main_file_id")  # 主文件ID
        postgame_file_id = config.get("postgame_file_id")  # 复盘文件ID

        # 读取文件
        main_transcript = read_text(main_transcript_path)
        postgame_transcript = read_text(postgame_transcript_path) if postgame_transcript_path else None
        format_rules = read_text(format_path)

        # 【Stage 1 输出】分段边界和结构化信息
        stage1_meta = None  # 存储day_boundaries等元数据

        # 创建分析器，包装回调以实时保存阶段结果
        stage_results = {"stage1": None, "stage2": None, "stage3": None}

        async def ws_callback(data: dict):
            # 先发送 WebSocket 消息
            try:
                print(f"[WS Callback] About to send: {data.get('type')}")
                await websocket.send_json(data)
                print(f"[WS Callback] Successfully sent: {data.get('type')}")
            except Exception as e:
                print(f"[WS Callback] Failed to send {data.get('type')}: {e}")
                # 即使发送失败，仍尝试保存到数据库

            # 阶段完成时，保存结果到数据库
            if data.get("type") == "stage_complete":
                stage = data.get("data", {}).get("stage")
                result_data = data.get("data", {}).get("result")
                print(f"[WS Callback] Stage {stage} complete, result: {'present' if result_data else 'missing'}")

                if stage == 1 and result_data:
                    stage_results["stage1"] = {
                        "meta": result_data.get("meta"),
                        "class_1_structured_facts": result_data.get("class_1_structured_facts")
                    }
                    # 提取segments供Stage 2使用
                    nonlocal stage1_meta
                    segments = result_data.get("segments", [])
                    if segments:
                        stage1_meta = {"segments": segments}
                        print(f"[WS Callback] Extracted {len(segments)} segments")
                    print(f"[WS Callback] Saved stage1_result")
                elif stage == 2 and result_data:
                    stage_results["stage2"] = {
                        "class_2_daytime_speeches": result_data.get("class_2_daytime_speeches"),
                        "class_3_commentator_content": result_data.get("class_3_commentator_content")
                    }
                    print(f"[WS Callback] Saved stage2_result")

                    # 保存发言内容到数据库（用于后续查询）
                    speeches = result_data.get("class_2_daytime_speeches", [])
                    if speeches and analysis_id:
                        try:
                            await save_speeches(analysis_id, speeches)
                        except Exception as e:
                            print(f"[WS Callback] Error saving speeches: {e}")

                    # 从 stage1_result 提取并保存票型到数据库
                    votes = []
                    stage1_facts = stage_results.get("stage1", {}).get("class_1_structured_facts", {})
                    day_vote_tables = stage1_facts.get("day_vote_tables", [])
                    for table in day_vote_tables:
                        day = table.get("day", 0)
                        vote_data = table.get("votes", {})
                        for voter_id, target_id in vote_data.items():
                            votes.append({
                                "day": day,
                                "vote_type": "daytime",
                                "voter_id": voter_id,
                                "target_id": target_id
                            })
                    # 警长投票
                    sheriff_table = stage1_facts.get("sheriff_vote_table", {})
                    sheriff_votes = sheriff_table.get("votes", {})
                    for voter_id, target_id in sheriff_votes.items():
                        votes.append({
                            "day": 0,
                            "vote_type": "sheriff",
                            "voter_id": voter_id,
                            "target_id": target_id
                        })
                    if votes and analysis_id:
                        try:
                            await save_votes(analysis_id, votes)
                        except Exception as e:
                            print(f"[WS Callback] Error saving votes: {e}")
                elif stage == 3 and result_data:
                    intent_engine = result_data.get("intent_analysis_engine", {})
                    stage_results["stage3"] = {
                        "intent_analysis_engine": intent_engine
                    }
                    print(f"[WS Callback] Saved stage3_result")

                    # ═══════════════════════════════════════════════════════════════════
                    # 【新增】保存 RAG 数据到数据库
                    # ═══════════════════════════════════════════════════════════════════
                    if analysis_id:
                        try:
                            # 1. 保存推理链
                            daily_chains = intent_engine.get("daily_reasoning_chains", [])
                            if daily_chains:
                                # 转换格式以匹配数据库结构
                                inference_chains = []
                                for chain in daily_chains:
                                    observer_id = chain.get("observer_id")
                                    observer_role = chain.get("observer_role")
                                    day = chain.get("day", 0)
                                    beliefs = chain.get("beliefs", {})
                                    belief_changes = chain.get("belief_changes", {})

                                    # 为每个被推理的玩家创建一条记录
                                    for target_id, belief in beliefs.items():
                                        change_info = belief_changes.get(target_id, {})
                                        inference_chains.append({
                                            "observer_id": observer_id,
                                            "observer_role": observer_role,
                                            "day": day,
                                            "target_id": target_id,
                                            "conclusion_type": "identity",
                                            "conclusion": belief.get("conclusion", ""),
                                            "confidence": belief.get("confidence", 0.5),
                                            "reasoning": belief.get("reasoning", ""),
                                            "evidence_ids": [],
                                            "key_clues": [],
                                            "previous_conclusion": change_info.get("from", ""),
                                            "change_reason": change_info.get("triggered_by", ""),
                                            "is_correct": None,
                                            "truth": ""
                                        })

                                if inference_chains:
                                    await save_inference_chains(analysis_id, inference_chains)
                                    print(f"[WS Callback] Saved {len(inference_chains)} inference chains")

                            # 2. 保存操作策略
                            strategies = intent_engine.get("operation_strategies", [])
                            if strategies:
                                await save_operation_strategies(analysis_id, strategies)
                                print(f"[WS Callback] Saved {len(strategies)} operation strategies")

                            # 3. 保存知识片段
                            chunks = intent_engine.get("knowledge_chunks", [])
                            if chunks:
                                await save_knowledge_chunks(analysis_id, chunks)
                                print(f"[WS Callback] Saved {len(chunks)} knowledge chunks")

                        except Exception as e:
                            print(f"[WS Callback] Error saving RAG data: {e}")

                # 实时保存到数据库
                try:
                    await save_analysis(
                        game_name=game_name,
                        format_name=Path(format_path).stem,
                        stage1=stage_results["stage1"],
                        stage2=stage_results["stage2"],
                        stage3=stage_results["stage3"],
                        analysis_id=analysis_id,  # 使用可能从已有记录获取的 ID
                        label=label,
                        file_id=main_file_id,  # 使用主文件ID
                        stage1_meta=stage1_meta  # 保存分段边界供断点续传使用
                    )
                    print(f"阶段 {stage} 结果已保存 (ID: {analysis_id})")
                except Exception as save_err:
                    print(f"保存阶段 {stage} 结果失败: {save_err}")

        analyzer = StreamingAnalyzer(task_id, ws_callback)
        active_tasks[task_id] = analyzer

        # 检查前端是否指定了开始阶段
        start_stage = config.get("start_stage", 1)
        print(f"[WS] Received start_stage from frontend: {start_stage}, config: {config}")
        existing_results = None
        analysis_id = task_id  # 默认使用新的 task_id

        # 如果前端明确指定从阶段1开始，强制重新分析
        if start_stage == 1:
            print(f"前端要求从阶段1开始，将重新分析")
            # 如果提供了 main_file_id，尝试删除旧记录
            if main_file_id:
                existing_analysis = await get_analysis_by_file_id(main_file_id)
                if existing_analysis:
                    await delete_analysis(existing_analysis["id"])
                    print(f"已删除旧分析记录: {existing_analysis['id']}")
        elif main_file_id:
            # 查询已有的分析记录进行断点续传
            existing_analysis = await get_analysis_by_file_id(main_file_id)
            if existing_analysis:
                # 使用已有的 analysis_id，确保更新同一条记录
                analysis_id = existing_analysis["id"]
                print(f"找到已有分析记录: {analysis_id}")

                # 确定从哪个阶段开始
                completed_stages = []
                if existing_analysis.get("stage1_result"):
                    completed_stages.append(1)
                if existing_analysis.get("stage2_result"):
                    completed_stages.append(2)
                if existing_analysis.get("stage3_result"):
                    completed_stages.append(3)

                if len(completed_stages) < 3:
                    # 有未完成的阶段，默认从下一个阶段开始
                    next_stage = len(completed_stages) + 1
                    print(f"[WS] completed_stages: {completed_stages}, next_stage: {next_stage}, frontend start_stage: {start_stage}")
                    # 如果前端明确指定了起始阶段，且该阶段前序都已完成，则使用前端指定的
                    can_use_frontend_stage = start_stage > 1 and start_stage <= 3 and start_stage <= next_stage
                    print(f"[WS] can_use_frontend_stage: {can_use_frontend_stage} (start_stage > 1: {start_stage > 1}, start_stage <= 3: {start_stage <= 3}, start_stage <= next_stage: {start_stage <= next_stage})")
                    if can_use_frontend_stage:
                        print(f"[WS] Using frontend specified start_stage: {start_stage} (auto-resume would be stage {next_stage})")
                    else:
                        print(f"[WS] Overriding start_stage from {start_stage} to {next_stage}")
                        start_stage = next_stage
                    # 从stage1_meta中提取segments（如果存在）
                    stage1_meta = existing_analysis.get("stage1_meta", {})
                    segments = stage1_meta.get("segments", []) if isinstance(stage1_meta, dict) else []
                    existing_results = {
                        "stage1_result": existing_analysis.get("stage1_result"),
                        "stage2_result": existing_analysis.get("stage2_result"),
                        "stage3_result": existing_analysis.get("stage3_result"),
                        "segments": segments  # 传递分段信息用于Stage 2分批处理
                    }
                    print(f"断点续传: 从阶段 {start_stage} 开始，已完成 {completed_stages}")
                    if segments:
                        print(f"断点续传: 已加载 {len(segments)} 个段落")
                else:
                    # 所有阶段都已完成，设置 existing_results 以便同步到前端
                    print(f"该文件已完成所有阶段分析，将同步已有结果到前端")
                    stage1_meta = existing_analysis.get("stage1_meta", {})
                    segments = stage1_meta.get("segments", []) if isinstance(stage1_meta, dict) else []
                    existing_results = {
                        "stage1_result": existing_analysis.get("stage1_result"),
                        "stage2_result": existing_analysis.get("stage2_result"),
                        "stage3_result": existing_analysis.get("stage3_result"),
                        "segments": segments
                    }

        # 运行分析（双文件版本）
        print(f"[WS] Calling run_full_pipeline with start_stage={start_stage}, existing_results stages: s1={bool(existing_results and existing_results.get('stage1_result'))}, s2={bool(existing_results and existing_results.get('stage2_result'))}, s3={bool(existing_results and existing_results.get('stage3_result'))}")
        result = await analyzer.run_full_pipeline(
            main_transcript=main_transcript,
            format_rules=format_rules,
            game_name=game_name,
            start_stage=start_stage,
            existing_results=existing_results,
            postgame_transcript=postgame_transcript
        )

        # 分析完成，更新最终结果
        print(f"[Main] Pipeline completed. stage_results: s1={bool(stage_results['stage1'])}, s2={bool(stage_results['stage2'])}, s3={bool(stage_results['stage3'])}")
        print(f"[Main] Result keys: {list(result.keys()) if result else 'None'}")

        # 优先使用 stage_results（从回调中收集的），如果没有则使用 result（从 pipeline 返回的）
        final_stage1 = stage_results["stage1"] or {
            "meta": result.get("meta"),
            "class_1_structured_facts": result.get("class_1_structured_facts")
        }
        final_stage2 = stage_results["stage2"] or {
            "class_2_daytime_speeches": result.get("class_2_daytime_speeches"),
            "class_3_commentator_content": result.get("class_3_commentator_content")
        }
        final_stage3 = stage_results["stage3"] or {
            "intent_analysis_engine": result.get("intent_analysis_engine")
        }

        # 提取segments作为stage1_meta存储（用于Stage 2分批处理）
        segments = result.get("segments", [])
        stage1_meta = {"segments": segments} if segments else None

        print(f"[Main] Final stages to save: s1={bool(final_stage1)}, s2={bool(final_stage2)}, s3={bool(final_stage3)}")
        print(f"[Main] Segments: {len(segments)} segments")

        final_analysis_id = await save_analysis(
            game_name=game_name,
            format_name=Path(format_path).stem,
            stage1=final_stage1,
            stage2=final_stage2,
            stage3=final_stage3,
            pipeline=result,
            analysis_id=analysis_id,  # 使用已有的 ID
            label=label,
            file_id=main_file_id,  # 使用主文件ID
            stage1_meta=stage1_meta  # 存储分段边界供后续使用
        )

        # 【新增】保存 segments 到 day_segments 表
        if segments:
            await save_day_segments(final_analysis_id, segments)
            print(f"[Main] Saved {len(segments)} segments to day_segments table")

        await websocket.send_json({
            "type": "saved",
            "task_id": task_id,
            "analysis_id": final_analysis_id,
            "data": {"message": "分析结果已保存", "id": final_analysis_id}
        })

        # 等待一小段时间确保消息发送完毕，然后正常关闭连接
        await asyncio.sleep(0.5)
        try:
            await websocket.close(code=1000, reason="Analysis completed successfully")
        except Exception:
            pass  # 连接可能已经被客户端关闭

    except WebSocketDisconnect:
        print(f"Client {task_id} disconnected")
    except RuntimeError as e:
        # 连接已关闭或API调用失败
        error_msg = str(e)
        print(f"WebSocket error for task {task_id}: {error_msg}")

        # 检查是否是连接被重置错误
        if "Not enough data" in error_msg or "Connection reset" in error_msg:
            print(f"API连接中断，任务 {task_id} 的分析未完成")

        # 尝试保存已完成的部分结果
        try:
            if main_file_id and 'analyzer' in locals() and analyzer and task_id:
                # 从数据库查询已有的分析记录
                existing = await get_analysis_by_file_id(file_id)
                if existing:
                    completed_stages = []
                    if existing.get("stage1_result"):
                        completed_stages.append(1)
                    if existing.get("stage2_result"):
                        completed_stages.append(2)
                    if existing.get("stage3_result"):
                        completed_stages.append(3)
                    print(f"任务 {task_id} 已有阶段 {completed_stages} 完成，可断点续传")
        except Exception as save_error:
            print(f"检查中间结果失败: {save_error}")
    except Exception as e:
        error_msg = str(e)
        print(f"Error in task {task_id}: {error_msg}")
        try:
            if task_id in active_connections:
                await websocket.send_json({
                    "type": "error",
                    "task_id": task_id,
                    "data": {"message": error_msg}
                })
        except Exception:
            # 发送错误消息失败，忽略
            pass
    finally:
        active_connections.pop(task_id, None)
        active_tasks.pop(task_id, None)


@app.get("/api/analyses")
async def get_analyses(limit: int = 50) -> List[dict]:
    """获取历史分析列表"""
    return await list_analyses(limit)


@app.get("/api/analyses/label/{label}")
async def get_analysis_by_label_endpoint(label: str):
    """通过标签获取分析结果"""
    result = await get_analysis_by_label(label)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis with this label not found")
    return result


@app.get("/api/analyses/{analysis_id}")
async def get_analysis_by_id(analysis_id: str):
    """获取单个分析的完整结果"""
    result = await get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.delete("/api/analyses/{analysis_id}")
async def delete_analysis_by_id(analysis_id: str):
    """通过 analysis_id 删除分析"""
    success = await delete_analysis(analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Deleted successfully"}


@app.delete("/api/analyses/by-file")
async def delete_analysis_by_file(
    file_id: Optional[str] = None,
    from_stage: Optional[int] = None
):
    """通过 file_id 删除分析

    Args:
        file_id: 文件ID
        from_stage: 可选，从指定阶段开始清除（1-3），包含该阶段
                   不传则删除整个分析记录
    """
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id is required")

    analysis = await get_analysis_by_file_id(file_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found for file_id")

    if from_stage and from_stage in [1, 2, 3]:
        # 部分清除：只清除指定阶段及之后的结果
        from database import clear_stage_results_from
        success = await clear_stage_results_from(analysis['id'], from_stage)
        if success:
            return {
                "message": f"Cleared stages {from_stage}+ results",
                "cleared_from_stage": from_stage
            }
    else:
        # 完全删除整个分析
        success = await delete_analysis(analysis['id'])
        if success:
            return {"message": "Deleted successfully"}

    raise HTTPException(status_code=500, detail="Failed to delete analysis")


@app.get("/api/check")
async def check_config():
    """检查后端配置状态"""
    api_key_set = bool(os.getenv("DEEPSEEK_API_KEY"))
    return {
        "api_key_configured": api_key_set,
        "upload_dir": str(UPLOAD_DIR.relative_to(PROJECT_ROOT)),
        "database": "analysis.db",
        "prompts_dir": "prompts/"
    }


# 静态文件服务（前端构建产物）
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
