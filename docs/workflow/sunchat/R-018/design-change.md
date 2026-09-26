# R-018 增量设计(相对基线 R-017/pose-core r-v2)

需求: R-018 | 基线: R-017/modules/{pose-core,pose-skeleton,pose-report,pose-api}.md
(R-017 尚未归档,`design/modules/` 内暂无 pose-* 基线,故以 R-017 模块文档为对照基线)
日期: 2026-09-26 | 版本: r1

## 一、变更清单(逐条注明触发 FR / 兼容性)

| # | 变更 | 触发 | 影响模块 | 向后兼容 |
|---|---|---|---|---|
| C-1 | 新增纯函数 `detect_orientation(lms_any, frame_hw) -> dict`(orient 判定) | FR-1,FR-2,FR-3 | P1 pose-core | 新增函数,无破坏 |
| C-2 | `sample_frames(..., rot=0)`:新增参数,在 `to_image()` 后按 `np.rot90` 转正 | FR-4 | P1 | **默认 rot=0 → 老调用行为逐值不变** |
| C-3 | `analyze_video()` 流水线插入判定环节:粗扫→判向→(k≠0 则)密采带 rot + **重跑粗扫关键点** | FR-1,FR-4,FR-7 | P1 | 签名不变;quality 增键 |
| C-4 | `PoseResult` 增 `orient: dict` 字段;`quality` 增 `orient`/`orient_conf` 两键 | FR-5 | P1→P4 | 增键,消费侧全部 `.get()` |
| C-5 | `_frames_at_ts(data, ts, rot=0)` 端点取帧同步转正 | FR-4 | P4→P2 | 默认参数,老调用不变 |
| C-6 | `transparency_lines()` 增"画面已按人体朝向转正/朝向不可定"一行(模板与 VL 双路) | FR-5,FR-6 | P3 | 行数可变,已有 list 契约 |
| C-7 | `evt=pose.analyze.run` fields 增 `orient` | FR-5 | P4 | fields 增加,键名不删 |

## 二、技术选型(每项一句理由)

| 选型 | 理由 |
|---|---|
| 转正用 `np.rot90(frame, k)`(内存像素),**不用** PyAV display matrix | A-1 实证 PyAV 17.1.0 不应用元数据;写 display matrix 依赖版本且不同解码器行为不一,像素级转正最确定 |
| 判向用**几何**(肩髋轴+鼻符号),**不重推理** | FR-2 禁"能否检出"作判据;A-4 实证真 upright 档可检不出,重推理既慢又不可靠 |
| 判向样本=粗扫帧(5fps)的**已检出关键点**,多数投票 | 零额外推理开销(FR-3);粗扫本就跑全片,样本量≈全片秒数×5 |
| k≠0 时**粗扫关键点重跑一次**(在转正帧上) | 保证 body_ratio/locate_activity 的 y 轴、crop_bbox 全部来自转正坐标系(FR-7);代价 = 一次粗扫(5fps@256px,实测 low_conf 全片 0.5s 级,可接受) |
| 判定阈值参数化 `POSE_ORIENT_*`(min样本/一致度/边界带) | 与既有 POSE_* 组同构,可调不改码 |

## 三、流水线改动前后(时序)

```
改前: probe → 粗扫帧 → 粗扫关键点 → [low_conf/body_ratio 门槛] → locate_activity
      → 段内密采 → 密采关键点 → _segment → _metrics → _pace → crop_bbox → PoseResult

改后: probe → 粗扫帧(rot=0) → 粗扫关键点 → detect_orientation(关键点投票)
      ├─ orient=="0" ──┐
      ├─ undetermined ─┤→ [low_conf/body_ratio 门槛] → locate → 密采(rot=k) → …(下同)
      └─ k≠0:粗扫帧 rot=k → 粗扫关键点**重跑** → 门槛 → locate → 密采(rot=k) → …
```
关键点(易错):
- 门槛(low_conf/body_ratio)**一律在转正后的坐标系统计**,否则 A-3 的误拒不除(FR-7)。
- `undetermined` 分支与 `orient="0"` 分支**行为完全相同**(不转、门槛照算、不新增拒析),
  唯一区别是 quality.orient 值与报告文案(FR-6)。
- 密采与骨架帧取帧(`_frames_at_ts`)必须用**同一个 k**(FR-4),骨架不得回到横躺系。
- `_metrics/_pace/pelvic_tilt` 全部不改:它们读的 y/x 在转正系里自然正确。

## 四、detect_orientation 判定逻辑(纯函数,详见 R-018/modules/pose-core.md)

