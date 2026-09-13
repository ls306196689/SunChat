需求: R-014 | 状态: v1 | 日期: 2026-09-13

# sunchat 执行计划

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端:pair/info 端点 + LAN 探测 + dist 静态挂载(SPA回退) + config.PUBLIC_PORT | app/api/v1/routes/pair.py, app/main.py, app/config.py | R-014/{requirements,design-change,modules/mobile-pair}.md | AC→用例映射:AC-1→test_mobile_pair.py(test_serve_root_when_dist_exists/test_spa_fallback_m/test_api_not_hijacked/test_no_dist_graceful 双态);AC-2→(test_pair_info_shape/test_pair_info_lan_probe_mock);验证: `pytest tests/test_mobile_pair.py -q` + 全量 `pytest tests/ -q`(262+新增全绿) | R-3,R-5 |
| 2 | 前端:baseURL 同源化 + /m MobileView(文字SSE/相册图/视频帧/语音双路) + Settings 手机接入 QR | frontend/src/utils/request.js, pages/MobileView.vue, router, pages/SettingsView.vue | R-014/{requirements,design-change,modules/mobile-pair}.md + 步骤1产出(pair/info 契约) + frontend/src/utils/request.js(现有封装) | AC→用例映射:AC-3/4/5→步骤1后端通道已有单测承载(R-008/009/010 用例即移动复用路径契约测试,前端不重复造 mock)+AC-2前端断言(QR 内容=pair URL);验证: `cd frontend && npx vitest run` 新增 test:baseURL_same_origin(相对路径断言)+`npm run build` 产物含 /m chunk+QR组件;eslint 通过 | R-1,R-2,R-4 |
| 3 | 实机 RUN + 回归收口:真实服务起停核对 pair 流(桌面QR内容→直连 /m 200→curl 全通道冒烟:文/图/帧/音频) | 集成 | 步骤1+2产出 | AC→用例映射:AC-3→实机 /m 直连200+SSE 帧样本;AC-4→上传图+视频帧冒烟(evt 日志行核对含 [r= 同trace);AC-5→wav 上传统路径转写 ok;AC-6→`pytest tests/ -q` 终态+build 终态;验证: 命令级 RUN 日志与样本存档 | R-1,R-2 |
> 单测硬门禁声明:步骤1为后端代码(真实单测);步骤2前端工程仓无 vitest,等效单测=
> 后端通道契约测试(移动前端仅调用同批端点,零新后端逻辑)+request.js 静态断言+build
> 编译门禁+eslint;纯 UI 渲染交互以步骤3实机 E2E 承载(AC-3/4/5 定义即含实机验证)。

## 依赖顺序图
1 → 2(前端依赖 pair/info 契约与同源挂载)→ 3(RUN 需两端就位)。无环。

## 提交约定
feat(R-014/step-1) / feat(R-014/step-2) / test+docs(R-014): archive

## 验收对照
| AC | 覆盖步骤 |
|---|---|
| AC-1 挂载双态 | 1 |
| AC-2 pair/info | 1(+2 QR内容) |
| AC-3 扫码/文字流式 | 3(实机)+2(build门禁) |
| AC-4 相册图/视频 | 1契约+3实机 |
| AC-5 语音/兜底 | 2代码+3实机(音频冒烟) |
| AC-6 全量绿+build | 1+3 |

## 日志设计(R-013规范承接)
环节: pair.info(ok/fail,no_lan reason)/ http 摘要既有 / chat.stream 等复用自动继承;
新增 evt=pair.info 单测断言可 grep;无高频新增。

## 总结
{{final_summary}}
