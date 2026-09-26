# R-018 TODO —— 无法在本机执行的事项(用户指令:无法执行的记录 todo 项)

日期: 2026-09-27 | 状态: step-1~4 已 done,step-5/6 待用户配合

## T-1 【step-5 真人实拍对账,AC-6】唯一硬阻塞:需要用户手机素材
**为什么本机做不了**:①无摄像头;②公版素材站实测不可取(mixkit 403、
archive.org / commons.wikimedia 超时、pexels 404);③pandamation 数据集走
Google Drive,本机网络不通;④合成剪影素材过不了 `coverage<0.6` 门槛
(step-4c:正立/横躺都卡在检出率 45%),且剪影上 cadence 严重高估
(A=233 vs 真值 165),不能用于步频对账。**真人素材不可替代。**

**需要用户做的动作(二选一)**:
- 手机拍侧跑视频(路跑:相机外侧 5~8m 跑过正面;或跑步机侧面平行)**横屏、竖屏各一段**,
  通过手机页面上传:手机页 `http://<本机局域网IP>:5173/m`(会话内直接发视频;
  本机 IP 用 `hostname -I` 取,当前值见本机 shell 输出,不写进文档),
  或把文件放到本机任意路径告诉我;
- 或直接给文件路径,我用接口跑:
  `curl -X POST http://localhost:8000/api/v1/chat/video/pose -F file=@x.mp4 -F session_id=21`

**判据(AC-6)**:两段均 `orient` 非 undetermined(横屏一段应为 90cw/270cw 之一)、
`cadence_spm ∈ [140,220]`、报告打印"画面已按人体朝向转正(头朝上,原为 …)"、
骨架帧里人正立;身高 173cm 已在 `backend/.env`(`POSE_USER_HEIGHT_CM=173`),
配速应出数并与自感配速 ±20% 级对账。
**结果写入**: `run-evidence/live-reconcile.md`,并回写 **R-017/step-8**(其 blocked 由本需求解除)。

## T-2 【step-6 归档】两个强制人工节点,不能自动完成
1. **归档门禁必须单独 question**(req-dev 硬规则 4:总授权不覆盖归档节点),
   需用户明示"确认归档";
2. 归档前需 **R-017 与 R-018 一并验收**(step-5 是两需求共同的收尾),
   R-017 state 的 step-8 需同步解除 blocked。

准备工作已全部就绪,拿到 step-5 结果后可一次做完:
`design/` 基线回写(朝向归一化并入 pose-core/pose-api/pose-report 基线)、
`baseline.md`、`INDEX.md` 两行(R-017/R-018)、
`compliance.sh archive sunchat/R-017` 与 `sunchat/R-018` 双 FAIL=0、全量测试摘要入档。

## T-3 【R-017 遗留,不在本需求范围】步频精度调优
活体观察(编码世代对齐的合成跑动,可控真值 **170 步/分**)在**正立基准**上测得
**375 步/分** → 高估不属 R-018 转正引入(正立同样高估),是 **R-017 步频算法**
遗留:①剪影/弱波形触发半步伪分;②IC 计数在 1~4 个周期的短样本上 ±1 即摆动几十个百分点。
R-017 归档时该风险本就未闭合,建议归档记录里点名,或另立 R-020。
证据: `run-evidence/step4c-real-inference-equivalence.md` §四、§八。

## T-3b 【与 T-3 同源,建议一并看】短样本下的 asym / cycles 稳健性
同批对照里 cycles 4 vs 1、asym 24.2% vs 50.0%,说明小样本时这两个指标对
段定位长度极敏感。属 R-017 指标稳健性,不在 R-018 范围。

## T-4 【R-019,已登记待立项】R-010 视频对话抽帧路同族缺陷
`core/video.py` 抽帧同样不应用显示旋转/不做人体朝向归一化 → 手机竖拍视频在
**普通视频对话**里仍是横躺画面交给 VLM。风险 R-4(prob 高)。本需求显式排除
(改动波及全部视频对话),INDEX 已提示。**需用户点头再立项。**

## T-5 【环境事实,避免下次重复试错】
- 便携 ffmpeg 7.0.2 **无法写** rotate 元数据(`-metadata:s:v:0 rotate=90` 静默丢弃)
  → 需要带元数据的样本时,用 `/tmp/mp4matrix.py::patch_tkhd_rotation` 直改 tkhd
  matrix box(已验证 PyAV 反读得到 `Type.DISPLAYMATRIX`);
- 读显示矩阵:`frame.side_data` 里的 DISPLAYMATRIX 已被 ffmpeg 转成**主机序**,
  用**小端** `<9i` 解(大端 `>9i` 会得 `(0,256,…)` 荒谬值);写进 tkhd 时才用大端
  (`struct.pack(">9i")`,ISO 14496-12)。写/读字节序不同,详见 step-4b §一;
- `/tmp` 下素材与脚本重启即丢,复现步骤已抄进 step-4b §四、step-4c 表头。

## T-6 【skill issue-009】用户已选"暂不处理"
compliance.sh 从 skill 目录运行时路径误报 + change/micro 节点缺登记,保持现状。
