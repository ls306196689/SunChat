# R-016 执行计划

需求: R-016 | 类型: bugfix | 日期: 2026-09-13 | design-change.md v1(arch/design 双门禁确认)

## 步骤表
| id | 目标 | 模块 | 上下文清单 | 产出 + 验证方式 | 关联风险 |
|---|---|---|---|---|---|
| 1 | 后端:diag 端点 + 静态托管缓存治理 | backend/app/api/v1/routes/diag.py, main.py, tests/test_diag.py, tests/test_mobile_pair.py | design-change.md §对外接口(diag/静态托管) + design/modules/mobile-pair.md 对外接口节 + tests/test_mobile_pair.py(既有双态范式) | diag.py 新路由 + main.py(no-cache/ assets404止投毒)+ 注册;验证: `pytest tests/test_diag.py tests/test_mobile_pair.py -q`(AC-1→test_diag_ingest/test_diag_truncate_400/test_diag_evt_line;AC-2→test_index_no_cache/test_assets_missing_404_json/test_root_no_cache)后 `pytest tests/ -q`(AC-6→全量276+收集零回归) | R-1,R-3 |
| 2 | 前端:mobileDiag 诊断通道 + 上传规范化/超时 + 埋点 | frontend/src/utils/mobileDiag.js, utils/request.js, pages/MobileView.vue, scripts/r016_check.mjs | design-change.md §mobileDiag/埋点/multipart/超时 + R-016/requirements.md FR-2/4/5 + AC-4/AC-5 + r015_check.mjs(断言范式) | mobileDiag.js(缓冲/flush/补发/err序列化)+ request.js(三处删显式CT+upload 20s)+ MobileView 埋点(reqId 贯穿);验证: `node scripts/r016_check.mjs`(AC-4→test_no_explicit_multipart_ct;AC-5→test_upload_timeout_20s;FR-2→test_diag_module_contract/test_flush_triggers_present;先 npm run build 后跑,新签名断言—OPT-012)+ `npm run build`(AC-6)+ r014/15_check 复跑(AC-6) | R-2,R-4 |
| 3 | 真机 RUN:手机上传全链路 + reqId 日志对账 | 集成 | R-016/AC-3 + run-evidence 采集约定(OPT-011) | 用户手机实拍上传(成功或失败均产生 diag 日志);`grep mobile.diag backend/logs/sunchat_$(date +%Y%m%d).log` 截图存档 `R-016/run-evidence/`(AC-3 渲染层证据:事件行与 http.post 对账表);失败若复现据一手错误对象定位并回步 2 调试协议 | R-3 |

## 豁免声明
无豁免:三步均含验证单测(后端 pytest/前端静态断言等效单测沿用 R-014/015 仓例
无 vitest 先例)/真机对账。

## AC→用例映射总表
AC-1→test_diag_*;AC-2→test_index_no_cache/test_assets_missing_404_json;
AC-3→步骤3真机+日志对账;AC-4→test_no_explicit_multipart_ct;AC-5→
test_upload_timeout_20s;AC-6→全量 pytest+build+三 check。
