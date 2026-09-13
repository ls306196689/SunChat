# 模块设计:pose-skeleton(core/pose_skeleton.py)

需求: R-017 | 触发: FR-4 | 日期: 2026-09-13 | 状态: draft r1

## 对外接口
```python
def select_key_frames(result: PoseResult, k: int = 4) -> list[tuple[int, str]]:
    """按相位代表性选帧 → [(帧下标, 相位标签)];相位∈{initial_contact, midstance,
    toe_off, swing}。同一视频内各帧相位尽量互异。"""

def draw_skeleton(rgb_frame: np.ndarray, landmarks: list[LM]) -> np.ndarray:
    """33 点 + mp 官方连线(躯干/四肢)叠加到 RGB 帧,返回新帧。"""
```

## 能力说明
- 提供:选帧策略 + 骨架绘制(纯函数,输入输出均为内存对象)。
- 不提供:落盘/文件命名(P4)、JPEG 编码参数外的任何副作用。

## 内部关键逻辑
1. 选帧:遍历 `result.cycles`,对每个相位收集事件时间戳,映射到 `sample_ts` 最近帧;
   优先首个完整周期;不足 k 相位用周期中点(swing)补足;帧去重。
2. 绘制:PIL 线段宽 2,关节点半径 3;颜色约定:触地侧腿红(#e11d48),摆动侧绿(#16a34a),
   躯干白,骨盆连线加粗——让左右腿状态一眼可辨;不画面部点。
3. JPEG quality=85 编码由 P4 调用侧 `.save(buf,'JPEG')` 完成,本模块只给 ndarray。

## 依赖
- P1 pose-core:`PoseResult`/`Cycle`/`LM` 类型(仅接口名,见 pose-core.md)。
