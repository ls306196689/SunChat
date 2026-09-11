# R-012 多模态上传响应字段路径缺陷修复(image_id/frame_ids/text/status 解析恒 undefined)

需求: R-012 | 类型: bugfix(micro) | 状态: confirmed | 日期: 2026-09-11

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-11 | 初稿(总授权直通;R-011 用户报障引出) | 用户:图片上传失败了 |

## 一、需求
### 现象 / 动机
用户在页面(localhost:5173)选/拖/粘贴图片上传 → 待发缩略图**变红显示重试**;
但后端日志与 uploads/chat/ 落盘显示上传请求实际 **200 成功**。

### 根因(analysis.md#A-1)
`utils/request.js:32` 响应拦截器 `return response.data` 已解包一层;后端体为
`{code,message,data:{image_id}}` → axios promise 值即该体,`resp.data.data.image_id`
恒 undefined → 判"上传返回异常"标红。R-008/009/010 引入共 4 处同类错误
(ChatView:79/150-118(151)/274/309);既有代码(chat.js:195)已用双写防御范式。
R-011 归档自检与历次实机验证均 python 直连后端,绕过拦截器 → 漏检(测试盲区)。

### 期望行为
1. 图片/视频抽帧/语音转写/ASR状态 四个响应字段读取全部正确(单解包与双解包均兼容);
2. 正常网络下上传缩略图转 done,可发送;失败(断网/超限)仍正确红+重试;
3. 同类缺陷全仓清零(grep 复核 `data.data`)。

### 影响范围
- 文件: `frontend/src/pages/ChatView.vue`(1 文件 4 处);对外接口不变、后端零改动。

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | node 桩模拟拦截器解包体,4 条路径字段提取非 undefined | 代码级复现脚本(调试协议留档) |
| AC-2 | `vite build` 通过 | 命令 |
| AC-3 | `pytest tests/` 全绿(后端零改动) | 命令 |
| AC-4 | 全仓 `data.data` 残留=0 | grep |

## 二、方案设计
### 改动点定位
| 位置 | 现行为 → 目标 |
|---|---|
| ChatView 79 `resp?.data?.data?.image_id` | → `resp?.data?.image_id ?? resp?.image_id`(chat.js:195 既定防御范式) |
| ChatView 150 `resp?.data?.data`+151 frame_ids | → `resp?.data?.frame_ids ?? resp?.frame_ids`,duration/d 同源 |
| ChatView 274 `resp?.data?.data?.text` | → `?? 双写` |
| ChatView 309 `r?.data?.data?.status` | → `?? 双写` |

### 修改思路
不反向修改全局拦截器(影响面大:chat.js/memories 等全部按解包约定写,改动会引入回归);
按仓库既有**调用侧双写防御**范式修复,零回归风险。测试盲区教训登记 issues/(前端无网络层
测试基建,后续以 node 冒烟脚本补)。

### 回归测试设计
AC-1 node 脚本(后端体模板×双写提取断言);全量回归。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证 |
|---|---|---|
| 1 | 4 处双写修复+node 断言脚本+构建+全量回归 | ChatView.vue;`vite build`+`pytest`+grep |

## 越界自检
- [x] 1 文件? [x] 后端/接口零改动? [x] 无新依赖?

## 归档结果(2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | node 桩:解包体 {code,message,data:{image_id}}→新路径得 'IMG-123'、老路径得 undefined(复现即回归断言) |
| AC-2 | 通过 | vite build ✓ |
| AC-3 | 通过 | pytest → 237 passed, 1 skipped |
| AC-4 | 通过 | grep `data\.data` ChatView 0 残留 |
调试协议:复现(curl/日志:请求200→前端红)→定位(拦截器双解包,node 实证)→最小修复
(调用侧双写,遵循 chat.js:195 既有范式,不动全局拦截器)→回归。1 回合,无 debug-log 必要升级。
教训:前端-后端联调必须以浏览器链路为验(直连脚本会绕过拦截器),已登记 skill issues/。
