#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
狼人杀对局分析脚本（DeepSeek API）

默认运行三阶段流水线，降低单次爆 token 风险：
- stage1: 事实抽取
- stage2: 发言与解说整理
- stage3: 意图分析与校验

兼容单阶段：--mode single
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

import requests


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-reasoner"


def read_text(path: Path) -> str:
    """读取文本文件，优先 utf-8，失败时回退 gb18030。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030")


def load_api_key_from_env_file(project_root: Path) -> str:
    """从项目根目录 .env 读取 DEEPSEEK_API_KEY。"""
    env_path = project_root / ".env"
    if not env_path.exists():
        return ""

    text = read_text(env_path)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().replace("\ufeff", "")
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if key == "DEEPSEEK_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def extract_json_text(model_text: str) -> str:
    """从模型输出中尽量提取 JSON。"""
    stripped = (model_text or "").strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    md_match = re.search(r"```json\s*(\{.*\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if md_match:
        return md_match.group(1).strip()

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and last > first:
        return stripped[first : last + 1].strip()

    raise ValueError("无法从模型输出中提取 JSON")


def normalize_json_candidate(text: str) -> str:
    """对近似 JSON 做轻量清洗，尽量转成可解析 JSON。"""
    cleaned = text

    # 统一常见中文/智能引号，避免字符串边界识别失败
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")

    # 去掉非法控制字符（保留 \t \n \r）
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", cleaned)

    # 去掉对象/数组结束前的尾逗号
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    return cleaned


def parse_json_relaxed(model_text: str) -> Dict[str, Any]:
    """先严格解析，失败后走宽松清洗再解析。"""
    candidate = extract_json_text(model_text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = normalize_json_candidate(candidate)
        return json.loads(repaired)


def save_text(path: Path, content: str) -> None:
    path.write_text(content or "", encoding="utf-8")


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def call_deepseek(
    api_key: str,
    model: str,
    prompt_text: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    max_retries: int,
    heartbeat_interval: int,
) -> Dict[str, Any]:
    """调用 DeepSeek，并返回 content/reasoning/usage。"""
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严谨的数据抽取与推理引擎，必须输出合法 JSON。"},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    def heartbeat(stop_event: threading.Event) -> None:
        started = time.time()
        while not stop_event.wait(heartbeat_interval):
            print(f"[INFO] 等待模型响应中... 已等待 {time.time() - started:.0f}s", flush=True)

    last_err: BaseException | None = None
    for idx in range(1, max_retries + 1):
        stop_event = threading.Event()
        t = threading.Thread(target=heartbeat, args=(stop_event,), daemon=True)
        t.start()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        except requests.RequestException as err:
            last_err = err
            if idx < max_retries:
                print(f"[WARN] 第 {idx} 次调用失败，准备重试: {err}", file=sys.stderr)
                time.sleep(idx * 2)
                continue
            raise RuntimeError(f"DeepSeek 调用失败：{err}") from err
        finally:
            stop_event.set()
            t.join(timeout=1)

        try:
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            return {
                "content": message.get("content", ""),
                "reasoning_content": message.get("reasoning_content", ""),
                "usage": data.get("usage", {}),
            }
        except (ValueError, KeyError) as err:
            last_err = err
            if idx < max_retries:
                print(f"[WARN] 第 {idx} 次解析响应失败，准备重试: {err}", file=sys.stderr)
                time.sleep(idx * 2)
                continue
            break

    raise RuntimeError(f"DeepSeek 调用失败：{last_err}")


def repair_json_with_model(
    api_key: str,
    model: str,
    bad_output_text: str,
    timeout_seconds: int,
    max_retries: int,
    heartbeat_interval: int,
) -> str:
    """二次修复：让模型把已有文本重排为纯 JSON。"""
    repair_prompt = (
        "请将下面文本修复并重排为一个合法 JSON 对象。\n"
        "1) 只输出 JSON，不要任何解释。\n"
        "2) 缺失字段可填 null 或 unknown。\n"
        "3) 不要新增无依据事实。\n\n"
        "待修复文本：\n"
        f"{bad_output_text}"
    )
    result = call_deepseek(
        api_key=api_key,
        model=model,
        prompt_text=repair_prompt,
        temperature=0.0,
        max_tokens=8192,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        heartbeat_interval=heartbeat_interval,
    )
    return result.get("content", "")


def fill_template(template: str, mapping: Dict[str, str]) -> str:
    text = template
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def run_one_stage(
    stage_name: str,
    prompt_text: str,
    output_dir: Path,
    stem: str,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    max_retries: int,
    heartbeat_interval: int,
    require_json: bool,
) -> Dict[str, Any] | None:
    """执行单个阶段，返回解析后的 JSON；非严格模式失败返回 None。"""
    print(f"[INFO] 开始阶段: {stage_name}")
    started_at = time.time()
    result = call_deepseek(
        api_key=api_key,
        model=model,
        prompt_text=prompt_text,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        heartbeat_interval=heartbeat_interval,
    )
    elapsed = time.time() - started_at
    print(f"[INFO] 阶段 {stage_name} 调用完成，耗时 {elapsed:.1f}s")
    if result.get("usage"):
        print(f"[INFO] 阶段 {stage_name} usage: {result['usage']}")

    raw_text = result.get("content", "")
    reasoning_text = result.get("reasoning_content", "")
    raw_path = output_dir / f"{stem}.{stage_name}.raw.txt"
    save_text(raw_path, raw_text)
    print(f"[OK] 已保存阶段原始输出: {raw_path}")
    if reasoning_text:
        reasoning_path = output_dir / f"{stem}.{stage_name}.reasoning.txt"
        save_text(reasoning_path, reasoning_text)
        print(f"[OK] 已保存阶段推理输出: {reasoning_path}")

    try:
        parsed = parse_json_relaxed(raw_text)
        json_path = output_dir / f"{stem}.{stage_name}.json"
        save_json(json_path, parsed)
        print(f"[OK] 已保存阶段JSON: {json_path}")
        return parsed
    except (ValueError, json.JSONDecodeError) as err:
        err_path = output_dir / f"{stem}.{stage_name}.failed.error.txt"
        save_text(err_path, f"首次解析失败: {err}")
        print(f"[WARN] 阶段 {stage_name} 首次 JSON 解析失败: {err}")

    print(f"[WARN] 阶段 {stage_name} 尝试自动修复 JSON...")
    repaired_text = repair_json_with_model(
        api_key=api_key,
        model=model,
        bad_output_text=raw_text,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        heartbeat_interval=heartbeat_interval,
    )
    repaired_raw_path = output_dir / f"{stem}.{stage_name}.repaired.raw.txt"
    save_text(repaired_raw_path, repaired_text)
    print(f"[OK] 已保存阶段修复原文: {repaired_raw_path}")

    try:
        repaired = parse_json_relaxed(repaired_text)
        repaired_json_path = output_dir / f"{stem}.{stage_name}.repaired.json"
        save_json(repaired_json_path, repaired)
        print(f"[OK] 已保存阶段修复JSON: {repaired_json_path}")
        return repaired
    except (ValueError, json.JSONDecodeError) as repair_err:
        err2_path = output_dir / f"{stem}.{stage_name}.repair.failed.error.txt"
        save_text(err2_path, f"二次修复失败: {repair_err}")
        print(f"[WARN] 阶段 {stage_name} 二次修复失败: {repair_err}")
        if require_json:
            raise RuntimeError(f"阶段 {stage_name} JSON 失败，且 require_json=True") from repair_err
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="狼人杀对局 DeepSeek 分析脚本")
    parser.add_argument("--mode", choices=["pipeline", "single"], default="pipeline", help="运行模式，默认 pipeline")

    parser.add_argument("--transcript", default="data/京城大师赛260312（机械狼通灵师）.txt", help="单局对局转写 txt 路径")
    parser.add_argument("--format", default="formats/机械狼通灵师版型.txt", help="版型规则 txt 路径")

    parser.add_argument("--prompt", default="prompts/v1_organize_and_intent_prompt.txt", help="single 模式的 prompt 模板")
    parser.add_argument("--stage1-prompt", default="prompts/v1_stage1_facts_prompt.txt", help="pipeline 阶段1 prompt")
    parser.add_argument("--stage2-prompt", default="prompts/v1_stage2_speeches_prompt.txt", help="pipeline 阶段2 prompt")
    parser.add_argument("--stage3-prompt", default="prompts/v1_stage3_intent_prompt.txt", help="pipeline 阶段3 prompt")

    parser.add_argument("--output-dir", default="outputs", help="输出目录")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名，默认 {DEFAULT_MODEL}")
    parser.add_argument("--max-tokens", type=int, default=8192, help="单次请求最大输出 token")
    parser.add_argument("--stage1-max-tokens", type=int, default=8192, help="stage1 最大输出 token")
    parser.add_argument("--stage2-max-tokens", type=int, default=12288, help="stage2 最大输出 token")
    parser.add_argument("--stage3-max-tokens", type=int, default=8192, help="stage3 最大输出 token")
    parser.add_argument("--temperature", type=float, default=0.0, help="采样温度")
    parser.add_argument("--timeout-seconds", type=int, default=360, help="单次请求超时秒数")
    parser.add_argument("--heartbeat-interval", type=int, default=5, help="进度打印间隔秒")
    parser.add_argument("--max-retries", type=int, default=3, help="请求重试次数")
    parser.add_argument("--require-json", action="store_true", help="严格模式：任一阶段 JSON 失败即报错")
    parser.add_argument("--game-name", default="werewolf_game", help="输出文件名前缀")
    return parser.parse_args()


def load_template(path: Path) -> str:
    text = read_text(path)
    if not text.strip():
        raise ValueError(f"模板为空: {path}")
    return text


def main() -> None:
    args = parse_args()

    project_root = Path.cwd()
    env_path = project_root / ".env"

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or load_api_key_from_env_file(project_root)
    if not api_key:
        raise EnvironmentError(
            "未检测到 DEEPSEEK_API_KEY。\n"
            f"已检查环境变量与文件: {env_path}\n"
            "请在 .env 中写入: DEEPSEEK_API_KEY=你的APIKey"
        )

    transcript_path = Path(args.transcript)
    format_path = Path(args.format)
    output_dir = Path(args.output_dir)
    ensure_output_dir(output_dir)

    for p in [transcript_path, format_path]:
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")

    print("[INFO] 读取输入文件...")
    transcript_text = read_text(transcript_path)
    format_rules_text = read_text(format_path)

    stem = f"{args.game_name}_{int(time.time())}"

    if args.mode == "single":
        prompt_path = Path(args.prompt)
        if not prompt_path.exists():
            raise FileNotFoundError(f"文件不存在: {prompt_path}")

        print("[INFO] single 模式：构建提示词...")
        tpl = load_template(prompt_path)
        if "{{FORMAT_RULES}}" not in tpl or "{{RAW_TRANSCRIPT}}" not in tpl:
            raise ValueError("single 模板缺少 {{FORMAT_RULES}} 或 {{RAW_TRANSCRIPT}}")
        prompt_text = fill_template(
            tpl,
            {
                "{{FORMAT_RULES}}": format_rules_text.strip(),
                "{{RAW_TRANSCRIPT}}": transcript_text.strip(),
            },
        )

        parsed = run_one_stage(
            stage_name="single",
            prompt_text=prompt_text,
            output_dir=output_dir,
            stem=stem,
            api_key=api_key,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            heartbeat_interval=args.heartbeat_interval,
            require_json=args.require_json,
        )
        if parsed is not None:
            final_path = output_dir / f"{stem}.json"
            save_json(final_path, parsed)
            print(f"[OK] single 最终JSON: {final_path}")
        print("[DONE] 完成")
        return

    # pipeline mode
    for p in [Path(args.stage1_prompt), Path(args.stage2_prompt), Path(args.stage3_prompt)]:
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")

    print("[INFO] pipeline 模式：stage1 事实抽取")
    stage1_tpl = load_template(Path(args.stage1_prompt))
    stage1_prompt = fill_template(
        stage1_tpl,
        {
            "{{FORMAT_RULES}}": format_rules_text.strip(),
            "{{RAW_TRANSCRIPT}}": transcript_text.strip(),
        },
    )
    stage1 = run_one_stage(
        stage_name="stage1",
        prompt_text=stage1_prompt,
        output_dir=output_dir,
        stem=stem,
        api_key=api_key,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.stage1_max_tokens,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        heartbeat_interval=args.heartbeat_interval,
        require_json=args.require_json,
    )

    print("[INFO] pipeline 模式：stage2 发言与解说整理")
    stage2_tpl = load_template(Path(args.stage2_prompt))
    stage2_prompt = fill_template(
        stage2_tpl,
        {
            "{{FORMAT_RULES}}": format_rules_text.strip(),
            "{{RAW_TRANSCRIPT}}": transcript_text.strip(),
        },
    )
    stage2 = run_one_stage(
        stage_name="stage2",
        prompt_text=stage2_prompt,
        output_dir=output_dir,
        stem=stem,
        api_key=api_key,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.stage2_max_tokens,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        heartbeat_interval=args.heartbeat_interval,
        require_json=args.require_json,
    )

    if stage1 is None or stage2 is None:
        msg = "stage1/stage2 未产出可用 JSON，无法继续 stage3。"
        if args.require_json:
            raise RuntimeError(msg)
        print(f"[WARN] {msg} 已结束（非严格模式）")
        return

    print("[INFO] pipeline 模式：stage3 意图分析")
    stage3_tpl = load_template(Path(args.stage3_prompt))
    stage3_prompt = fill_template(
        stage3_tpl,
        {
            "{{STAGE1_JSON}}": json.dumps(stage1, ensure_ascii=False),
            "{{STAGE2_JSON}}": json.dumps(stage2, ensure_ascii=False),
        },
    )
    stage3 = run_one_stage(
        stage_name="stage3",
        prompt_text=stage3_prompt,
        output_dir=output_dir,
        stem=stem,
        api_key=api_key,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.stage3_max_tokens,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        heartbeat_interval=args.heartbeat_interval,
        require_json=args.require_json,
    )

    if stage3 is None:
        msg = "stage3 未产出可用 JSON。"
        if args.require_json:
            raise RuntimeError(msg)
        print(f"[WARN] {msg} 已结束（非严格模式）")
        return

    merged: Dict[str, Any] = {}
    merged.update(stage1)
    merged.update(stage2)
    merged.update(stage3)
    merged["pipeline_meta"] = {
        "mode": "pipeline",
        "model": args.model,
        "created_at": int(time.time()),
        "source_files": {
            "transcript": str(transcript_path),
            "format": str(format_path),
            "stage1_prompt": args.stage1_prompt,
            "stage2_prompt": args.stage2_prompt,
            "stage3_prompt": args.stage3_prompt,
        },
    }

    merged_path = output_dir / f"{stem}.pipeline.json"
    save_json(merged_path, merged)
    print(f"[OK] pipeline 最终JSON: {merged_path}")
    print("[DONE] 完成")


if __name__ == "__main__":
    main()
