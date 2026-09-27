# R-018 TODO —— 无法在本机执行的事项(用户指令:无法执行的记录 todo 项)

日期: 2026-09-27(13:09 复核) | 状态: step-1~4 已 done,step-5/6 待用户配合
| 两仓 origin==HEAD 无待推(本仓 tip `9f030a60`,skills tip `00b3d79`)
| 本轮变更: T-8/T-9 复核后转为"已由 skill R-009 关闭",新增 T-10(与 R-016 共用一次手机采集)

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
- 或直接给文件路径,我用**已入库的取证脚本**跑(会按 AC-6 逐项打 PASS/FAIL + 机读 JSON):
  ```bash
  cd backend && python scripts/pose_live_capture.py \
      --file /path/横屏.mp4 --label 横屏 --session-id 82
  # 竖屏同命令换 --file/--label;两段都跑完即可直接抄成 run-evidence/live-reconcile.md
  ```
  (脚本判定逻辑有单测 `tests/test_pose_live_capture_script.py`,8 例;
  等价裸命令:`curl -X POST http://localhost:8000/api/v1/chat/video/pose -F file=@x.mp4 -F session_id=82`)

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

## T-7 【范围外发现,建议另立 micro 需求】启动期 storage reconcile 成功日志必抛 TypeError
现场(本轮重启后端时 backend.log 实录):

```
TypeError: log_event() got multiple values for argument 'result'
```
根因(`backend/app/main.py:65`,与 R-018 无关,属既有缺陷):
```python
log_event(logger, "storage", "reconcile", "ok", result=str(r)[:120], pruned=p)
#       ^log     ^domain     ^action      ^result(位置参)  ↑又给了一次 result= 关键字 → 双值冲突
```
签名是 `log_event(log, domain, action, result, exc=False, level=None, **fields)`
(`backend/utils/logger.py:167`)。

**影响面(已核实,不扩大)**:`reconcile()` / `prune_orphan_vectors()` /
`fts_bootstrap_from_sqlite()` 都在该行**之前已执行完成**,异常被外层 `except` 捕获,
服务照常 `Application startup complete` → **功能无损,但每次启动都把"成功"记成
fail + 误导性 error + 堆栈**,污染启动日志、掩盖真故障。修法一行:
把 `result=str(r)[:120]` 改成 `stat=str(r)[:120]`(或删掉该 kw)并加一条
"启动成功路径不抛"的回归单测。

**为什么没在本需求里顺手改**:改 `app/main.py` 属改变代码行为,req-dev 硬规则 3
要求任何逻辑改动必须先立需求与方案文档;R-018 的范围是抽帧朝向归一化,夹带会让
回归面与验收判据失真。建议按 micro 快速通道立项(1 文件 + 1 单测)。

## T-8 【已解决,无需你再决定】本仓 master 未设 upstream
原现象:`git diff @{u}...HEAD` 在本仓直接 `fatal: 尚未给分支 'master' 设置上游`
(`branch.master.merge` 为空),而 skill 旧 §push 第 1 步正用它取样 →
命令失败 → stdout 空 → grep 无命中 → **报 CLEAN 而实际一个字节都没查**(假绿)。

**现状(skill R-009 已修,2026-09-27)**:取样基线改为显式解析链
`adopted_at_commit → @{u} → last_pushed_commit`,**三者皆不可解析而仍有待推提交即判 FAIL**
(issue-019 fixed,SHA `6d3754c`)。本仓实测(不依赖 upstream):
```
$ bash req-dev/compliance.sh pre-push sunchat/R-018
[PASS] R009-PRE-PUSH base=last_pushed_commit:9f030a60b pending=0 无待推内容(不打印 CLEAN)
— 节点 pre-push @ sunchat/R-018: FAIL=0
```
→ 本项**不再需要你授权** `git branch --set-upstream-to`。习惯仍保留:范围核对用显式
`origin/master..HEAD`,stderr 出 `fatal:` 则自检作废。

## T-9 【skill 侧:三项缺陷已由 R-009 关闭,只剩一个历史清理决定】
本轮 push 通道暴露的 skill(req-dev)缺陷,**均已在 skills 仓 micro R-009 修复并推送**
(2026-09-27 复核,登记状态以 `skills/issues/INDEX.md` 为准):
- **issue-018(过拦)** → fixed @ `6d3754c`:命中判定只看新增行(`added_only()`),
  删除行/上下文行仅回显;
- **issue-019(高,失拦)** → fixed @ `6d3754c`:基线链 fail-closed + `pre-push` 机械节点
  (见 T-8 实测输出),节点空转亦判 FAIL(issue-022);
- **issue-020(低)** → **wontfix,你 2026-09-27 已定**:不扩 `allow` 白名单,
  汇总修订型提交走"挂在在办需求的 R-NNN 下提交"这一合规通道。

**流程违例(精确记法,已自纠)**:推那批待推 commit 本身不违例
(SKILL §会话初始化第 2 条授权"凡 push_pending → 按 §push 重试合并推送");
违例的是 **§push 第 1 步敏感自检整步跳过**——补跑时 STRONG 在**新增行**命中 2 行:
issue-018 的"二次复现"记录把已清理的内网 IP 以字面量写回文档(即整改提交重新引入被整改对象),
属**真泄露**而非该 issue 声称的过拦,自检本可当场拦住。已改形态描述并推清。

### 唯一留给你的决定:远端历史里那一条字面内网 IP 是否清洗
本轮**逐 commit 全历史核实**(不是转述):`git rev-list origin/main` 逐 SHA `git grep`
→ **仅 `2826cb77`(短 2826cb7)一个 commit 的 `req-dev/issues/issue-018.md` 含该字面**,
远端 tip(00b3d79)与全仓工作树 **0 命中**。
- 性质:私仓、非凭据、仅 RFC1918 内网地址;当前 checkout 与所有后续版本均已无该串。
- 清洗代价:`filter-branch`/`filter-repo` 改写 `2826cb7` 之后的**全部**后代 SHA
  + `push --force`,而 R-008/R-009 的台账与 state 里登记的 SHA(`6d3754c`/`2eabc7c`/`821dd72` …)
  会随之失配 → 归档记录的取证引用需一并回写。
- **建议:不清洗**(后果可控、代价是破坏性操作 + 台账 SHA 全面失配),除非你有合规上的硬要求。
- 若要清洗,请明示"确认改写历史并强推",我再执行并同步回写两份台账里的 SHA 引用。

## T-10 【顺手项:一次手机访问可同时关掉 R-016 的挂账】
R-016(execute,`updated_at` 2026-09-13)的 **step-3「真机上传 + reqId 对账」仍 `in_progress`,
已挂 14 天**,卡的正是"用手机访问一次本机页面"——与 T-1 是**同一个动作**。
`MobileView.vue`(`/m`)在同一次会话里既发 `pose.*` 也发 `upload.*` 的 `evt=mobile.diag`,
所以按 T-1 打开一次手机页并上传,即可同时取得:
①T-1 需要的真人视频(→ R-018 step-5 / AC-6);
②R-016 step-3 需要的 `upload.*` reqId 往返对账(→ 解除其 in_progress、R-016 AC-3 可验收)。
**范围不合并**:两段证据分别写各自需求的 `run-evidence/`,R-016 的收口仍按它自己的 plan 走
(不在 R-018 内代归档);本条只登记"一次采集、两处受益",避免你再跑第二趟。


