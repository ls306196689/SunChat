# R-018 checkpoint(step-1~4 done,剩 step-5 实拍 + step-6 归档)
更新: 2026-09-27 | 上下文快照,新会话优先读本文件 + state.json

## 需求主线
- R-018 跑姿抽帧朝向归一化(以人体头脚轴),bugfix 标准流程,phase=execute
- 四道门禁齐:requirements(user)/architecture(user)/design+plan(**blanket**,
  quote="后续都按照最优方案执行,我全部授权",scope=R-018)
- 步骤:1✅ 31d2dc30 / 2✅ b4beb0d4 / 3✅ 2d482c85 / 4✅ bb52be8e(证据 run-evidence/)
  / **5⏳ 真人实拍对账(需用户素材)** / 6⏳ 归档(归档节点必须单独 question,禁 blanket)

## 已落地实现(勿重复设计)
- `core/pose.py`:ORIENT_MAP/_norm_rot/rotate_frame/_pixel_pt/_frame_orient/_q_to_k/
  `detect_orientation`(纯函数永不抛;u=肩髋轴中点法+鼻符号消180°+**像素域 θ**+15°边界带
  弃权+多数投票);`sample_frames(rot=0)` 内 np.rot90,越界按 0
- `analyze_video`:粗扫(rot=0)→判向→k≠0 则转正帧**重跑粗扫关键点**→门槛(不新增拒因)
  →locate→密采 rot=k;`PoseResult.orient` + quality `orient`/`orient_conf`
- `pose_report.transparency_lines`:首位插朝向行三态(转正/不可定/正立不打印)
- `chat._frames_at_ts(data, ts, rot=0)` + 端点透传 `result.orient["rot_k"]`;evt 增
  `orient`/`orient_conf`(ok 路;fail 路无 result 按设计省略)
- config:`POSE_ORIENT_MIN_SAMPLES=3 / MIN_AGREE=0.6 / EDGE_DEG=15 / ENABLED`(关=回退 v2)
- **`_pace` 零改动**(decisions D-6:v2 写法本就是真像素距,横竖帧皆正确)

## 测试基线(全绿)
- `cd backend && python -m pytest tests -q` → **367 passed, 1 skipped**(~14s)
  (R-017 基线 340+1skip,+27 条:pose_core 19 / pose_report 4 / pose_api 4)
- AC-1/2/3/4/5/7 已覆盖;**AC-3 文案 + AC-5 含"忘传 rot 必失败"负例**(32×16 横 vs 16×32 竖)
- 夹具:`_rot_lm`(与 np.rot90 逐像素/归一化同构)、`_patch_orient`(fake_detect 按喂入帧
  是否已转正决定给正向/旋转关键点——杜绝"关键点凭空转正")。k 方向真值 = (4−src_k)%4

## 未完成 = 只有两条
1. **step-5 真人实拍对账(阻塞在素材)**:用户手机侧跑实拍**横屏录 + 竖屏录各一段**
   (跑过相机 2s 以上,身高对账已在 `backend/.env` 写 `POSE_USER_HEIGHT_CM=173`)。
   判据 AC-6:`orient` 非 undetermined、cad∈[140,220]、骨架帧人正立、报告含"已按人体
   朝向转正"、配速出数(±20% 级对账)。结果写 `R-018/run-evidence/live-reconcile.md`,
   并回写 **R-017/step-8**(其 blocked 由本需求解除)。**本机无摄像头+外网受限,合成素材
   不能产生真人跑动关键点 → 必须真人素材**(step-5 单测豁免理由已入 plan)。
   收件后:`curl -X POST localhost:8000/api/v1/chat/video/pose -F file=@x.mp4 -F session_id=21`
2. **step-6 归档**:design/modules 基线回写 + baseline.md + INDEX 两行(R-017/R-018)+
   `compliance.sh archive` 两侧 FAIL=0 + 全量测试摘要入档。**归档前必须 question 取确认**

## 环境事实(省得再探)
- 服务已恢复:uvicorn :8000(重启于 09-27,health 冷启动 ~30s 后 <1s)、vite :5173(`/m`)
- `backend/.env` 已建(gitignored,含 POSE_USER_HEIGHT_CM=173;start.sh cd backend 后启动,
  相对 .env 生效);改码需重启(无 --reload):`pkill -f "uvicorn app.main"` 然后
  `cd backend && setsid --fork bash -c 'exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> backend.log 2>&1 < /dev/null'`
- 局域网 192.168.1.47(`/m` 手机可直连上传实拍)
- 便携 ffmpeg:`/tmp/fftool/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2`;
  ⚠**ffmpeg 7 写 `rotate=` 元数据会被丢弃** → 元数据变体活体对照本机不可构造
  (已在 step-4 证据如实标注未执行;等效钉死=源码 grep 禁读 + A-1 PyAV 不应用元数据)
- 真人落盘帧可用:`data/uploads/chat/`(246 系列 1280×720 人横躺;238-A 真竖屏正立)
  —step-4 活体冒烟判定与 A-5 复算吻合(246-A θ=−90.2→q270;238-A θ=−7.1→q0)

## 遗留/后续(不在本需求)
- R-019:`core/video.py`(R-010 视频对话抽帧路)同族不归一化(风险 R-4,INDEX 已提示)
- skill issue-009(compliance 从 skill 目录跑路径误报 + change/micro 节点缺登记)用户选暂不处理
