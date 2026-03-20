"""
SQLite database for persisting analysis results
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

DATABASE_PATH = Path(__file__).parent / "analysis.db"


async def init_db():
    """Initialize database tables"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 先创建基础表（如果不存在）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                game_name TEXT NOT NULL,
                format_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                stage1_result TEXT,
                stage2_result TEXT,
                stage3_result TEXT,
                pipeline_result TEXT
            )
        """)

        # 检查并添加缺失的列
        cursor = await db.execute("PRAGMA table_info(analyses)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        # 添加 label 列（如果不存在）
        if "label" not in column_names:
            try:
                await db.execute("ALTER TABLE analyses ADD COLUMN label TEXT")
                print("[DB] Added label column")
            except Exception as e:
                print(f"[DB] Error adding label column: {e}")

        # 添加 file_id 列（如果不存在）
        if "file_id" not in column_names:
            try:
                await db.execute("ALTER TABLE analyses ADD COLUMN file_id TEXT")
                print("[DB] Added file_id column")
            except Exception as e:
                print(f"[DB] Error adding file_id column: {e}")

        # 添加 stage1_meta 列（存储day_boundaries等元数据，用于Stage 2分批处理）
        if "stage1_meta" not in column_names:
            try:
                await db.execute("ALTER TABLE analyses ADD COLUMN stage1_meta TEXT")
                print("[DB] Added stage1_meta column")
            except Exception as e:
                print(f"[DB] Error adding stage1_meta column: {e}")

        # 创建索引
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_file_id ON analyses(file_id)")
        except Exception as e:
            print(f"[DB] Error creating index: {e}")

        # 创建 day_segments 表（对局分段信息）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS day_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                segment_type TEXT NOT NULL,
                name TEXT,
                start_anchor TEXT,
                end_anchor TEXT,
                contains_commentary BOOLEAN DEFAULT 0,
                for_stage2 BOOLEAN DEFAULT 1,
                start_pos INTEGER,
                end_pos INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 创建 speeches 表（发言内容）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS speeches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                round TEXT,
                speech_order INTEGER,
                speaker_id TEXT NOT NULL,
                text_summary TEXT,
                text_full TEXT,
                claims_json TEXT,
                stance_json TEXT,
                intent_tags_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 创建 votes 表（票型）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                vote_type TEXT,
                voter_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 创建索引
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_segments_analysis ON day_segments(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_segments_day ON day_segments(analysis_id, day)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_speeches_analysis ON speeches(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_speeches_day ON speeches(analysis_id, day)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_speeches_speaker ON speeches(analysis_id, speaker_id, day)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_votes_analysis ON votes(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_votes_day ON votes(analysis_id, day, vote_type)")
        except Exception as e:
            print(f"[DB] Error creating index: {e}")

        # ═══════════════════════════════════════════════════════════════════════════
        # 【新增】RAG支持表 - Stage 3逐日推理链
        # ═══════════════════════════════════════════════════════════════════════════

        # 推理链表 - 记录每个玩家每天的推断过程
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inference_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                observer_id TEXT NOT NULL,           -- 推理者（玩家ID）
                observer_role TEXT,                   -- 推理者真实身份
                day INTEGER NOT NULL,                 -- 第几天
                target_id TEXT NOT NULL,              -- 被推理的玩家
                conclusion_type TEXT,                 -- identity/intent/relationship
                conclusion TEXT,                      -- 结论内容
                confidence REAL,                      -- 置信度 0-1
                reasoning TEXT,                       -- 推理过程
                evidence_ids TEXT,                    -- JSON: 证据ID列表
                key_clues TEXT,                       -- JSON: 关键线索
                previous_conclusion TEXT,             -- 之前的结论（用于追踪变化）
                change_reason TEXT,                   -- 为什么改变看法
                is_correct BOOLEAN,                   -- 是否正确（事后验证）
                truth TEXT,                           -- 真实身份
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 时间线事件表 - 记录对局关键事件
        await db.execute("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                day INTEGER NOT NULL,                 -- 第几天
                phase TEXT,                           -- night/day/vote
                event_type TEXT,                      -- speech/vote/death/badge_transfer
                event_id TEXT,                        -- 关联ID
                content TEXT,                         -- 事件内容摘要
                is_public BOOLEAN DEFAULT 1,          -- 是否公开可见
                visible_to TEXT,                      -- JSON: 可见玩家列表
                importance_score REAL DEFAULT 0.5,    -- 重要性评分
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 操作策略表 - 记录每个玩家的操作及评价
        await db.execute("""
            CREATE TABLE IF NOT EXISTS operation_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                player_id TEXT NOT NULL,              -- 操作者
                player_role TEXT,                     -- 真实身份
                operation_type TEXT,                  -- vote/speech/kill/save/check
                day INTEGER NOT NULL,
                operation_detail TEXT,                -- 操作详情
                effectiveness_score REAL,             -- 有效性评分
                skill_level TEXT,                     -- beginner/intermediate/advanced/expert
                good_points TEXT,                     -- 做得好的地方
                bad_points TEXT,                      -- 可以改进的地方
                alternative_actions TEXT,             -- 其他可能的选择
                lesson_learned TEXT,                  -- 教学价值
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 知识片段表 - 用于RAG检索
        await db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                chunk_type TEXT,                      -- strategy/mistake/insight/relationship
                content TEXT NOT NULL,                -- 自然语言描述
                embedding TEXT,                       -- 向量嵌入（预留）
                game_context TEXT,                    -- 对局背景
                related_players TEXT,                 -- JSON: 涉及玩家
                related_events TEXT,                  -- JSON: 相关事件ID
                importance_score REAL DEFAULT 0.5,    -- 重要性
                tags TEXT,                            -- JSON: 标签列表
                created_at TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        """)

        # 为新增表创建索引
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_inference_analysis ON inference_chains(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_inference_observer ON inference_chains(analysis_id, observer_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_inference_target ON inference_chains(analysis_id, target_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_inference_day ON inference_chains(analysis_id, day)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_analysis ON timeline_events(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_day ON timeline_events(analysis_id, day)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_operation_analysis ON operation_strategies(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_operation_player ON operation_strategies(analysis_id, player_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_analysis ON knowledge_chunks(analysis_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_chunks(chunk_type)")
        except Exception as e:
            print(f"[DB] Error creating RAG table indexes: {e}")

        await db.commit()
        print("[DB] Database initialized with RAG support")


async def save_analysis(
    game_name: str,
    format_name: str,
    stage1: Optional[dict] = None,
    stage2: Optional[dict] = None,
    stage3: Optional[dict] = None,
    pipeline: Optional[dict] = None,
    analysis_id: Optional[str] = None,
    label: Optional[str] = None,
    file_id: Optional[str] = None,
    stage1_meta: Optional[dict] = None
) -> str:
    """Save or update analysis result"""
    if analysis_id is None:
        analysis_id = str(uuid.uuid4())[:8]

    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 检查列是否存在
        cursor = await db.execute("PRAGMA table_info(analyses)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        has_label = "label" in column_names
        has_file_id = "file_id" in column_names
        has_stage1_meta = "stage1_meta" in column_names

        # Check if exists
        cursor = await db.execute(
            "SELECT id FROM analyses WHERE id = ?",
            (analysis_id,)
        )
        exists = await cursor.fetchone()

        if exists:
            # Update - 动态构建SQL，只更新存在的列
            update_fields = [
                "stage1_result = COALESCE(?, stage1_result)",
                "stage2_result = COALESCE(?, stage2_result)",
                "stage3_result = COALESCE(?, stage3_result)",
                "pipeline_result = COALESCE(?, pipeline_result)",
                "updated_at = ?"
            ]
            params = [
                json.dumps(stage1, ensure_ascii=False) if stage1 else None,
                json.dumps(stage2, ensure_ascii=False) if stage2 else None,
                json.dumps(stage3, ensure_ascii=False) if stage3 else None,
                json.dumps(pipeline, ensure_ascii=False) if pipeline else None,
                now
            ]

            if has_label:
                update_fields.append("label = COALESCE(?, label)")
                params.append(label)
            if has_file_id:
                update_fields.append("file_id = COALESCE(?, file_id)")
                params.append(file_id)
            if has_stage1_meta:
                update_fields.append("stage1_meta = COALESCE(?, stage1_meta)")
                params.append(json.dumps(stage1_meta, ensure_ascii=False) if stage1_meta else None)

            params.append(analysis_id)

            sql = f"UPDATE analyses SET {', '.join(update_fields)} WHERE id = ?"
            await db.execute(sql, params)
        else:
            # Insert - 动态构建SQL，只插入存在的列
            insert_columns = ["id", "game_name", "format_name", "created_at", "updated_at",
                             "stage1_result", "stage2_result", "stage3_result", "pipeline_result"]
            insert_values = ["?"] * len(insert_columns)
            params = [
                analysis_id, game_name, format_name, now, now,
                json.dumps(stage1, ensure_ascii=False) if stage1 else None,
                json.dumps(stage2, ensure_ascii=False) if stage2 else None,
                json.dumps(stage3, ensure_ascii=False) if stage3 else None,
                json.dumps(pipeline, ensure_ascii=False) if pipeline else None
            ]

            if has_label:
                insert_columns.append("label")
                insert_values.append("?")
                params.append(label)
            if has_file_id:
                insert_columns.append("file_id")
                insert_values.append("?")
                params.append(file_id)
            if has_stage1_meta:
                insert_columns.append("stage1_meta")
                insert_values.append("?")
                params.append(json.dumps(stage1_meta, ensure_ascii=False) if stage1_meta else None)

            sql = f"INSERT INTO analyses ({', '.join(insert_columns)}) VALUES ({', '.join(insert_values)})"
            await db.execute(sql, params)

        await db.commit()

    return analysis_id


async def get_analysis(analysis_id: str) -> Optional[dict]:
    """Get analysis by ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (analysis_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['stage1_result', 'stage2_result', 'stage3_result', 'pipeline_result', 'stage1_meta']:
            if result.get(field):
                result[field] = json.loads(result[field])

        return result


async def get_analysis_by_file_id(file_id: str) -> Optional[dict]:
    """Get analysis by file_id (latest first)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM analyses WHERE file_id = ? ORDER BY created_at DESC LIMIT 1",
            (file_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['stage1_result', 'stage2_result', 'stage3_result', 'pipeline_result']:
            if result.get(field):
                result[field] = json.loads(result[field])

        return result


async def get_analysis_by_label(label: str) -> Optional[dict]:
    """Get analysis by label"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM analyses WHERE label = ?",
            (label,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['stage1_result', 'stage2_result', 'stage3_result', 'pipeline_result']:
            if result.get(field):
                result[field] = json.loads(result[field])

        return result


async def list_analyses(limit: int = 50) -> List[dict]:
    """List all analyses, newest first"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT id, label, game_name, format_name, created_at, updated_at FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def delete_analysis(analysis_id: str) -> bool:
    """Delete analysis by ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM analyses WHERE id = ?",
            (analysis_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_stage_results_from(analysis_id: str, from_stage: int) -> bool:
    """清除从指定阶段开始及之后的所有阶段结果

    Args:
        analysis_id: 分析记录ID
        from_stage: 从哪个阶段开始清除（1-3），包含该阶段

    Returns:
        是否成功清除
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        fields_to_clear = []
        if from_stage <= 1:
            fields_to_clear.extend(["stage1_result", "stage1_meta"])
        if from_stage <= 2:
            fields_to_clear.extend(["stage2_result", "stage2_meta"])
        if from_stage <= 3:
            fields_to_clear.extend(["stage3_result", "stage3_meta"])

        if not fields_to_clear:
            return True

        set_clause = ", ".join([f"{field} = NULL" for field in fields_to_clear])

        cursor = await db.execute(
            f"""UPDATE analyses
                SET {set_clause},
                    updated_at = ?
                WHERE id = ?""",
            (datetime.now().isoformat(), analysis_id)
        )
        await db.commit()

        print(f"[DB] Cleared stages {from_stage}+ results for analysis {analysis_id}")
        return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════════════════════════
# Day Segments 相关操作
# ═══════════════════════════════════════════════════════════════════════════

async def save_day_segments(analysis_id: str, segments: List[dict]):
    """保存对局分段信息到数据库

    Args:
        analysis_id: 分析记录ID
        segments: Stage 1 输出的分段列表
    """
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 先删除该分析记录已有的分段
        await db.execute("DELETE FROM day_segments WHERE analysis_id = ?", (analysis_id,))

        # 批量插入新分段
        for seg in segments:
            await db.execute("""
                INSERT INTO day_segments
                (analysis_id, day, segment_type, name, start_anchor, end_anchor,
                 contains_commentary, for_stage2, start_pos, end_pos, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                seg.get("day", 0),
                seg.get("type", ""),
                seg.get("name", ""),
                seg.get("start_anchor", ""),
                seg.get("end_anchor", ""),
                1 if seg.get("contains_commentary") else 0,
                1 if seg.get("for_stage2", True) else 0,
                seg.get("start_pos"),
                seg.get("end_pos"),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(segments)} day_segments for analysis {analysis_id}")


async def get_day_segments(analysis_id: str) -> List[dict]:
    """获取某分析的所有分段，按天数排序"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT * FROM day_segments
            WHERE analysis_id = ?
            ORDER BY day
        """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        segments = []
        for row in rows:
            seg = dict(zip(columns, row))
            # 转换布尔值
            seg["contains_commentary"] = bool(seg.get("contains_commentary"))
            seg["for_stage2"] = bool(seg.get("for_stage2"))
            segments.append(seg)

        return segments


async def get_day_segment_by_day(analysis_id: str, day: int) -> Optional[dict]:
    """获取某天的分段信息"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT * FROM day_segments
            WHERE analysis_id = ? AND day = ?
        """, (analysis_id, day))

        row = await cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        seg = dict(zip(columns, row))
        seg["contains_commentary"] = bool(seg.get("contains_commentary"))
        seg["for_stage2"] = bool(seg.get("for_stage2"))
        return seg


# ═══════════════════════════════════════════════════════════════════════════
# Speeches 相关操作
# ═══════════════════════════════════════════════════════════════════════════

async def save_speeches(analysis_id: str, speeches: List[dict]):
    """保存发言内容到数据库

    Args:
        analysis_id: 分析记录ID
        speeches: Stage 2 输出的发言列表
    """
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 先删除该分析记录已有的发言（避免重复）
        await db.execute("DELETE FROM speeches WHERE analysis_id = ?", (analysis_id,))

        # 批量插入新发言
        for speech in speeches:
            await db.execute("""
                INSERT INTO speeches
                (analysis_id, day, round, speech_order, speaker_id,
                 text_summary, text_full, claims_json, stance_json, intent_tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                speech.get("day", 0),
                speech.get("round", ""),
                speech.get("speech_order", 0),
                str(speech.get("speaker", "")),
                speech.get("text_summary", ""),
                speech.get("text_full", ""),
                json.dumps(speech.get("claims", []), ensure_ascii=False),
                json.dumps(speech.get("stance", {}), ensure_ascii=False),
                json.dumps(speech.get("intent_tags", []), ensure_ascii=False),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(speeches)} speeches for analysis {analysis_id}")


async def get_speeches_by_analysis(analysis_id: str) -> List[dict]:
    """获取某分析的所有发言，按天和发言顺序排序"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT * FROM speeches
            WHERE analysis_id = ?
            ORDER BY day, speech_order
        """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        speeches = []
        for row in rows:
            speech = dict(zip(columns, row))
            # 解析 JSON 字段
            for field in ['claims_json', 'stance_json', 'intent_tags_json']:
                if speech.get(field):
                    try:
                        speech[field.replace('_json', '')] = json.loads(speech[field])
                    except:
                        speech[field.replace('_json', '')] = []
                    del speech[field]
            speeches.append(speech)

        return speeches


async def get_speeches_by_player(analysis_id: str, player_id: str, max_day: int = None) -> List[dict]:
    """获取某玩家的所有发言（可限制到第几天）"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if max_day is not None:
            cursor = await db.execute("""
                SELECT * FROM speeches
                WHERE analysis_id = ? AND speaker_id = ? AND day <= ?
                ORDER BY day, speech_order
            """, (analysis_id, str(player_id), max_day))
        else:
            cursor = await db.execute("""
                SELECT * FROM speeches
                WHERE analysis_id = ? AND speaker_id = ?
                ORDER BY day, speech_order
            """, (analysis_id, str(player_id)))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        speeches = []
        for row in rows:
            speech = dict(zip(columns, row))
            for field in ['claims_json', 'stance_json', 'intent_tags_json']:
                if speech.get(field):
                    try:
                        speech[field.replace('_json', '')] = json.loads(speech[field])
                    except:
                        speech[field.replace('_json', '')] = []
                    del speech[field]
            speeches.append(speech)

        return speeches


# ═══════════════════════════════════════════════════════════════════════════
# Votes 相关操作
# ═══════════════════════════════════════════════════════════════════════════

async def save_votes(analysis_id: str, votes: List[dict]):
    """保存票型到数据库

    Args:
        analysis_id: 分析记录ID
        votes: 票型列表，每项包含 day, vote_type, voter_id, target_id
    """
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 先删除该分析记录已有的票型
        await db.execute("DELETE FROM votes WHERE analysis_id = ?", (analysis_id,))

        # 批量插入新票型
        for vote in votes:
            await db.execute("""
                INSERT INTO votes
                (analysis_id, day, vote_type, voter_id, target_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                vote.get("day", 0),
                vote.get("vote_type", ""),
                str(vote.get("voter_id", "")),
                str(vote.get("target_id", "")),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(votes)} votes for analysis {analysis_id}")


async def get_votes_by_analysis(analysis_id: str) -> List[dict]:
    """获取某分析的所有票型，按天排序"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT * FROM votes
            WHERE analysis_id = ?
            ORDER BY day, vote_type
        """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def get_votes_by_day(analysis_id: str, day: int, vote_type: str = None) -> List[dict]:
    """获取某天的票型"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if vote_type:
            cursor = await db.execute("""
                SELECT * FROM votes
                WHERE analysis_id = ? AND day = ? AND vote_type = ?
            """, (analysis_id, day, vote_type))
        else:
            cursor = await db.execute("""
                SELECT * FROM votes
                WHERE analysis_id = ? AND day = ?
            """, (analysis_id, day))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════
# RAG 支持表 - Stage 3 逐日推理链操作
# ═══════════════════════════════════════════════════════════════════════════

async def save_inference_chains(analysis_id: str, inference_chains: List[dict]):
    """保存推理链到数据库

    Args:
        analysis_id: 分析记录ID
        inference_chains: 推理链列表
    """
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 先删除该分析记录已有的推理链
        await db.execute("DELETE FROM inference_chains WHERE analysis_id = ?", (analysis_id,))

        # 批量插入新推理链
        for chain in inference_chains:
            await db.execute("""
                INSERT INTO inference_chains
                (analysis_id, observer_id, observer_role, day, target_id,
                 conclusion_type, conclusion, confidence, reasoning,
                 evidence_ids, key_clues, previous_conclusion, change_reason,
                 is_correct, truth, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                str(chain.get("observer_id", "")),
                chain.get("observer_role", ""),
                chain.get("day", 0),
                str(chain.get("target_id", "")),
                chain.get("conclusion_type", "identity"),
                chain.get("conclusion", ""),
                chain.get("confidence", 0.5),
                chain.get("reasoning", ""),
                json.dumps(chain.get("evidence_ids", []), ensure_ascii=False),
                json.dumps(chain.get("key_clues", []), ensure_ascii=False),
                chain.get("previous_conclusion", ""),
                chain.get("change_reason", ""),
                chain.get("is_correct"),
                chain.get("truth", ""),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(inference_chains)} inference chains for analysis {analysis_id}")


async def get_inference_chains(analysis_id: str, observer_id: str = None, day: int = None) -> List[dict]:
    """获取推理链

    Args:
        analysis_id: 分析记录ID
        observer_id: 可选，过滤特定推理者
        day: 可选，过滤特定天数
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        params = [analysis_id]
        sql = "SELECT * FROM inference_chains WHERE analysis_id = ?"

        if observer_id:
            sql += " AND observer_id = ?"
            params.append(observer_id)
        if day:
            sql += " AND day = ?"
            params.append(day)

        sql += " ORDER BY day, observer_id"

        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        chains = []
        for row in rows:
            chain = dict(zip(columns, row))
            # 解析 JSON 字段
            for field in ['evidence_ids', 'key_clues']:
                if chain.get(field):
                    try:
                        chain[field] = json.loads(chain[field])
                    except:
                        chain[field] = []
            chains.append(chain)

        return chains


async def save_timeline_events(analysis_id: str, events: List[dict]):
    """保存时间线事件"""
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM timeline_events WHERE analysis_id = ?", (analysis_id,))

        for event in events:
            await db.execute("""
                INSERT INTO timeline_events
                (analysis_id, day, phase, event_type, event_id, content,
                 is_public, visible_to, importance_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                event.get("day", 0),
                event.get("phase", ""),
                event.get("event_type", ""),
                event.get("event_id", ""),
                event.get("content", ""),
                1 if event.get("is_public", True) else 0,
                json.dumps(event.get("visible_to", []), ensure_ascii=False),
                event.get("importance_score", 0.5),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(events)} timeline events for analysis {analysis_id}")


async def get_timeline_events(analysis_id: str, day: int = None) -> List[dict]:
    """获取时间线事件"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if day:
            cursor = await db.execute("""
                SELECT * FROM timeline_events
                WHERE analysis_id = ? AND day = ?
                ORDER BY day, id
            """, (analysis_id, day))
        else:
            cursor = await db.execute("""
                SELECT * FROM timeline_events
                WHERE analysis_id = ?
                ORDER BY day, id
            """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        events = []
        for row in rows:
            event = dict(zip(columns, row))
            event["is_public"] = bool(event.get("is_public"))
            if event.get("visible_to"):
                try:
                    event["visible_to"] = json.loads(event["visible_to"])
                except:
                    event["visible_to"] = []
            events.append(event)

        return events


async def save_operation_strategies(analysis_id: str, strategies: List[dict]):
    """保存操作策略及评价"""
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM operation_strategies WHERE analysis_id = ?", (analysis_id,))

        for strategy in strategies:
            await db.execute("""
                INSERT INTO operation_strategies
                (analysis_id, player_id, player_role, operation_type, day,
                 operation_detail, effectiveness_score, skill_level,
                 good_points, bad_points, alternative_actions, lesson_learned, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                str(strategy.get("player_id", "")),
                strategy.get("player_role", ""),
                strategy.get("operation_type", ""),
                strategy.get("day", 0),
                strategy.get("operation_detail", ""),
                strategy.get("effectiveness_score"),
                strategy.get("skill_level", ""),
                strategy.get("good_points", ""),
                strategy.get("bad_points", ""),
                strategy.get("alternative_actions", ""),
                strategy.get("lesson_learned", ""),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(strategies)} operation strategies for analysis {analysis_id}")


async def get_operation_strategies(analysis_id: str, player_id: str = None) -> List[dict]:
    """获取操作策略"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if player_id:
            cursor = await db.execute("""
                SELECT * FROM operation_strategies
                WHERE analysis_id = ? AND player_id = ?
                ORDER BY day, id
            """, (analysis_id, str(player_id)))
        else:
            cursor = await db.execute("""
                SELECT * FROM operation_strategies
                WHERE analysis_id = ?
                ORDER BY day, id
            """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]


async def save_knowledge_chunks(analysis_id: str, chunks: List[dict]):
    """保存知识片段用于RAG"""
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM knowledge_chunks WHERE analysis_id = ?", (analysis_id,))

        for chunk in chunks:
            await db.execute("""
                INSERT INTO knowledge_chunks
                (analysis_id, chunk_type, content, embedding, game_context,
                 related_players, related_events, importance_score, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                chunk.get("chunk_type", ""),
                chunk.get("content", ""),
                chunk.get("embedding"),  # 预留向量字段
                chunk.get("game_context", ""),
                json.dumps(chunk.get("related_players", []), ensure_ascii=False),
                json.dumps(chunk.get("related_events", []), ensure_ascii=False),
                chunk.get("importance_score", 0.5),
                json.dumps(chunk.get("tags", []), ensure_ascii=False),
                now
            ))

        await db.commit()
        print(f"[DB] Saved {len(chunks)} knowledge chunks for analysis {analysis_id}")


async def get_knowledge_chunks(analysis_id: str, chunk_type: str = None) -> List[dict]:
    """获取知识片段"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if chunk_type:
            cursor = await db.execute("""
                SELECT * FROM knowledge_chunks
                WHERE analysis_id = ? AND chunk_type = ?
                ORDER BY importance_score DESC
            """, (analysis_id, chunk_type))
        else:
            cursor = await db.execute("""
                SELECT * FROM knowledge_chunks
                WHERE analysis_id = ?
                ORDER BY importance_score DESC
            """, (analysis_id,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        chunks = []
        for row in rows:
            chunk = dict(zip(columns, row))
            for field in ['related_players', 'related_events', 'tags']:
                if chunk.get(field):
                    try:
                        chunk[field] = json.loads(chunk[field])
                    except:
                        chunk[field] = []
            chunks.append(chunk)

        return chunks
