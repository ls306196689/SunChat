# 模块设计:pose-core(core/pose.py)

需求: R-017 | 触发: FR-1, FR-2, FR-3 | 日期: 2026-09-13 | 状态: draft r1

## 对外接口
```python
def analyze_video(data: bytes, *, max_sample_frames: int = None) -> PoseResult:
    """视频字节 → 步态分析结果。采样+MediaPipe+切分+指标全在此完成。

    PoseResult(数据类):
      metrics: dict  # 7 指标,见下表,缺项=None(周期不足时)
      quality: dict  # {"mean_conf": float, "body_ratio": float, "cycles": int, "score": 0~1}
      cycles: list[Cycle]           # 已切分步态周期
      landmarks_seq: list[list[LM] | None]  # 采样帧关键点(供 P2 选帧重绘),LM=(x,y,z,visibility)
      sample_ts: list[float]        # 每采样帧时间戳(秒)
      video_duration: float

    class Cycle:  # 单步态周期(右侧触地→下一次右侧触地)
      t0: float; t1: float
      events: dict  # {"initial_contact_r": ts|None, "midstance_r": .., "toe_off_r": ..,
                    #  "initial_contact_l": .., "midstance_l": .., "toe_off_l": ..}
      cadence_spm: float | None
"""

class PoseQualityError(Exception):
    """质量门槛不通过;属性: reason('low_conf'|'no_cycles'|'body_too_small'), detail 文案。"""

def sample_frames(data: bytes, fps: float, max_frames: int) -> tuple[list[np.ndarray], list[float], float]:
    """PyAV 采样(H,W,3) RGB 帧 + 时间戳 + 时长;超 max_frames 自动加大步距(保首末)。"""
```
metrics 7 键:`cadence_spm`(步/分)、`stance_swing_ratio`(触/腾,右腿)、
`knee_angle_at_contact_deg`、`knee_angle_at_toeoff_deg`、`hip_rom_deg`、
`pelvic_tilt_deg`(冠状面)、`asymmetry_pct`(左右腿触地时间差%)。

## 能力说明
- 提供:采样、逐帧单人体关键点、周期切分、7 指标、质量评分与门槛判定。
- 不提供:视频存盘、图像标注(P2)、报告(P3)、HTTP 语义(P4 负责翻译异常)。

## 内部关键逻辑
1. **采样**:`fps=min(POSE_SAMPLE_FPS, 时长→400帧步距)`;RGB 转换供 mp。
2. **关键点**:进程级单例 `_landmarker_lock + _landmarker`(风险 R-6 锁);单人体取
   pose_landmarks 唯一输出(2D 归一化坐标+x/y/z+visibility)。
3. **切分**:踝 y(屏幕向下,翻转)取速度反转+髋 y 辅助;左右分别找"踝最低点=触地候选",
   按侧配对成周期;周期数 <2 → 门槛 `no_cycles`。
4. **指标**:关节角=带符号投影∠ABC(如膝=髋-膝-踝向量夹角),取事件时刻前后 ±半帧窗口
   角度(中值降噪,风险 R-3);骨盆侧倾=左右髋 y 差/肩宽归一→度;不对称=左右 stance
   时长差的相对值。
5. **质量**:`mean_conf`<0.5(low_conf)/人体包围盒高占比<0.12(body_too_small)/周期<2
   → raise PoseQualityError;`score=mean_conf*0.7+min(body_ratio/0.3,1)*0.3` 随结果返回。
6. 阈值全部读 `settings`(POSE_MIN_CONF/POSE_MIN_CYCLES/POSE_MIN_BODY_RATIO/POSE_SAMPLE_FPS)。

## 依赖
- 库:av、mediapipe(tasks vision)、numpy、PIL(仅 P2 用,本模块无)。
- 无其他业务模块依赖(底层)。
