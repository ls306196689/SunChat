# R-018 step-4 补做:AC-4「带 rotate 元数据 vs 不带」活体对照

需求: R-018 | 日期: 2026-09-27 | 覆盖: AC-4 元数据面(补 step-4 标注"未执行"的那一组)
环境: PyAV 17.1.0 / MediaPipe pose_landmarker_lite / 便携 ffmpeg 7.0.2(不用于写元数据)
关联: step4-regression-and-smoke.md §三 尾部"⚠工具限制"、decisions.md D-1/D-5

## 一、为什么当初记未执行,现在为什么能执行
step-4 原计划用 `ffmpeg -metadata:s:v:0 rotate=90` 造带旋转元数据的 mp4,实测本机
便携 ffmpeg 7.0.2 **写入被静默丢弃**(`stream.metadata`/`container.metadata`/
`frame.side_data` 均无 rotate,`to_image()` 尺寸不变)→ 对照不可构造,如实标注未执行,
当时靠 ①判定源码 grep 禁读元数据 ②analysis A-1 实证 PyAV 不应用元数据 两处等效钉死。

本次改从**容器规范真身**下手:MP4 里的显示旋转就是 `trak/tkhd` 内的 matrix box
(16.16 定点 3×3,ISO 14496-12 行主序大端)。直接改字节的脚本 `/tmp/mp4matrix.py`
(`patch_tkhd_rotation(src,dst,angle)`:递归下探 moov→trak→tkhd,按 tkhd version
取 `fixed = 4/8`,偏移 `p = t+4+2*fixed+4+4+fixed+8+2+2+2+2`,写 36 字节矩阵 +
保留 width/height),即可造出手机竖拍同款元数据。**关键是先证明元数据真的存在**,
否则对照是自欺:

```
$ python -c "… av.open(p); f=next(c.decode(video=0))"
flat_nometa.mp4    coded=640x360 n_side=0 matrix=None    toimage=640x360
flat_META90.mp4    coded=640x360 n_side=1 matrix=(0,1,0,-1,0,0,0,0)  toimage=640x360
flat_META270.mp4   coded=640x360 n_side=1 matrix=(0,-1,0,1,0,0,0,0)  toimage=640x360
upright_META180.mp4 coded=360x640 n_side=1 matrix=(-1,0,0,0,-1,0,0,0) toimage=360x640
portrait238_META90/270.mp4  coded=362x640 n_side=1 matrix=…90/…270   toimage=362x640
```

取证要点(逐条,避免误读):
- **写入按大端**(tkhd box 内是 ISO 规范的 16.16 大端定点),**读取按小端**:
  ffmpeg 已把解码帧的 DISPLAYMATRIX 转成主机序,`frame.side_data` 要用 `<9i` 解
  (实测大端 `>9i` 解出 `(0,256,0,65535,…)/65536` 这类荒谬值,小端解出
  `(0,1,0,-1,0,0,0,0)` 即规范 90° 矩阵)——写/读字节序不同这一事实本身,
  正反证了元数据**经过了容器的编解码链路**,不是我们自己在内存里糊的;
- `container.metadata`/`stream.metadata` 里 **没有** `rotate` 键(ffmpeg 17 时代改用
  display matrix 表达),所以取证读 side_data 而非 metadata 字典;
- **`to_image()` 尺寸与无元数据变体完全一致(640×360 / 362×640)** —— 这就是
  analysis A-1 的活体重述:元数据存在但 PyAV **不执行**它,喂给 MediaPipe 的像素
  仍是码流原朝向。对照因此有意义:如果判定读元数据,输出必然随元数据变。

## 二、活体对照结果(真实推理,非注入)
判定链与 `analyze_video` 完全同构:`sample_frames(POSE_COARSE_FPS, width=256)`
→ `_detect_landmarks`(真实 MediaPipe)→ `detect_orientation`。脚本
`/tmp/r018_meta_ac4.py`。

| # | 内容(真人素材) | 显示矩阵元数据 | 检出 | orient | conf | samples | rot_k | 期望 |
|---|---|---|---|---|---|---|---|---|
| 1 | 246 组 4 帧,人横躺,640×360 | 无 | 4/4 | **270cw** | 0.667 | 3 | 3 | 270cw |
| 2 | 同内容 | **顺 90°(与内容矛盾)** | 4/4 | **270cw** | 0.667 | 3 | 3 | 同 1 |
| 3 | 同内容 | **顺 270°(恰与正确修正同向)** | 4/4 | **270cw** | 0.667 | 3 | 3 | 同 1 |
| 4 | 246 组像素转正(竖向下),360×640 | 无 | 4/4 | undetermined | 0.0 | 2 | 0 | 不转 |
| 5 | 同 4 | **180°** | 4/4 | undetermined | 0.0 | 2 | 0 | 同 4 |
| 6 | 238-A 真竖屏正立真人,362×640 | 无 | 4/4 | **0** | 1.0 | 4 | 0 | 0 |
| 7 | 同 6 | **顺 90°(谎报)** | 4/4 | **0** | 1.0 | 4 | 0 | 同 6 |
| 8 | 同 6 | **顺 270°(谎报)** | 4/4 | **0** | 1.0 | 4 | 0 | 同 6 |

