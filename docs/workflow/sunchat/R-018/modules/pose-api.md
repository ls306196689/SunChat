# 模块设计:pose-api 端点朝向透传(routes/chat.py)

需求: R-018 | 触发: FR-4, FR-5 | 基线: R-017/modules/pose-api.md
状态: draft r1 | 日期: 2026-09-26

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-26 | `_frames_at_ts` 增 `rot` 参数并 `np.rot90` 转正;端点把 `result.orient["rot_k"]` 传入;evt 日志 fields 增 `orient`/`orient_conf` | FR-4/FR-5 |

## 对外接口
```python
def _frames_at_ts(data: bytes, target_ts: List[float], rot: int = 0
                  ) -> List[Optional[np.ndarray]]:
    """单次解码取最近帧;rot∈0..3 时对每张帧 np.rot90(与 analyze_video 同一 k)。
    默认 0 → 既有调用/测试逐值不变。越界按 0(与 sample_frames 同规则,永不抛)。"""

@router.post("/chat/video/pose")   # 路径/请求体/响应结构均不变(仅 quality 增两键)
```
响应 `data.quality` 因 P1 增键而多 `orient`/`orient_conf`(向后兼容:前端只读
`report`/`frame_ids`,`extra` 内 quality 由 `json.dumps` 直出,无解包断言)。

## 能力说明
- 提供:骨架帧取帧与指标分析**同一 k**(FR-4 契约在 P4 侧的落点);朝向进日志。
- 不提供:在端点内判定或纠正朝向(判定唯一落点 P1);`core/video.py` 视频对话路
  的朝向处理(→ R-019);响应新增字段(除 quality 内增键)。

## 内部关键逻辑
1. **k 的来源与传递(唯一关键线)**:
   ```
   result = analyze_video(data)                      # P1 内部已用 k 转正粗扫+密采
   k = int((getattr(result,"orient",None) or {}).get("rot_k", 0))
   frames_at = _frames_at_ts(data, want_ts, rot=k)   # ← 忘记传 = 骨架回横躺(AC-5 负例钉住)
   draw_skeleton(rgb, result.landmarks_seq[idx], crop_bbox=result.crop_bbox)
   ```
   `orient` 缺失(老 result / mock)→ `k=0`,与 v2 行为一致(R-7 缓解:全 `.get()`)。
2. **拒析路径不变**:`PoseQualityError` 的 reason 集合不增项(FR-6),`_POSE_REJECT_HINT`
   文案不改;`undetermined` 不产生任何 HTTP 层面差异。
3. **日志(FR-5)**:`evt=pose.analyze.run` 的 ok 与 fail 两路 fields 均增
   `orient=<90cw|undetermined|…>`、`orient_conf=<0.83>`(fail 路 analyze 抛异常时
   无 result → 该两字段省略,不抛)。既有字段一视同仁保留(R-017/step-6 契约)。
4. **不做二次解码**:仍在同一次 `_frames_at_ts` 解码内 `np.rot90`,不重开容器。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| pose-core | `analyze_video`, `PoseResult.orient`, `sample_frames(rot=)` | R-018/modules/pose-core.md |
| pose-skeleton | `draw_skeleton`, `select_key_frames`(k 不变) | R-018/modules/pose-skeleton.md |
| pose-report | `build_report`(透明度行自动生效) | R-018/modules/pose-report.md |

## 回归断言(归入 backend/tests/test_pose_api.py)
- AC-5:mock `analyze_video` 返回 `orient={"rot_k":1,…}` → 断言 `_frames_at_ts` 收到的
  `rot==1`,且落盘骨架帧尺寸与转正后一致(横→竖)、报告含转正透明度行。
- AC-5 负例:`orient={"rot_k":0}` 且夹具为横躺 → 骨架帧仍横躺(证明"忘了传 rot"必失败)。
- AC-7:不带 `orient` 的 mock result → 端点 200 且行为与基线逐值一致(默认 k=0)。
