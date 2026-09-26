# 模块设计:pose-skeleton 朝向适配(core/pose_skeleton.py)

需求: R-018 | 触发: FR-4(同坐标系) | 基线: R-017/modules/pose-skeleton.md
状态: draft r1 | 日期: 2026-09-26

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-26 | **本模块代码零改动**;仅登记坐标系契约与新增回归断言 | FR-4(AC-5) |

## 对外接口
**签名与行为完全不变**(引基线,不重复定义):
```python
def select_key_frames(result: PoseResult, k: int = 4) -> List[Tuple[int, str]]: ...
def draw_skeleton(rgb_frame: np.ndarray, landmarks: list,
                  crop_bbox: Optional[Tuple[float,float,float,float]] = None) -> np.ndarray: ...
```

## 能力说明(FR-4 坐标系契约)
- 本模块**不做任何朝向处理**,也无需做:它收到的 `rgb_frame` 与 `landmarks` 是否正立,
  由调用方(P4)保证**同源同 k**。这是本需求刻意的设计选择——朝向归一化只有一处落点
  (`core/pose.py` 采样侧 + P4 取帧侧),避免两处各转一半造成"指标正立骨架横躺"。
- 契约(新增,须由 AC-5 钉住):
  `draw_skeleton` 的 `rgb_frame` 必须是 `sample_frames(..., rot=k)` 或
  `_frames_at_ts(..., rot=k)` 产出的帧;`landmarks` 必须来自同一 k 下的
  `_detect_landmarks`;`crop_bbox` 来自同一 k 下的 `analyze_video`。三者 k 不同即违约。
- 不提供:自动检测/纠正传入帧的朝向(明确排除,见不做清单)。

## 内部关键逻辑
无改动。`_remap`(裁剪系内重映射)与越界钳制在转正系内语义不变:归一化坐标与
转正后帧的尺寸同系,`crop_bbox` 亦在转正系内求得。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| pose-core | `PoseResult.landmarks_seq / sample_ts / crop_bbox / orient`(只读) | R-018/modules/pose-core.md |

## 回归断言(归入 P1/P4 测试文件,本模块测试只补一条契约断言)
- AC-5:对"横躺夹具 + k=对应档"产出的帧与关键点绘制骨架,断言骨架像素重心在
  **转正后帧**的中部偏上(头在上);并对"帧与关键点 k 不一致"的负例给出可诊断断言
  (即:若忘了传 rot,该测试必须失败)。
