# 模块设计:pose-core 朝向归一化(core/pose.py)

需求: R-018 | 触发: FR-1, FR-2, FR-3, FR-4, FR-7 | 基线: R-017/modules/pose-core.md(v2)
状态: draft r1 | 日期: 2026-09-26

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-26 | 新增 detect_orientation;sample_frames 增 rot;analyze_video 插入判向环节;PoseResult/quality 增键 | FR-1/2/3/4/7 |
| r1.1 | 2026-09-26 | **澄清(非语义变更)**:角度计算必须在**像素域**(u 向量 x×W、y×H 后再单位化)。签名里的 `frame_hw` 就是为此存在 | decisions.md D-1 |

## 对外接口

```python
ORIENT_MAP = {0: "0", 1: "270cw", 2: "180", 3: "90cw"}   # rot90 k → 对外字符串
ORIENT_K   = {v: k for k, v in ORIENT_MAP.items()}       # "undetermined" 不在表内 → 视为 k=0

def detect_orientation(lms: list, frame_hw: tuple[int, int]) -> dict:
    """粗扫帧关键点(归一化坐标,None=该帧无人)→ 画面朝向判定结果。纯函数,永不抛。

    返回 dict:
      orient:         "0" | "90cw" | "180" | "270cw" | "undetermined"
      orient_conf:    float 0~1(多数票占比;**低一致度的 undetermined 也如实回显占比**,
                      样本不足/全弃权时为 0.0)
      orient_samples: int    参与投票帧数(有效帧;**全分支如实计数**,含样本不足分支)
      orient_abstain: int    因落量化边界带弃权的帧数
      rot_k:          int 0..3,喂给 np.rot90 / sample_frames 的转正档(未定=0)

    判定只用关键点几何;不读任何视频元数据、不用画面宽高比、不用"能否检出"择优(FR-2)。
    """

def sample_frames(data: bytes, fps: float = None, max_frames: int = None,
                  t0: float = None, t1: float = None, width: int = 0,
                  rot: int = 0) -> tuple[list[np.ndarray], list[float], float]:
    """... 新增 rot:对每张解码帧做 np.rot90(frame, rot)(rot∈0..3,越界按 0 并不抛)。
    默认 0 → 与 v2 行为逐值一致(向后兼容)。"""

@dataclass
class PoseResult:
    ...                                    # v2 既有字段不变
    orient: dict = ...                     # detect_orientation 的返回(含 orient/rot_k/…)

# PoseResult.quality 增两键(消费侧一律 .get()):
#   "orient":      "0"/"90cw"/"180"/"270cw"/"undetermined"
#   "orient_conf": float
```

配置新增(`app/config.py`,POSE_* 组内):
```python
POSE_ORIENT_MIN_SAMPLES: int = 3     # 少于该有效帧数 → 不判(undetermined)
POSE_ORIENT_MIN_AGREE: float = 0.6   # 多数票占比门槛,不足 → undetermined
POSE_ORIENT_EDGE_DEG: float = 15.0   # |θ − 最近90°档| 超此值该帧弃权(斜握/异常)
```

## 能力说明
- 提供:以**人体自身头脚轴**为基准的 90° 档朝向判定;判定后统一坐标系(粗扫重跑 +
  密采与骨架帧同 k);转正后质量门槛在正确坐标系统计。
- 不提供:连续角度纠偏(仅 0/90/180/270 四档)、元数据读取与写入、多人体分头转正、
  `core/video.py`(R-010 普通视频路)的朝向处理(另立 R-019)。

## 内部关键逻辑

1. **单帧判定**(FR-1):
   `u = 归一化(肩中点 − 髋中点)`;`若 dot(鼻 − 髋中点, u) < 0 → u = −u`(鼻必在头侧,消 180°);
   `θ = degrees(atan2(u_x, −u_y))`(0=头朝上,顺时针为正);
   `q = round(θ/90)*90 mod 360`;`|θ − q| > POSE_ORIENT_EDGE_DEG` → 该帧**弃权**(斜握)。
   有效样本前提:该帧关键点非 None 且 `|肩中点 − 髋中点| > 1e-6`(退化躯干弃权)。
   证据:R-018/analysis A-5——真人 4 横躺帧 θ=−87~−95°(一致判 270cw),正立帧 −7.1°(判 0)。

2. **投票**(FR-3):按 q 计数,取最高档;`有效帧 < MIN_SAMPLES` 或 `占比 < MIN_AGREE`
   → `undetermined`(rot_k=0,**不转**)。不做二次推理、不做四向试探(A-4 证伪)。

3. **流水线插入**(FR-4/FR-7,`analyze_video`):
   ```
   粗扫帧(rot=0, 5fps@256px) → 粗扫关键点 → detect_orientation
     k = rot_k
     if k != 0: 粗扫帧 = np.rot90(粗扫帧, k) 逐帧转正 → 重跑粗扫关键点   # 门槛须在转正系
   → low_conf / body_ratio 门槛(转正后坐标) → locate_activity → 段内密采(rot=k)
   → _segment → _metrics → _pace → crop_bbox → PoseResult(orient=…, quality 增两键)
   ```
   - `orient="0"` 与 `undetermined` **两条分支代码路径完全相同**(不转、门槛照算、
     不新增任何 reject reason,FR-6),仅 quality/report/日志取值不同。
   - `_metrics` / `_pace` / `pelvic_tilt` / `crop_bbox` **零改动**:转正后它们读的
     y(竖直)/x(水平)自然正确(design-change.md 第五节逐点自查)。
   - 密采与端点取帧(`_frames_at_ts`)必须使用同一 `k`;skeleton 关键点与帧同在转正系。

4. **不破坏的既有契约**:
   - `sample_frames` rot 默认 0 → v2 全部既有测试逐值不变(AC-7)。
   - 永不抛:参数越界、关键点退化、无人体,统统归 `undetermined`(与 probe_frames 同风格)。
   - 注入面不变:`_detect_landmarks(frames, ts)` / `sample_frames(...)` / `probe_frames`
     仍是三个 monkeypatch 点;新增判向函数为纯函数,直测无需 mock。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| pose-skeleton | `draw_skeleton(rgb, lms, crop_bbox)`(帧与关键点同在转正系) | R-017/modules/pose-skeleton.md |
| pose-report | `transparency_lines(result)`(读 orient 透明度行) | R-018/modules/pose-report.md |
| pose-api | `_frames_at_ts(data, ts, rot)` 透传 k | R-018/modules/pose-api.md |
| app.config | `POSE_ORIENT_MIN_SAMPLES/MIN_AGREE/EDGE_DEG` | R-017/modules/pose-core.md(配置组) |
