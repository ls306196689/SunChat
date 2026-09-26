# R-017 step-8 活体验收(进行中)
- [x] 后端重启(setsid 脱离;旧 uvicorn 382120 已替换),extra 列迁移日志"数据库初始化/迁移完成"
- [x] 活体拒析链:垃圾魔数→400 "不支持的视频格式";纯色无人体 avi→400
      "关键点置信度不足(conf=0.00,检出率=0%)。拍摄要点:…"(真 MediaPipe 推理已发生)
- [x] POST /chat/video/pose 端点注册+health 200(evt=pose.analyze.run reason=bad_magic 日志见 sunchat_20260913.log)
- [ ] AC-1 真人侧跑视频→指标合理性(cadence 140~220):等用户实拍(剪影合成视频 mp 不检出,已验证属预期)
- [ ] AC-3 真机 /m 渲染证据(截图):等用户执行
- [ ] AC-3 骨架帧 /chat/images 回显 200:随 AC-1 一并进行
- [ ] AC-4 活体降级:当前会话模型即非 VL 语境,实拍完成时 report_source 应为 template(或切 VL 后 vl)
- 注:合成视频无法替代真人关键点检出(lite 模型对卡通剪影不敏感),真实视频豁免项按计划声明
- [x] AC-3 渲染层证据(OPT-011,headless iPhone-390x844+桌面1280x800,playwright DOM 断言+截图入本目录):
      mobile_has_pose_btn=true / guide_modal=true(弹出且含路跑+跑步机双支)=guide_two_scenes /
      guide 取消关闭=true / desktop "🏃 跑步分析"按钮=true
      (截图 mobile_pose_guide.png / desktop_pose_btn.png)

## v2 活体冒烟(2026-09-26 10:3x,后端今日重启载入 HEAD 代码,health 200)
- [x] 全量单测终态基线:`cd backend && python -m pytest tests -q` → **340 passed, 1 skipped**
      (无回归,与 step-6 基线一致;R-11 修复前该数字为 v2 代码态终测参照)
- [x] 垃圾魔数→400 "不支持的视频格式"(1.2ms,R-11 排查后的复测)
- [x] 纯色无人体 avi(320x240@15fps 2s 真编码+真上传)→400 "关键点置信度不足(conf=0.00,
      检出率=0%)。拍摄要点…"(536ms,粗扫真 MediaPipe 推理发生,low_conf 链正确)
- [x] evt 日志对应 `evt=pose.analyze.run result=fail reason=bad_magic / low_conf`
      (logs/sunchat_20260926.log)
- [x] 运行态=HEAD 确认:进程启动 09:31 晚于 chat.py mtime 09-14 02:04;openapi 含
      /api/v1/chat/video/pose;git push 实测 "Everything up-to-date"(origin/master=61fd2b51)
- [x] /m 移动端在服:snapshot 见底栏「🏃分析」按钮;历史真人跑姿报告(消息246)含骨架图回显
- [ ] ⛔AC-1/AC-3 真人实拍对账:**前置阻塞 R-11/A-5**(旋转元数据未应用,人体在帧内横躺,
      竖直法量错轴)——2026-09-26 查证入档 analysis.md A-5 + state R-11(occurred)。
      实拍前需用户在 §A-5 三条路径中定序,详见 checkpoint.md「step-8 等用户」节

## v2 活体冒烟(2026-09-14 02:15,后端已重启载入 v2 代码,health 200)
- [x] 垃圾魔数→400 "不支持的视频格式"(v2 流水线未破坏 bad_magic 快速拒绝,真推理未启动)
- [x] 纯色无人体 avi(320x240@15fps 2s 真编码+真上传)→400 "关键点置信度不足(conf=0.00,
      检出率=0%)。拍摄要点…"——v2 粗扫真 MediaPipe 推理发生且 low_conf 链正确(0.49s 完成)
- [ ] AC-1/AC-3 真人侧跑:等用户实拍(v1 遗留,稀释 bug 已 step-3 修+AC-7 永久护栏;
      v2 预期:报告带"跑动分析段 Xs(站立/走位段已剔除)"透明度行,骨架帧为裁剪版)
- [ ] AC-4 活体降级(随实拍:当前 ollama 模型非 VL → report_source=template)
- 身高配速对账(可选):POSE_USER_HEIGHT_CM=175 重启后实拍视频应出 pace 三态之一

