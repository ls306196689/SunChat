# R-011 图片交互 UI 优化

需求: R-011 | 类型: iteration(micro) | 状态: confirmed | 日期: 2026-09-11

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| v1 | 2026-09-11 | 初稿(总授权直通) | 用户:优化图片交互逻辑特别是 UI |

## 一、需求
### 现象 / 动机
R-008/R-010 落地后的图片交互偏"能用":上传期间无反馈(慢网下缩略图空窗)、
失败仅 toast 无法重试且已占名额、拖拽无区域提示、待发区无计数、
消息气泡图片点击只是打开新标签(无灯箱/多图切换)。

### 期望行为(全部前端,后端接口零改动)
1. 待发图**状态机**:选择后立即以本地 objectURL 乐观展示(uploading 遮罩+spin);
   成功→换成服务端 url(done);失败→error 态(红色遮罩+"重试"按钮,重试不占新名额)。
2. **发送策略**:仅 done 图计入发送;仍有 uploading → 提示"图片上传中";
   存在失败图 → 提示可重试或忽略(忽略时移除失败图继续发)。
3. 待发区右上 **计数徽章**(n/4),达上限才禁用 📎/🎬(现状已如此,保持)。
4. **拖拽遮罩**:dragenter/dragover 时输入区显示"松开以添加图片"罩层,
   dragleave/drop 消失(计数引用法防子元素抖动)。
5. **气泡灯箱**:消息图片改 NImageGroup+NImage(lazy,click-to-preview 灯箱,
   多图左右切换、缩放旋转),替代裸 `<a><img></a>`。
6. objectURL 生命周期:移除图片/发送成功/组件卸载时 revoke,防内存泄漏。

### 影响范围
- 文件: `frontend/src/pages/ChatView.vue`、`frontend/src/components/ui/MessageItem.vue`(2 文件)
- 对外接口: 后端零改动(MUST);前端 payload 结构不变(images=image_ids[])
- 新依赖: 无(naive-ui NImage 已有)

### 验收标准
| 编号 | 标准 | 验证方式 |
|---|---|---|
| AC-1 | 待发图带 status 态机;uploading 显 spin 遮罩;失败显重试且原地重试成功转 done | 代码审查+构建+浏览器手测 |
| AC-2 | 仅 done 图发送;uploading 拒绝发送并提示;error 图不进 payload | 代码审查+构建 |
| AC-3 | 拖拽遮罩出现/消失正确(含子元素 dragenter 抖动防护) | 同上 |
| AC-4 | 气泡 NImage 灯箱:单击放大、多图切换、lazy | naive-ui 组件事义+构建 |
| AC-5 | objectURL 在 移除/发送/unmount 三路径 revoke | 代码审查 |
| AC-6 | 回归:`npx vite build` 退出码 0;`pytest tests/` 全绿(后端未动,零失败) | 命令 |

## 二、方案设计
### 改动点定位
| 位置 | 现行为 → 目标行为 |
|---|---|
| ChatView.vue:24 pendingImages | `{id,url,name}` → `{id,url,name,status:'uploading\|done\|error',localUrl,rawFile}` |
| ChatView.vue addImageFiles | 直接 await 上传 → 先 push optimistic(uploading+localUrl),完成换 url,失败标记+保留 rawFile 重试;removePendingImage revoke |
| ChatView.vue handleSend | 仅校验非空 → uploading 拦截提示/error 剔除后发送 |
| ChatView.vue 输入区模板 | 无遮罩 → dragActive 罩层;pending 缩略图三态样式+计数徽章 |
| ChatView.vue 卸载 | 无清理 → onUnmounted revoke 全部 localUrl |
| MessageItem.vue:msg-images | `<a target=_blank><img>` → `<n-image-group><n-image lazy>`(预览即灯箱) |

### 修改思路
状态机以数组元素 status 字段实现(轻量,无 store);拖拽遮罩用 enter/leave 计数器
防子元素事件抖动;灯箱用 naive-ui 既有 NImageGroup 的预览组能力,零自定义 lightbox。

### 回归测试设计
本需求为纯 UI 交互(无单测框架接入前端):以 `vite build` 硬门禁+后端全量 pytest
回归(证明接口面零触碰)+ AC 清单代码审查。理由:前端无测试基建,引入属架构决策
(超 micro 范畴)。

## 执行步骤(≤2)
| id | 目标 | 产出 + 验证方式 |
|---|---|---|
| 1 | 前端两文件改造 + 构建+回归 | vite build 0 + pytest 237 绿 |

## 越界自检
- [x] ≤3 文件(2)? [x] 未改后端/对外接口? [x] 无新依赖/架构决策? [x] 失败<2 次?

## 归档结果(2026-09-11)
| AC | 结果 | 证据 |
|---|---|---|
| AC-1 | 通过 | addImageFiles→reactive entry 状态机(uploading spin 遮罩/本地 objectURL 立显);error 遮罩"重试"按钮→retryUpload 原地重传(rawFile 保留,不占新名额) |
| AC-2 | 通过 | handleSend:pendingUploading 拦截 warning"上传中";error 图剔除明示"已忽略N张";仅 done 入 payload;发送失败回滚 sentEntries(已存服务端免重传);发送按钮 uploading 期禁用+文案"上传中…" |
| AC-3 | 通过 | dragDepth 计数器+types 含 Files 判定(图片/文本悬停不误触发);drop-overlay pointer-events:none;drop/dragleave 归零 |
| AC-4 | 通过 | MessageItem:n-image-group+n-image(lazy,preview-src,click 即灯箱,组内左右切换缩放);:deep(img) 尺寸样式保持缩略图观感 |
| AC-5 | 通过 | revokeEntry 三路径:removePendingImage / handleSend 成功 forEach / onUnmounted(globalThis 兜底 try) |
| AC-6 | 通过 | `npx vite build` ✓6.15s;`pytest tests/` → 237 passed, 1 skipped(后端零改动) |

调试记录(debug D-1,1 回合):首轮 build 失败 ChatView.vue:372——编辑遗留重复代码块
(`message.error('发送消息失败…」}×2 残留)删除修复;同轮发现 reactive 未导入(构建不报、
运行时 ReferenceError),补导入并以静态自检脚本验证 vue API 导入完整性。
观察项:tests/test_video.py::test_synthetic_avi_frames 全量首跑一次偶发红、隔离 8 连跑全绿
(R-010 遗留 seek 采样断言偏脆,与本次无关,登记留后续加固)。
越界自检:改动 2 文件✓ 后端零改动✓ 无新依赖✓。
chat-image 基线交互面变化(预览灯箱+待发三态),归档后追加基线注记。
