# sunchat 执行计划

需求: R-018 | 状态: 待确认(plan_confirmed) | 日期: 2026-09-26

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | `detect_orientation()` 纯函数 + `POSE_ORIENT_*` 三参 + `sample_frames(rot=)` | P1 pose-core, config | `R-018/modules/pose-core.md`(接口节+内部逻辑 1/2)、`backend/core/pose.py`(sample_frames 节)、`backend/app/config.py`(POSE_ 组)、`backend/tests/test_pose_core.py`(夹具 `_gait`/`_patch`) | pose.py 新增 `ORIENT_MAP`/`detect_orientation`;config 增 3 参数;`sample_frames` 增 `rot`(np.rot90,越界归 0 不抛)。验证: `cd backend && python -m pytest tests/test_pose_core.py -q`,新增 `TestOrientation`:**AC-1** 夹具整体旋转 90°→`rot_k` 对应档且 θ 稳定;**AC-2** 正立→`orient="0"`;**AC-3** 三分支(全 None / 有效帧<3 / θ 落 45° 边界带)→`undetermined`+`rot_k=0`;**AC-4** 解耦:同一关键点内容分别喂 640×480 与 480×640 的 `frame_hw`、并断言函数源码不含 `metadata`/`side_data`/`W>H` 判据(grep 级);rot 越界(-1/4)→等价 0 不抛。**先跑既有全文件确认无破坏再补新用例** | R-1, R-2 |
| 2 | `analyze_video` 插入判向环节 + 粗扫重跑 + 门槛转正系 + `PoseResult.orient`/quality 增键 | P1 pose-core | `R-018/modules/pose-core.md`(内部逻辑 3/4)、`R-018/design-change.md`(第三/五节)、`backend/core/pose.py`(`analyze_video` 全体) | 流水线:粗扫(rot=0)→关键点→`detect_orientation`→`k≠0` 则粗扫帧 `np.rot90`+重跑关键点→门槛→locate→密采(`rot=k`)→指标零改动;`PoseResult` 增 `orient`;quality 增 `orient`/`orient_conf`。验证: `cd backend && python -m pytest tests/test_pose_core.py -q` — **AC-1** 横躺注入(注入面把关键点几何旋 90° 且喂 k 转正)cadence 回到正立夹具同值 ±5%;**AC-2** 正立夹具逐值等于插入前基线(先记录基线再比对);**AC-3** undetermined 不转**不新增拒析**(同夹具降样本→仍正常出指标);**FR-7** 横躺转正后 `body_ratio` ≥ 0.25(不误拒);既有用例全部零改动通过 | R-3, R-6, R-7 |
| 3 | P4 端点同-k 取帧 + evt 字段;P3 透明度行 | P4 routes/chat.py, P3 pose_report | `R-018/modules/pose-api.md`、`R-018/modules/pose-report.md`、`backend/app/api/v1/routes/chat.py`(`/chat/video/pose` + `_frames_at_ts`)、`backend/core/pose_report.py`(`transparency_lines`)、`backend/tests/test_pose_api.py`、`backend/tests/test_pose_report.py` | `_frames_at_ts(data, ts, rot=0)` 内 `np.rot90`;端点 `k=result.orient.get("rot_k")` 传入;evt ok/fail 两路 fields 增 `orient`/`orient_conf`;`transparency_lines` 首位插朝向行(三态文案,正立不打印)。验证: `cd backend && python -m pytest tests/test_pose_api.py tests/test_pose_report.py -q` — **AC-5**:mock `orient={"rot_k":1}` → 断言 `_frames_at_ts` 收到 `rot==1` 且落盘帧尺寸横→竖(负例:`rot_k=0` 时同样夹具必须仍为横幅,证明忘传必失败);**AC-3 文案**:报告含"朝向不可定"且指标段照常;**FR-5**:evt 行含 `orient=`;**AC-7**:老 result(无 orient 键)行为逐值不变 | R-5, R-7 |
| 4 | 全量回归 + 活体冒烟(带 rotate 元数据的合成 mp4 过端点) | 全部 | `R-018/design-change.md`(第八节)、`backend.log` | 验证: `cd backend && python -m pytest tests -q`(基线 340 passed 1 skipped,**AC-7**);便携 ffmpeg 造 3 组同内容 mp4(带 `rotate=90` / 不带 / 竖幅)打端点 → `quality.orient` 只随人体朝向变(活体面 AC-4);`/api/v1/health` 200;改码后重启 uvicorn 并核对 `total_ms` 未劣化(R-6) | R-4, R-6, R-7 |
| 5 | 真人实拍对账(与 R-017/step-8 合并执行) | P1/P4 端到端 | `R-017/plan.md`(step-8 节)、`R-017/run-evidence/step8-live.md`、`R-018/requirements.md`(AC-6) | 用户手机实拍侧跑**横屏 + 竖屏各一段**(身高 173cm)→ 端点实测:`orient` 非 undetermined、cad∈[140,220]、骨架帧人正立、报告含转正透明度行、配速出数并给±20% 级对账;结果写 `R-018/run-evidence/live-reconcile.md` 并回写 R-017/step-8 状态。**需用户提供素材**(本机无摄像头,合成无法替代真人检出) | R-1, R-2 |
| 6 | 归档准备:基线回写 + 两需求验收总结(归档节点须单独 question,禁 blanket) | 文档 | `R-017/plan.md`、`R-018/plan.md`、`docs/workflow/sunchat/design/`、`baseline.md`、`INDEX.md` | `design/modules/pose-*.md` 回写 R-017+R-018 合并终态;`baseline.md` 增朝向归一化段;INDEX 两行置 done;`compliance.sh archive` 两侧 FAIL=0;全量测试摘要入档 | R-4 |

