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

D-2 处置第2回合(step-3b 落地):
UA对账实锤:14:26 iPhone(192.168.1.3, iOS16.1 Safari)拉 /m+css+新JS 全200,之后
sessions GET/canary 前置版(page.enter)零到达→JS未执行或未初始化。静态体检:esbuild
safari15 解析OK,toSorted 仅 core-js polyfill 内部非调用面。根因判定需真机一手证据,
但诊断通道依赖应用JS 自身→部署内联 canary(见 commit 1326e435):canary/js.error/
js.hung 三态探针,sendBeacon+fetch 双保险。等待真机对账:①canary未到=网络层断(另案);
②js.error=真因(消息+行列号)即修;③js.hung=应用挂起,查 init 链;
④page.enter 到+一切正常=此前为旧页残影/缓存路径问题(已被 step-3 治理)。
预算:本回合为 D-2 第2也是最后调试回合(plan execute §5.4),仍 blocked 则升级 question。

D-2 处置第3回合(15:04,入口标记+资源错误上报已部署 index-BfUqk5CD):
iPhone 新证据链:canary(ver=1.1.0)全到达(网络/post正常);js.error "Script error.@:0:0"
(page=/,ACAO已上线仍遮蔽);/m 两次仅 canary 即无后续(hung 2.5s 定时器未触发即离开
页面,或 iOS 后台杀 fetch)。桌面 Firefox 出现 ver=1.0.0 的 canary+完整 entry(挂载
成功)——旧 HTML 无 no-cache 入缓存的新鲜期证据(Safari 同理)。
判读装置:main.js import 头 entry.import.ok/挂载 app.mounted(Vue errorHandler→vue.error);
resource.error(元素级加载失败含文件名);js.hung 附 performance 资源尾部清单。
下一步:用户 iPhone 关闭全部旧标签 → Safari 设置-清除该网站数据(或用无痕)→
访问 http://192.168.1.47:8000/m?v=2。预期:①entry.import.ok+app.mounted=修复达成;
②仅 canary=资源加载层;③js.error 明文=执行期根因。
