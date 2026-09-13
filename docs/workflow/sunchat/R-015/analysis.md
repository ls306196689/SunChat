# R-015 分析:手机扫码端缺陷取证

范围:frontend App 壳/路由/MobileView/SettingsView/vite 配置 + R-014 归档证据 + 实机 curl。
立题:手机打开 /m 的显示缺陷根因为何?R-014 验收为何未拦截?

## A-1 /m 被桌面壳包裹(主缺陷根因)

证据:
- [CODE] frontend/src/App.vue:44-60 — 模板无条件渲染 `Sidebar`(n-layout has-sider)
  + `HeaderBar` + `router-view` + `app-footer`,无路由分支;
- [CODE] frontend/src/App.vue:77-86 — `#app{height:100vh;overflow:hidden}`、
  `.app-layout{height:100vh}`;
- [CODE] frontend/src/App.vue:100-105 — `.content-wrapper{flex:1;overflow:hidden}`;
- [CODE] frontend/src/pages/MobileView.vue:222 — `.mv{height:100dvh}`;
- [CODE] frontend/src/components/layout/Sidebar.vue:67-76,89 — `isMobile(<768px)` 时
  `collapsed=true`,而 `n-layout-sider :collapsed-width="64"` → 手机视口仍占 64px 黑条;
- [CODE] frontend/src/App.vue:107-114 — `.app-footer`("SunChat v1.0.0 本地运行中")
  无条件渲染,/m 场景出现桌面底栏;
- [CODE] MobileView 自带 header(`mv-bar`,10:172)→ 与桌面 64px HeaderBar 双头叠加
  (标题还显示兜底"聊天",HeaderBar.vue:7-14 无 /m 映射);
- 算术:`.mv` 高 100dvh 处于 `content-wrapper(=100vh−64px header−footer−64px sider)` 内
  → 溢出被 overflow:hidden 裁切,输入区被顶出可视区风险。
- [REQ] R-014/FR(AC-3) — "手机扫码打开 /m:发文字→SSE 流式回复上屏";设计意图为
  轻量独立移动页;
- [DESIGN] design/modules/mobile-pair.md §对外接口 — MobileView 为 `/m` 单栏页,
  未声明桌面壳共存处理 → 设计遗漏(壳适配未列入模块职责)。

结论 C-1:R-014 只新增了路由与页面,未处理 App.vue 全局壳对 /m 的包裹,属实现
遗漏(设计基线亦未覆盖);手机打开 /m = 64px 黑侧条 + 双头部 + 桌面底栏 + 100dvh
溢出裁切。修复必须落在 App.vue 壳层(route 分支裸渲染 /m)。

## A-2 R-014 验收未拦截的原因

证据:
- [RUN] logs/backend-service.log — /m 200、assets 200、pair/info ok、SSE 通、
  wav 转写 200(仅 HTTP 层与接口层);
- [RUN] docs/workflow/sunchat/R-014/run-evidence/ — sse/evt 样本,无 DOM/截图层证据;
- [REQ] R-014/AC-3 验证方式列"实机手机 E2E",当时以接口链路+页面 200 替代。

结论 C-2:验收止步于"HTTP 200 + 接口链路",无渲染层检查,壳缺陷不在覆盖路径。
教训:移动端 UI 需求的 RUN 证据须含 DOM/视觉级确认(headless 截图或用户实拍)。

## A-3 vite dev 口 5173 手机不可达(次要使用坑)

证据:
- [CODE] frontend/vite.config.js:14-23 — server 无 `host: true`(仅本机监听);
- [RUN] `ss -tlnp` — 5173 监听 0.0.0.0(历史进程),但默认绑定语义不保证;QR 固定
  8000(pair.py:47 port 取 Host/PUBLIC_PORT,不含 5173);
- [CODE] SettingsView.vue 手机接入卡片 — 无 8000(生产)vs 5173(dev)提示。

结论 C-3:扫码固定 8000 正确;风险是开发态误导(手机扫不到 5173)。补一行文案即可,
不改配置(加 host:true 会把 dev 服务暴露到 LAN,违背 dev/生产分离,列为不做)。

## 假设区
- ⚠假设:手机端老版微信内核对 vite5 默认 target(es2020,`??` 转译后)白屏 —
  dist 内含 `??` 64 处但均为转译产物形态,真机白屏未复现。验证方法:真机打开
  192.168.1.47:8000/m;未验证前不作为改动依据。
