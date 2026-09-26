# R-018 checkpoint(需求 v1 已写,待冻结门禁)
更新: 2026-09-26 11:50 | 上下文快照,新会话优先读本文件 + state.json

## 需求主线
- R-018 跑姿抽帧朝向归一化,req_type=bugfix(影响>2 文件+quality 增键 → 标准流程,非 micro)
- phase=requirements(v1),change_count=0,gates=[](**requirements_confirmed 尚未取得**)
- 来源:R-017 step-8 实拍前置核查暴露的 R-017/risks[R-11](occurred);
  用户否决"在 R-017 走 v3"(影响 4 已完成步骤触发熔断),明示**新开 R-018**
- git: master,已 push 至 **cfc77c0d**(远端已同步)

## 用户明示指令(验收基准,不可偏离)
> "横屏竖屏不能作为旋转依据。要识别人的朝向。以人头上脚下为基准来控制旋转。"
→ FR-1/FR-2:**禁**用画面宽高比、**禁**用容器 rotate 元数据、**禁**用"某朝向能否检出
MediaPipe"作判据;只用检出人体自身头脚轴。身高 **173cm**(配速对账用,POSE_USER_HEIGHT_CM)。

## 取证要点(细节见 analysis.md A-1~A-6,勿重复实验)
- PyAV 17.1.0 `to_image()` **不应用** rotate 元数据(合成 mp4 实证:metadata 无 rotate/
  side_data=None/尺寸仍 640×480)
- 真人落盘帧(消息246)pipeline 自采帧内人体**横躺**:肩中点→髋中点偏离竖直 89.8~92.9°,
  bbox 高/宽 0.28;转正后 3.68。qwen2.5vl 独立复核一致
- 污染定量:踝真振荡轴 y→x;body_ratio 0.306→0.152(门槛0.12,误拒风险);
  pelvic_tilt +1.0°→+91.4°(落库 -42.1/-31.9/-28.4 同量级)
- **A-4 设计关键约束(勿重蹈)**:四向试探取"可检出者"必选错——真人帧真 upright 档在
  生产门槛 0.5 **检不出**(降到 0.15 才出且 vis 仅 0.70),错误朝向也能检出并给反向几何
  → 判朝向只能在**给定一次检出**的关键点上算几何
- **A-5 实现依据(实测通过)**:`u=单位化(肩中点−髋中点)`,180°歧义用"鼻在 u 上的符号"
  消解,量化到最近 90°;4 横躺帧一致判 270°CCW(=CW90),正立帧 238-A 判 0°;
  |肩-髋|=113~134px,偏角 -87~-95°,距档位边界裕度 >10°

## 下一步(门禁顺序)
1. ⏳**requirements_confirmed**(question,禁 blanket)← 当前卡这里
2. architecture/design:R-018 是 bugfix 增量,`design-change.md` 写增量(模块 P1 为主,
   P2/P3/P4 小改),门禁 design_confirmed
3. plan.md(六字段步骤表,含单测与关联风险)→ plan_confirmed → execute
4. execute 完 → **回 R-017 step-8** 做真人实拍对账(横屏+竖屏各一段)+ 全量终测 → 归档
   R-017(身高 173cm 出配速),然后归档 R-018

## 关键实现约束(实现时照做)
- 判定与转正的 k 值必须同时应用于**密采帧**与**骨架帧绘制/裁剪**(FR-4,防指标转正骨架仍横)
- 不可定向导:`orient="undetermined"` + `orient_conf`,**不转、不新增拒析理由**,
  报告透明度行打印"朝向不可定,指标可能失真"(FR-5/FR-6,避免与 R-3 门槛叠加误拒)
- quality 增键必须向后兼容:`q.get("orient")`,报告/日志/测试均用 get
- AC-4 必须有"元数据与宽高比解耦"断言:同内容伪装带 rotate=90 / 不带 / 竖幅 / 横幅,
  判定只随人体朝向变

## 验证命令
- `cd backend && python -m pytest tests -q`(基线 340 passed 1 skipped)
- 活体:curl -X POST localhost:8000/api/v1/chat/video/pose -F file=@run.mp4 -F session_id=1
- 服务在跑:uvicorn :8000(今 09:31 启,无 --reload → **改代码后必须重启**)、
  vite :5173(`/m` 移动端,`/api` 代理后端)
- 重启后端:`kill <pid>` 后 `cd backend && setsid --fork bash -c 'exec python -m uvicorn
  app.main:app --host 0.0.0.0 --port 8000 >> backend.log 2>&1 < /dev/null'`

## 环境事实(省得再探)
- 本机无摄像头、无系统 ffmpeg(可 `pip install --target /tmp/fftool imageio-ffmpeg` 取便携
  ffmpeg,已验证可用);外网 raw.githubusercontent/huggingface/googleapis(除 mediapipe-models)
  不可达 → **合成素材无法替代真人关键点检出**,AC-6 必须真人实拍
- 服务健康:`/api/v1/health`(非 /health,后者被 SPA fallback 吞);首次探活 ~11s 后缓存
- R-016 真机对账仍 in_progress(不阻塞本需求)