```
输入: 逐粗扫帧关键点列表(归一化坐标,None=该帧无人)
每帧: u = 归一化(肩中点 − 髋中点);若 dot(鼻−髋中心, u) < 0 → u 取反(消 180°)
      θ = atan2(u_x, −u_y)(0=头朝上,+顺时针偏)→ 量化 q = round(θ/90)*90 ∈ {0,90,180,270}
      边界带护栏: |θ − q| > POSE_ORIENT_EDGE_DEG(15°) → 本帧弃权
投票: 有效帧 < POSE_ORIENT_MIN_SAMPLES(3) 或 多数占比 < POSE_ORIENT_MIN_AGREE(0.6)
      → undetermined(不转)
输出: {"orient": "0"|"90cw"|"180"|"270cw"|"undetermined",
       "orient_conf": 多数占比(0~1, 未定为 0.0),
       "orient_samples": 参与投票帧数,
       "rot_k": 对应的 np.rot90 k 值(0..3;未定=0)}
```
**禁用项(FR-2,实现与测试双向钉死)**:不读 `container/stream.metadata`、不读
`side_data`、不使用 `frame.to_image()` 之外的元数据推断、**不使用画面 W>H/H>W**、
不使用"某朝向能否检出/检出质量高低"择优。

## 五、坐标系影响自查(逐消费点)

| 消费点 | 转正后是否正确 | 说明 |
|---|---|---|
| `_side_ankle_y` / `_dominant_lag`(踝/髋 y 振荡) | ✅ | 真振荡轴回到 y(A-3:横躺时 x=21.7>y=9.0,转正 y=28.2>x=15.1) |
| `_stance_intervals`(y>μ+kσ 切 IC/TO) | ✅ | 同上 |
| `locate_activity`(踝 y 能量门) | ✅ | 须在转正系重跑(本设计 C-3) |
| `_metrics.pelvic_tilt`(髋连线 atan2(dy,dx)) | ✅ | A-3:+91.4° → +1.0° |
| `_pace`(落点像素 x 距 + 腿长自标定) | ✅ | 转正后 x 才是水平世界轴;m/px 由腿长自标定,不依赖画面宽高比 |
| `crop_bbox`(关键点并集) | ✅ | 转正关键点求并集,FR-12 语义不变 |
| `body_ratio`(FR-3 门槛 0.12) | ✅ | 0.152 → 0.306,阈值**不改**(R-3 缓解:裕度充足,单测锁定) |
| `skeleton._remap` + 裁剪 | ✅ | 关键点与帧同在转正系 |

## 六、风险评审表(M9,同步 state.risks)

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R-1 | 肩/髋关键点遮挡或抖动致单帧 u 不稳 | 中 | 中 | 中点法对左右互换不敏感;≥3 样本多数投票;一致度<0.6 判 undetermined;边界带 15° 弃权 |
| R-2 | 斜握(非 90° 档)量化后残余倾斜 | 中 | 低 | 既有去趋势吸收小幅;报告透明度声明;>15° 落边界带→不转 |
| R-3 | 转正后 body_ratio/crop 语义变,既有阈值需复核 | 中 | 中 | 实测 0.306(门槛 0.12 裕度足);**阈值不改**,AC-2/AC-1 单测锁定逐值 |
| R-4 | R-010 视频路(core/video.py)同缺陷遗留 | 高 | 中 | 用户定夺另立 R-019;INDEX 已登遗留提示 |
| R-5 | 竖屏转正后帧尺寸变化致落盘变大 | 低 | 低 | 沿用 JPEG q85;必要时另需求调压缩 |
| R-6 | k≠0 时粗扫重跑增加耗时 | 中 | 低 | 仅一次粗扫(5fps@256px);实测纯色全片 low_conf 0.5s 级;evt 日志 total_ms 可观测 |
| R-7 | quality 增键使既有断言/前端解包失败 | 低 | 中 | 一律 `.get()`;AC-7 全量零回归;前端只读 report/frame_ids |

## 七、可观测性约定
- `evt=pose.analyze.run` fields 增 `orient`(如 `90cw`)、`orient_conf`;ok/fail 两路都打。
- `undetermined` **不新增 reject reason**(FR-6),仅在报告与 quality 体现,日志同 evt 打
  `orient=undetermined` 便于统计占比。
- 错误信息带上下文:判定函数纯函数无副作用;`sample_frames` rot 参数越界(非 0..3)
  按 0 处理并在 quality 打 `orient_rot_clamped=true`(不抛,保持"永不抛"契约)。

## 八、测试约定
- 框架/命令:`cd backend && python -m pytest tests -q`(基线 340 passed 1 skipped)。
- 新增覆盖(全部走既有注入面 `_detect_landmarks`/`sample_frames`,不依赖真人视频):
  AC-1 横躺夹具→orient=90cw/270cw 且 cadence 回真值±5%;AC-2 正立夹具→orient=0 且
  **逐值等于**基线;AC-3 三分支(无人 / 样本<3 / 角落边界带)→undetermined 不转不拒;
  AC-4 **解耦断言**:同一夹具内容 × {元数据 rotate=90 / 无元数据} × {竖幅 / 横幅} →
  orient 只随人体朝向变;AC-5 骨架+crop 同坐标系;AC-7 全量零回归。
- 真人素材豁免单测(AC-6),由 R-017 step-8 实拍对账承担(已在计划豁免声明)。

## 九、不做清单
- 连续角度(非 90° 档)纠偏、机位俯仰校正(R-9 已用">15° 不出配速")。
- `core/video.py`(R-010 普通视频对话路)朝向归一化 → 另立 R-019。
- 多人体朝向、跑步机场景专项优化、阈值重标定。
