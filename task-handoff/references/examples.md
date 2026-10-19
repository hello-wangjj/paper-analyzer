# 样例与反例

> 样例中的路径、sha、行号是虚构的，直接跑 `check` 会报不可达；它只用来对照格式与详略。

## 完整样例：tool-switch

任务在两台客户端之间换手，产物在仓库里，没有未落盘的草稿。

```markdown
---
handoff: 1
task: kf-dt-adaptive
title: KF 过程噪声按 dt 自适应
status: waiting
boundary: tool-switch
from: WorkBuddy/claude-sonnet-4.5
to: Codex/gpt-5
updated: 2026-10-17T19:40+08:00
project_root: C:/Users/wangj/Documents/gitworkspace/Radar_track
branch: feat/kf-dt-adaptive
head: 9f3c2ab
---

# 交接：KF 过程噪声按 dt 自适应

## 1. 目标与验收

**目标**：把 KF 的 Q 矩阵从常量改为按帧间 dt 计算，使 10 Hz 与 20 Hz 两种输入下的位置 RMSE 差距收敛到 5% 以内。

**完成判据**：

- [ ] `pytest tests/test_kf.py -k rmse` 全绿
- [ ] 同一段 rosbag 以 10 Hz / 20 Hz 分别回放，位置 RMSE 差值 ≤ 5%

**不在范围内**：

- 不改观测模型 H
- 不做自适应 R 估计

## 2. 当前状态

- [x] Q 的 dt 计算函数已实现 — 验证：`pytest tests/test_kf.py -k test_q_matrix` → 3 passed，exit 0
- [ ] 10 Hz / 20 Hz 对比回放 — 进度：10 Hz 已跑完，20 Hz 的 bag 还没找到
- [ ] 文档更新 — 未开始

## 3. 在途产物（verbatim）

- 文件：`src/kf/process_noise.cpp` @ `9f3c2ab` : `118-164` — dt 自适应 Q 的实现，当前分支唯一改动处
- 文件：`tests/test_kf.py` @ `9f3c2ab` : `40-88` — 新增的 test_q_matrix 用例

## 4. 已锁定决策

- **Q 用连续白噪声模型离散化** — 理由：dt 变化时协方差增长与物理一致，优于按帧缩放；影响：Q 参数从 3 个矩阵元素变成 2 个谱密度常数，标定流程要同步改

## 5. 已否决路径

- **按帧数线性缩放 Q** — 失败现象：20 Hz 下 RMSE 反而上升 12%，因为缩放没考虑 dt 的平方项；结论：不要再试线性假设

## 6. 环境与重建

| 项 | 值 |
|---|---|
| 运行时 | Python 3.13.12 + g++ 13.2 |
| 依赖 | `uv sync --extra test` |
| 环境变量 | `RADAR_BAG_ROOT`（值见密码库条目 `radar/bags`） |
| 构建 | `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j` |
| 测试 | `pytest tests/test_kf.py -k rmse` |

**已知环境坑**：

- Windows 下 CMake 必须用 Ninja generator，MSVC 工具链编不过 `-march=native`
- 回放脚本要求 LF 行尾，CRLF 会让 bag 解析器读错头长度

## 7. 授权与风险

**决策权**：Q 的数学形式已由 §4 锁定，改动需回来确认；测试与注释可自决

**可修改范围**：`src/kf/`、`tests/test_kf.py`

**禁止触碰**：`src/io/`、`include/radar/contracts.h`

**未决问题**：

- 20 Hz 的 bag 用哪一份 — 需要 王工 确认；当前按 `2026-09-30` 那份假设推进

**风险与阻塞**：

- 若 20 Hz bag 的时间戳有跳变，RMSE 对比会失真，需先做时间轴校验

## 8. 下一步

**第一步（唯一）**：向 王工 取 20 Hz 回放 bag 的路径，写入 `RADAR_BAG_ROOT`，跑 `pytest tests/test_kf.py -k rmse` 记录基线

**之后三步**：

1. 按 §1 判据做 10 Hz / 20 Hz 对比
2. 差值超标则回看 `process_noise.cpp:140` 的 dt 平方项
3. 更新 `docs/kf_design.md` 的标定章节

## 9. 交接链

- 2026-10-17 19:40 · WorkBuddy/claude-sonnet-4.5 → Codex/gpt-5 · tool-switch · 实现完成、对比回放未做，原会话上下文将满
```

这份记录能被接手方直接执行的原因：第一步是取一个具体文件并跑一条具体命令；产物有 sha 和行号；否决路径带了失败数据；环境坑写了两条真实会踩的。

---

## 反例对照

| 写法 | 问题 | 改法 |
|---|---|---|
| 「已完成 KF 调参，代码见仓库」 | 没有路径、没有 sha、没有验证 | `文件：\`src/kf/process_noise.cpp\` @ \`9f3c2ab\` : \`118-164\`` + 验证命令 |
| 「Q 矩阵那块我改了，你看下」 | 依赖"你"知道"那块"在哪 | 写函数名、文件、行号区间 |
| 「尝试过另一种方案，效果不好」 | 无法判断是否值得再试 | 写失败现象与数据："20 Hz 下 RMSE 上升 12%" |
| 「环境按 README 配」 | README 可能过期或与本分支不符 | 命令与版本直接写进 §6 |
| 「下一步：继续优化」 | 不是可执行动作 | "在 `x.cpp:140` 把 dt 平方项补上，跑 `pytest -k rmse`" |
| `[x] 已修复内存泄漏` 无验证 | 未验证的完成声明 | 降为 `[ ]`，或补 `验证：valgrind --leak-check=full ./bin/tracker` → 0 leaks |
| 把 200 行代码粘进 §3，同时又给路径 | 两份内容必然漂移 | 只留路径 + sha + 行号；只有磁盘上不存在的内容才粘贴 |
| 「详见上文」 | 接手方没有"上文" | 复述结论，或指向具体节与文件 |
| front matter 写 `status: done` 但 §8 还有三步 | 状态与内容矛盾 | 改 `status: waiting`，或删掉未完成步骤并说明 |

## 一份记录合格的最低标准

1. 关掉当前会话，只看这个文件，能知道**第一件事做什么**。
2. 文件里每个"已完成"，都能用给出的命令复现。
3. 文件里每个路径，在这台机器上都能打开。
4. 文件里没有任何"你懂的"。
