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
