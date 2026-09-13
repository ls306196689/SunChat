# R-016 调试日志

## D-1 diag 端点 405(resolved)
复现:pytest test_diag 405 → 假设:路由未挂 → 证据:citation main.py 只 import 未
include_router → 修复:补挂 `app.include_router(diag.router,...)`;回归 test_diag 5例绿。

## D-2 AC-3 首次真机:矛盾证据(处理中)
现象:用户称"上传了照片"且"界面正常能操作(Safari/Chrome)",但 14:07/14:08 手机侧
GET /m+新包 CWZxY4K1 到达后,**page.enter 诊断与 chat/sessions GET 均未达**。
推断:若 UI 渲染则 diagInit 必执行→fetch 同源于已通 GET→"UI 正常"与"零 API 调用"矛盾。
候选:①"界面正常"观测其实发生在电脑浏览器(桌面同源可开 /m);②手机页面为旧会话残影。
处置:中间件 evt=http 增 client IP+UA 字段(对账探针),重启服务,请用户做一轮
标注设备来源的干净测试(手机新开标签页)。≤2 回合预算内。
