"""
Pydantic models for API and database
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    ERROR = "error"


class PlayerInference(BaseModel):
    """Real-time player inference from Stage 3"""
    player_id: str
    day: int
    role_guess: str
    wolf_probability: float
    good_probability: float
    specific_role_guess: Optional[str] = None
    reason: str
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.now)


class StageProgress(BaseModel):
    """Progress of a single stage"""
    stage: int
    status: StageStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: int = 0  # 0-100
    current_action: str = ""  # 如 "分析玩家7/12..."


class AnalysisTask(BaseModel):
    """Main analysis task"""
    id: str
    game_name: str
    format_name: str
    status: AnalysisStatus
    stages: Dict[int, StageProgress] = {}
    reasoning_log: List[Dict[str, Any]] = []  # 实时思考内容
    player_inferences: Dict[str, List[PlayerInference]] = {}  # 玩家推断历史
    results: Dict[str, Any] = {}  # 各阶段完整结果
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str  # stage_start, stage_complete, reasoning, player_update, progress, error
    task_id: str
    data: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)


# Database models (simplified for SQLite)
class SavedAnalysis(BaseModel):
    """Saved analysis result"""
    id: str
    game_name: str
    format_name: str
    created_at: datetime
    stage1_result: Optional[Dict] = None
    stage2_result: Optional[Dict] = None
    stage3_result: Optional[Dict] = None
    pipeline_result: Optional[Dict] = None


class FormatInfo(BaseModel):
    """Game format information"""
    name: str
    file_path: str
    description: str = ""