## 豁免声明
- step-5:真人实拍素材豁免单元测试——本机无摄像头且外网不可达(无法下载公开跑步素材),
  合成素材不能产生真人关键点检出(R-018/analysis A-2/A-4);由端到端活体对账承担,
  证据形态为 run-evidence 文档 + 落盘骨架帧。判定/转正逻辑本身在 step-1/2 已有全单测覆盖。
- step-6:纯文档步骤,豁免单测(以 step-4 全量摘要作为测试证据)。

## 依赖顺序图
```
1(纯函数+rot 参数) → 2(流水线接入) → 3(P4/P3 透传) → 4(全量+活体冒烟) → 5(真人实拍,需用户素材) → 6(归档)
```
step-1 与 step-2 不合并:step-1 是可独立单测的纯函数,step-2 改主流程(回归面最大),
分开提交便于二分定位。step-3 依赖 step-2 的 `PoseResult.orient` 字段。

## 提交约定
- step-1/2/3: `feat(R-018/step-<id>): <目标>` + 敏感自检 + push
- step-4/5: 以文档+证据为主,有代码修补则 `fix(R-018/step-<id>): …` + push
- 文档节点: `docs(R-018,<scope>): …`(gates / plan / run-evidence / archive)

## 验收对照(对应需求 §验收标准)
| 需求验收项 | 覆盖步骤 |
|---|---|
| AC-1 横躺夹具判档 + cad 回真值±5% | 1(判档), 2(指标) |
| AC-2 正立逐值不变 | 1, 2 |
| AC-3 undetermined 不转不拒 + 降级文案 | 1(逻辑), 2(不拒), 3(文案) |
| AC-4 元数据/宽高比解耦 | 1(单测+grep 禁用项), 4(活体三组) |
| AC-5 骨架+crop 同坐标系(含负例;R-017/AC-10 裁剪断言同族扩展) | 3 |
| AC-6 真人横屏/竖屏实拍 | 5 |
| AC-7 全量零回归 | 1/2/3(各自文件级)+ 4(全量) |

## 总结
> 归档时填写:产出清单、与验收逐条核对结果、全量单测摘要(总数/通过数)、风险终态表。
{{final_summary}}
