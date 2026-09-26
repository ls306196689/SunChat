# R-018 step-4 全量回归 + 活体冒烟证据

需求: R-018 | 日期: 2026-09-27 | 覆盖: AC-7、AC-4 活体面、FR-7 活体面、R-6 耗时
环境: uvicorn :8000(改码后重启,pid 175370)/ PyAV 17.1.0 / MediaPipe pose_landmarker_lite
素材来源: 真人落盘帧(消息 246 pipeline 自采 4 帧,1280×720 画面内人横躺;消息 238-A 真竖屏正立帧),
便携 ffmpeg `/tmp/fftool/.../ffmpeg-linux-x86_64-v7.0.2` 合成 5s@5fps mp4(仅做容器/朝向变体)。

## 一、AC-7 全量零回归
```
cd backend && python -m pytest tests -q
367 passed, 1 skipped, 64 warnings in 14.08s
```
基线 340 passed 1 skipped → 新增 27 条(pose_core 19 / pose_report 4 / pose_api 4),
既有用例**一字未改**全部通过;quality 增键未破坏任何前端/断言解包(R-7 未成真)。

## 二、判定活体面:真人帧四向档位(与 analysis A-5 复算一致)
`detect_orientation` 逐帧 θ 与 A-5 手工复算完全吻合(像素域,D-1):

| 素材 | 喂入档 rot90 k | θ(°) | 量化 q | 判定 |
|---|---|---|---|---|
| 246-A 真人横躺 | 0(原样) | −90.2 | 270 | 修正 rot_k=3(单帧样本不足→不可定,符合 FR-3 门槛) |
| 246-A | 1 | 177.8 | 180 | 同上 |
| 246-C | 3 | 0.5 | 0 | 同上 |
| 238-A 真竖屏 | 0 | −7.1 | 0 | 同上 |

单帧一律 `undetermined` 是 FR-3 样本门槛(≥3 帧)的正常行为,不是缺陷;
投票通过样例见第三节。

## 三、AC-4 活体面:判定只随人体朝向变,与容器宽高比解耦
| # | 素材 | 容器/帧形状 | 检出 | orient | conf | rot_k | 判读 |
|---|---|---|---|---|---|---|---|
| 1 | 真人横躺 | 640×360 横幅 | 4/4 | **270cw** | 0.667 | 3 | 判向正确(采样 3 帧有效→过样本门槛) |
| 2 | 同一横躺内容贴竖幅黑边画布 | 360×640 竖幅 | **1/4** | undetermined | 0.0 | 0 | **未因"画面是竖的"就判 0**;检出退化→按 FR-6 不转 |
| 3 | 同内容像素转正(rot90 k=3) | 360×640 竖幅 | 4/4 | undetermined(2 有效帧,2 弃权) | 0.0 | 0 | 未误转 |
| 4 | 238-A 真竖屏正立真人 | 362×640 竖幅 | 4/4 | **0** | 1.0 | 0 | 正立内容判 0,不转 |

结论:1 与 2 内容同向 → 判定没有出现"竖幅容器当作已正立"的宽高比偷判;4 证明同一竖幅容器
在内容确实正立时判 0 → **orient 只随人体朝向变**。

⚠工具限制(如实登记):原计划用 `-metadata:s:v:0 rotate=90` 造"带 rotate 元数据 vs 不带"
对照,但本机便携 ffmpeg 7.0.2 **写入的 rotate 元数据被丢弃**(实测两种 mp4 的
`stream.metadata`/`container.metadata`/`frame.side_data` 均无 rotate 字段,`to_image()` 尺寸
一致)——该组对照在本环境不可构造。元数据禁用的等效钉死改由两处承担:
① `test_source_has_no_metadata_or_aspect_basis` 对判定源码 grep 禁 `metadata`/`side_data`/
`rotate`/`displaymatrix`/`container`/`stream`;② R-017/R-018 analysis A-1 已实证 PyAV 根本不
应用该元数据(判定即使想读也读不到可执行语义)。**元数据变体的活体对照标注为未执行**。

## 四、FR-7 活体面 + 门槛走向(真人横躺素材端到端)
同一素材 `analyze_video`:
```
POSE_ORIENT_ENABLED=False(v2 行为): reject=no_activity  (598ms)
POSE_ORIENT_ENABLED=True          : reject=no_activity  (323ms)
body_ratio: 横躺系 0.256 → 转正系 0.271(门槛 0.12,conf 0.82)
```
- 两路都能过 low_conf 与 body_too_small 门槛,最终都停在同一条**内容**门槛
  `no_activity`——素材是 4 张静态照片合成的"视频",本就没有跑动振荡,拒析是正确行为。
- 转正系 body_ratio 0.271 高于横躺系 0.256,方向与 A-3(0.152→0.306)一致;
  绝对值差异来自 256px 粗扫下关键点抖动(A-3 用原始 1280×720 直检)。
- ⚠ 未能在活体上跑通 ok 路径带转正:合成素材不产生真人跑动关键点(环境事实,
  见 checkpoint"真人素材不可替代")。ok 路径 orient 字段/透明度行/同-k 骨架帧
  由 step-1~3 单测(含 AC-5 正负例)覆盖,活体 ok 路径归 step-5 实拍对账。

## 五、R-6 耗时与 R-5 尺寸观察
- 端点活体:`ms=181.8 / 582.5`(粗扫 + 判向 + k≠0 重跑一次粗扫),无劣化迹象。
- 冷启动首次 `/api/v1/health` 23s(MediaPipe/模型加载),之后 <1s(与 R-017 同)。
- 竖屏转正帧尺寸变化未触发落盘异常(AC-5 单测断言 16×32 转正系 vs 32×16 横)。

## 六、端点活体日志
```
evt=pose.analyze.run result=fail reason=no_activity
evt=http.post result=ok path=/api/v1/chat/video/pose status=400 ms=582.5 client=127.0.0.1
```
拒析 reason 集合与拍摄指引文案一字未动(FR-6 不新增拒析)。ok 路径 `orient=` 字段
由 `test_ok_log_carries_orient` 覆盖(活体 ok 待 step-5)。
