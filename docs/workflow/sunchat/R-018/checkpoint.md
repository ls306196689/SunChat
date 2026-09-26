# R-018 checkpoint(step-1~4 done + 4b/4c 补证,step-5 blocked 待素材,step-6 待归档)
更新: 2026-09-27 | 上下文快照,新会话优先读本文件 + state.json + **todo.md**

## 需求主线
- R-018 跑姿抽帧朝向归一化(以人体头脚轴),bugfix 标准流程,phase=execute
- 四道门禁齐:requirements(user)/architecture(user)/design+plan(**blanket**,
  quote="后续都按照最优方案执行,我全部授权",scope=R-018)
- 步骤:1✅ 31d2dc30 / 2✅ b4beb0d4 / 3✅ 2d482c85 / 4✅ bb52be8e(+4b/4c 补证,本轮)
  / **5⛔ blocked:需用户手机实拍素材**(细则 `todo.md` T-1)/ 6⏳ 归档
  (归档节点必须单独 question,禁 blanket —— TODO T-2)
- **用户当前指令**:「我要离开一段时间,后续我全都授权你按照最优方案执行。无法执行的记录todo项。」
  → 已建 `R-018/todo.md`(T-1 实拍 / T-2 归档两问 / T-3、T-3b R-017 步频遗留 /
  T-4 R-019 立项 / T-5 环境事实 / T-6 skill issue-009 维持不处理)

## 已落地实现(勿重复设计)
- `core/pose.py`:`ORIENT_UNDET`/`ORIENT_MAP`/`_norm_rot`/`rotate_frame`/`_pixel_pt`/
  `_frame_orient`/`_Q_TO_K`+`_q_to_k`/`detect_orientation`(纯函数永不抛;u=肩髋轴中点法
  +鼻符号消180°+**像素域 θ**+15°边界带弃权+多数投票);`sample_frames(rot=0)` 内 np.rot90
- `analyze_video`:粗扫(rot=0)→判向→k≠0 则转正帧**重跑粗扫关键点**→门槛(不新增拒因)
  →locate→密采 rot=k;`PoseResult.orient` + quality `orient`/`orient_conf`
- `pose_report.transparency_lines`:首位插朝向行三态(正立不打印保 AC-7 逐值不变)
- `chat._frames_at_ts(data, ts, rot=0)` + 端点透传 `result.orient["rot_k"]`;evt 增
  `orient`/`orient_conf`(ok 路;fail 路无 result 按设计省略)
- config:`POSE_ORIENT_MIN_SAMPLES=3 / MIN_AGREE=0.6 / EDGE_DEG=15 / ENABLED`(关=回退 v2)
- **`_pace` 零改动**(decisions D-6:v2 写法本就是真像素距,横竖帧皆正确)

## 测试基线(全绿)
- `cd backend && python -m pytest tests -q` → **367 passed, 1 skipped**(~14.5s)
  (R-017 基线 340+1skip,+27 条:pose_core 19 / pose_report 4 / pose_api 4)
- AC-1/2/3/4/5/7 单测覆盖;**AC-3 文案 + AC-5 含"忘传 rot 必失败"负例**(32×16 横 vs 16×32 竖)
- 夹具:`_rot_lm`(与 np.rot90 逐像素/归一化同构)、`_patch_orient`(fake_detect 按喂入帧
  是否已转正决定给正向/旋转关键点——杜绝"关键点凭空转正")。k 方向真值 = (4−src_k)%4

## 本轮新增活体证据(run-evidence/,真实 MediaPipe 推理)
- **step-4b**:`/tmp/mp4matrix.py::patch_tkhd_rotation` 直改 tkhd matrix box → 造出手机
  竖拍同款 **display matrix**(PyAV 反读 `Type.DISPLAYMATRIX` 实证存在;写用大端、
  读 side_data 用**小端**)。真人内容在 无/顺90/顺270/180 四种元数据下 `orient`+`rot_k`
  **逐值一致** → 补上 step-4 当时记"未执行"的 AC-4 元数据对照。
  **§四决定性宽高比对照**:真人正立(238-A)竖幅→`np.pad` 加黑列变**横幅**(人像素不变),
  全分辨率与 256px 两口径仍 `orient=0 / rot_k=0 / 检出4/4`(宽高比启发式必然转掉它)。