断言(脚本内打印,全 PASS):
- 组 1/2/3 同内容三变体判定签名一致 `{('270cw', 3)}`;
- 组 4/5 一致 `{('undetermined', 0)}`;
- 组 6/7/8 一致且为 `{('0', 0)}`;
- 5 个带元数据变体的 display matrix 反读全部非空且互不相同;3 个无元数据变体全为空。

## 三、结论与如实边界
**结论(AC-4 元数据面成立)**:同一个真人内容,在"无 / 顺90 / 顺270 / 180"四种显示
矩阵元数据下,`orient` 与 `rot_k` **一字不差**;而矩阵确实不同且确实被解码器带出
(side_data 有 DISPLAYMATRIX)。判定唯一依据是像素里的人体头脚轴 → 满足 FR-2
"禁止用容器/stream rotate 元数据作为判定依据或优选条件"。
尤其组 3 是**元数据恰好指向正确修正角**的情形(顺 270 与 rot_k=3 同向):若实现
有任何"信任元数据"的捷径,该组会表现为"直接按元数据转、判定字段等于元数据",
但 orient 仍由人体轴独立得出且与 nometa 完全一致 → 无捷径。

**如实登记两点**:
1. 组 4/5 判 `undetermined` 不是缺陷:该素材是 4 张静止照片构成的"视频",竖向下
   256px 粗扫仅 2 帧给出有效肩髋轴(< `POSE_ORIENT_MIN_SAMPLES=3`)→ 按 FR-3/FR-6
   不转。本组要证的是"两种元数据下判定相同"(已成立),不是"竖幅必然判 0"。
   判 0 的活体证据由组 6/7/8(238-A,conf 1.0 / 4 样本)给出。
2. 元数据仍非手机实拍:tkhd 矩阵是手工写入的规范字段,形状与语义与手机竖拍一致、
   并被解码链如实带出,但**真实手机素材的端到端 ok 路径**(透明度行 + 同-k 骨架帧 +
   cadence 真值)仍在 step-5 实拍对账窗口。

## 四、AC-4 宽高比面:正立人体放进**横幅**画布仍判 0(决定性对照)
step-4 §三那一组是"横躺内容塞进竖幅画布",但 256px 下降采样使检出率塌到 1/4,
只能说"没偷判 0",证据力弱(那是分辨率效应不是宽高比效应)。本次把条件取反并
**用 np.pad 只加黑边、不缩放**,使人体像素逐值不变、唯一变量是容器宽高比:

素材 `4_portrait_upright_238A.mp4`(真人,**正立**,362×640 竖屏),
左右加黑列 → 724×640 **横幅**;脚本 `/tmp/r018_aspect2.py`,产物
`/tmp/r018_live/upright238_padlandscape.mp4`。

| 口径 | 容器 | 宽高比 | 检出 | orient | conf | samples | rot_k |
|---|---|---|---|---|---|---|---|
| 全分辨率 | 362×640 | 竖 | 4/4 | `0` | 1.0 | 4 | 0 |
| 全分辨率 | **724×640** | **横** | 4/4 | **`0`** | 1.0 | 4 | **0** |
| 生产 width=256 | 256×453 | 竖 | 4/4 | `0` | 1.0 | 4 | 0 |
| 生产 width=256 | **256×226** | **横** | 4/4 | **`0`** | 1.0 | 4 | **0** |

**为什么这条是决定性的**:"画面是横的 → 人多半躺着 → 需要转正"是一类极易写出的
宽高比启发式,它在这里必然会把正立的人转掉。实测两种口径下检出 4/4、
`orient="0"`、`rot_k=0`(**不转**),与 `_frame_orient` 的数学一致
(不缩放时 `(x/W)·W` 复原原像素,θ 不因黑边改变)→ FR-2"禁止用画面宽高比作为
判定依据或优选条件"在活体上得到正面证明,而不只是"源码里没有读它的代码"。

同向的弱对照(横躺内容 → 竖幅画布,`/tmp/r018_aspect.py`)结果如实记录:
256px 口径下检出 4/4→2/4、判定退化 `undetermined`(分辨率效应,非宽高比效应);
全分辨率口径 3/4 与 2/4 均 `undetermined`(样本不足)。二者都**未出现**
"竖幅→判 0"的偷判,但不能替代上表的正面证据。

## 五、复现步骤(素材在 /tmp,重启会丢)
```bash
FF=/tmp/fftool/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2
# 1) 由 backend/data/uploads/chat 的真人帧合成无元数据 mp4(见 /tmp/r018_build.py)
# 2) 打 display matrix(手机竖拍同款元数据)
python -c "import sys; sys.path.insert(0,'/tmp'); from mp4matrix import patch_tkhd_rotation as P; \
  P('/tmp/r018_live/flat_nometa.mp4','/tmp/r018_live/flat_META90.mp4',90); \
  P('/tmp/r018_live/upright_nometa.mp4','/tmp/r018_live/upright_META180.mp4',180)"
# 3) 跑对照
cd backend && python /tmp/r018_meta_ac4.py
```
