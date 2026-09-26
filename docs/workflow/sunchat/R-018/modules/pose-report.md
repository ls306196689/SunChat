# 模块设计:pose-report 朝向透明度行(core/pose_report.py)

需求: R-018 | 触发: FR-5, FR-6 | 基线: R-017/modules/pose-report.md
状态: draft r1 | 日期: 2026-09-26

## 修订记录
| 版本 | 日期 | 变更 | 触发 |
|---|---|---|---|
| r1 | 2026-09-26 | `transparency_lines()` 增朝向一行(转正/不可定两种文案);VL 路与模板路共用同一函数故双路自动同文 | FR-5/FR-6 |

## 对外接口
**签名不变**(引基线,不重复定义):
```python
def transparency_lines(result) -> list:      # 现有函数,行数 +0~1
def template_report(result) -> str: ...      # 不变(内部已拼接 transparency_lines)
def build_report(result, frame_b64s, *, llm=None, model=None, vision_ok=None) -> tuple[str, str]: ...
def summary_text(metrics: dict) -> str: ...  # 不变(朝向属"口径"不属"指标",不进 summary)
```
唯一改动落在 `transparency_lines()` 内部:读取 `result.quality.get("orient")` 追加一行。

## 能力说明
- 提供:把 P1 的朝向判定结论翻译成人话,注入模板报告与 VL 上下文两处(同一函数,天然同文)。
- 不提供:自行推断朝向(判定只在 P1)、朝向相关的规则建议(`_RULE_HINTS` 不动)、
  因朝向不可定而拒出报告或改指标(FR-6)。

## 内部关键逻辑
1. **插入位置**:朝向行放在 `transparency_lines()` **首位**(它决定其余所有口径的前提),
   在"分析帧率"行之前。
2. **文案(三态,逐值钉入单测)**:
   - `orient ∈ {"90cw","270cw","180"}` → `"画面已按人体朝向转正(头朝上,原为 {orient})"`
   - `orient == "undetermined"` → `"⚠人体朝向不可定,已按原始画面分析,指标可能失真"`
   - `orient ∈ {"0", None}` → **不追加行**(正立是本需求的默认预期,打印噪音;
     None = 老结果无该键,同不打印 → AC-7 既有断言不破坏)
3. **永不抛**:`quality` 非 dict、缺键、`orient` 为任意值 → 落入"不追加"分支。
   读取一律 `q.get("orient")`(R-7 缓解)。
4. **不新增 reject**:本模块无拒析能力,确认不改 `template_report`/`build_report`
   的分支结构(FR-6 由"根本没有分支"保证)。

## 依赖
| 模块 | 使用的接口名 | 其文档 |
|---|---|---|
| pose-core | `PoseResult.quality["orient"]`(只读,`.get()`) | R-018/modules/pose-core.md |

## 回归断言(归入 backend/tests/test_pose_report.py)
- AC-3 文案面:构造 `quality={"orient":"undetermined", …}` → 模板报告含
  "朝向不可定" 且指标段照常输出(不拒)。
- AC-5/FR-5:`quality={"orient":"90cw"}` → 报告含"已按人体朝向转正";VL 路 mock 断言
  上下文串同样包含该行。
- AC-7:既有 `transparency_lines` 用例(无 orient 键)输出**逐值不变**。
