"""
SunChat Backend - Configuration Management
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# 项目根目录（backend/）：基于本文件定位，消除对 CWD 的依赖
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


class Settings(BaseSettings):
    """应用配置"""

    # Ollama 配置
    LLM_API_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"
    LLM_TIMEOUT: int = 300  # LLM 请求超时（秒），本地生成较慢
    LLM_LIGHT_TIMEOUT: int = 20  # R-006: 路由/提取等轻量 LLM 调用短超时,失败快速回退
    HEALTH_AVAIL_TTL: int = 30  # R-006: /health LLM 探活结果缓存秒数（同 R-003 DDG 模式）

    # 嵌入模型配置（bge-m3: 中文语义优于 nomic-embed-text, 决策 D-001;切换后需重建向量库）
    EMBEDDING_API_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "bge-m3"

    # 模型管理配置
    MODEL_CONFIG_PATH: str = str(DATA_DIR / "model_config.json")  # 运行时模型选择持久化（绝对路径）
    MODEL_CACHE_TTL: int = 30  # 可用模型列表缓存秒数

    # 数据库配置（绝对路径，消除 CWD 依赖）
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'sunchat.db'}"
    CHROMA_PERSIST_DIR: str = str(DATA_DIR / "chroma")
    UPLOAD_DIR: str = str(UPLOAD_DIR)  # 知识库上传落盘目录
    CHAT_IMAGE_DIR: str = str(DATA_DIR / "uploads" / "chat")  # R-008: 对话图片落盘目录

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    PUBLIC_PORT: int = 0  # R-014: 二维码展示端口(反代/换端口场景覆盖;0=取 APP_PORT)
    FRONTEND_DIST: str = ""  # R-014: SPA 静态目录覆盖(空=自动探测 ../frontend/dist)
    DEBUG: bool = True

    # 单用户本地模式：统一用户标识（全项目引用，避免散落硬编码 user_id=1）
    LOCAL_USER_ID: int = 1

    # CORS 白名单（逗号分隔）；本地优先，默认只放行本地前端端口
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    # 上传约束
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt,md"
    MAX_UPLOAD_MB: int = 20
    CHAT_IMAGE_MAX_MB: int = 8  # R-008: 对话单图上传上限
    CHAT_IMAGE_MAX_PER_MSG: int = 4  # R-008: 单条消息附图上限
    CHAT_IMAGE_WINDOW_MSGS: int = 3  # R-008: 历史注入窗口（最近N条带图消息）
    CHAT_IMAGE_TOTAL_MAX: int = 8  # R-008: 单请求总图上限（控token/显存）

    # 语音输入约束（R-009）
    WHISPER_MODEL_SIZE: str = "base"  # tiny/base/small；环境变量 WHISPER_MODEL_SIZE 可调
    WHISPER_MODEL_DIR: str = str(DATA_DIR / "whisper-models")  # 模型预置目录（运行期禁下载）
    SPEECH_MAX_MB: int = 20  # 录音上传上限

    # 视频输入约束（R-010）
    VIDEO_MAX_MB: int = 50  # 视频上传上限
    VIDEO_MAX_FRAMES: int = 4  # 均匀抽帧数（与单消息图片上限对齐）

    # 姿态分析约束（R-017）
    POSE_MODEL_PATH: str = str(DATA_DIR / "pose-models" / "pose_landmarker_lite.task")
    POSE_SAMPLE_FPS: float = 20.0        # 采样帧率（步态周期≈0.7s,20fps 足够）
    POSE_MAX_SAMPLE_FRAMES: int = 600    # 段内密采帧上限,超限自动加大步距（R-2 缓解;R-017v2 400→600）
    POSE_MIN_CONF: float = 0.5           # 关键点置信度均值门槛（FR-3）
    POSE_MIN_CYCLES: int = 2             # 可切分步态周期数门槛
    POSE_MIN_BODY_RATIO: float = 0.12    # 人体包围盒高/画面高 门槛
    POSE_REPORT_TIMEOUT: int = 120       # 报告 VL 调用超时秒（独立于 LLM_*）
    # R-017 v2:真实帧率/关键段/密采/配速（design-change r2, analysis A-1~A-4）
    POSE_COARSE_FPS: float = 5.0         # 粗扫帧率（定位跑动段,FR-9;R-7 漏检则升8）
    POSE_DENSE_FPS: float = 25.0         # 段内密采帧率（FR-10;180spm 时 stance≥3帧）
    POSE_MAX_SEGMENT_SEC: float = 8.0    # 参与分析的最强跑动段总时长上限
    POSE_ACTIVITY_MIN_SEC: float = 1.5   # 有效跑动段最短时长,不足拒析 no_activity
    POSE_RUN_MIN_CAD: float = 125.0      # 窗口判"跑"的步频下限(步/分;走路≈100-120)
    POSE_USER_HEIGHT_CM: float = 0.0     # 身高(米/像素自标定算配速用;0=不输出配速 FR-11)
    POSE_SLO_RESTORE: bool = True        # 慢动作倍速还原(FR-8)

    # 搜索配置
    SEARCH_DUCKDUCKGO_API: str = ""  # 可选，留空使用无 Key 版本
    SEARCH_TIMEOUT: int = 10  # 搜索超时（秒）

    # 对话流程配置
    CHAT_HISTORY_MESSAGES: int = 6   # 多轮上下文携带的最近消息条数
    MEMORY_ROUTER_LLM_FALLBACK: bool = True  # 规则未命中且输入较长时才用 LLM 兜底分析
    MEMORY_ROUTER_LLM_MIN_LEN: int = 12  # 低于此长度的输入直接信任规则（问候语等 0 LLM）

    # 记忆写入阈值（宁缺毋滥, 决策 D-004）
    MEMORY_WRITE_MIN_CONFIDENCE: float = 0.6
    MEMORY_WRITE_MIN_IMPORTANCE: int = 4

    # 存储一致性
    RECONCILE_ON_STARTUP: bool = True  # 启动时 SQLite↔Chroma 对账自愈

    # 混合检索 / 排序融合（权重 α,β,γ,δ = 相似度,重要性,时间衰减,访问反馈）
    MEMORY_VEC_TOPN: int = 10            # 向量通道召回数
    MEMORY_FTS_TOPN: int = 10            # 关键词通道召回数
    MEMORY_SIM_THRESHOLD: float = 0.3    # 注入前最低余弦相似度（保守起步, 评测定参）
    MEMORY_FINAL_MIN_SCORE: float = 0.15
    MEMORY_RANK_WEIGHTS: str = "0.7,0.15,0.1,0.05"
    MEMORY_ACCESS_FEEDBACK: bool = True  # 命中注入后更新 access_count/accessed_at
    MEMORY_INJECT_TOPK: int = 5          # 注入 system prompt 的记忆条数

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


settings = get_settings()