- **step-4c**:合成跑动(v2 解剖相连:20/20 检出)真实推理跑通
  判向(横躺 20/20 票判 270cw/k=3 conf1.0)→转正→重跑粗扫→密采同 k→出指标。
  唯一变量对照(同字节,coarse 全分辨率):**body_ratio 不转正 0.316 → 转正 0.476**,
  与正立基准 **0.474** 一致(FR-7);不转正还产出 **pelvic_tilt −61.1°** 这类"看似合理
  实则错轴"的读数(转正 +7.7°)→ 线上 −42.1° 同源复现。
  编码世代已对齐(`/tmp/r018_ctl.py`:正立也空转再编码一轮)排除混淆。
- **骨架帧同 k 活体**:真人横躺字节,`_frames_at_ts(rot=0)`→640×360 横幅 vs
  `rot=3`→360×640 竖幅,`draw_skeleton` 产物 `/tmp/r018_live/skel_rot{0,3}.jpg`。
- ⚠诚实边界:合成素材 **不能**用来验收 AC-1 的"cadence ±5%"——正立基准自身 375 vs
  动画真值 170(半步伪分+IC 短样本抖动),属 R-017 步频遗留(T-3),数值对账归 step-5。

## 未完成 = 两条,都要用户
1. **step-5(blocked)**:手机侧跑实拍**横屏+竖屏各一段** →
   上传手机页(`http://<本机局域网IP>:5173/m`,IP 用 `hostname -I` 取),或 `curl -X POST localhost:8000/api/v1/chat/video/pose
   -F file=@x.mp4 -F session_id=21`。身高 173cm 已在 `backend/.env`。
   判据 AC-6:orient 非 undetermined、cad∈[140,220]、报告含"已按人体朝向转正"、
   骨架帧人正立、配速出数(±20% 级)。结果写 `run-evidence/live-reconcile.md`
   并回写 **R-017/step-8**(解除其 blocked)。
2. **step-6 归档**:`design/` 基线回写 + baseline.md + INDEX 两行 +
   `compliance.sh archive` 两侧 FAIL=0 + 全量摘要入档。**归档前必须 question**。

## 环境事实(省得再探)
- 服务**已在跑**(本轮 09-27 启动):`/api/v1/health` = healthy、llm_available=true。
  改码需重启(无 --reload):`pkill -f "uvicorn app.main"` 然后
  `cd backend && setsid --fork bash -c 'exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> backend.log 2>&1 < /dev/null'`(冷启动首请求 ~30s)
- **git push 欠账**:`repo.push_pending=true`,本地领先 3 个文档 commit
  (34d31e46/4634cf89/f23881d2)。⚠`curl https://github.com` 给 200 但 `git push` 走
  HTTPS 仍 `GnuTLS recv error (-110)`,连续 5 次失败 → 下次会话开场按 git-hub §push
  重试(敏感自检已过:净内容无内网 IP/凭据,唯一命中在"删除内网 IP"那一行)
- `backend/.env` 已建(gitignored,`POSE_USER_HEIGHT_CM=173`);局域网访问:手机页 `/m`(本机 IP 用 `hostname -I` 取)
- 便携 ffmpeg:`/tmp/fftool/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2`;
  ⚠ffmpeg 7 **写不了** rotate 元数据 → 用 `/tmp/mp4matrix.py` 改 tkhd(见 T-5)
- 外网:**pypi/github 200**,但 mixkit 403 / archive.org+commons 超时 / pexels 404
  → 真人跑动素材不可下载(这是 step-5 只能等用户的硬原因)
- 素材在 `/tmp`(重启即丢):`/tmp/r018_live/`(真人帧合成+元数据变体+骨架图)、
  `/tmp/r018_synth2/`(合成跑动 v2);脚本 `r018_{meta_ac4,eq2,v2,iso,ctl,skel_live,
  aspect,aspect2}.py`,复现步骤抄在 step-4b §五 / step-4c 表头

## 遗留/后续(不在本需求)
- R-019:`core/video.py`(R-010 视频对话抽帧路)同族不归一化(风险 R-4,INDEX 已提示)
- R-020(建议):R-017 步频精度(cadence 高估 / 短样本 asym 抖动),见 todo T-3
- skill issue-009 用户选暂不处理
