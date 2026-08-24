# 专利挖掘与交底书技能 — 产品说明（PRD 摘要）

## 1. 产品概述

本仓库为符合 [AgentSkills](https://agentskills.io) 习惯的 **Skill**：通过 `SKILL.md` 编排流程，`prompts/` 存放可引用的指令模板，`tools/` 预留可执行脚本扩展。

**目标**：完成专利点挖掘与**资产清单取舍** → 查新 → 技术交底书（对齐所内 docx 模板）→ 内部自检 → **版本化交付**与迭代修订。

## 2. 用户流程

```
用户触发（自然语言 / 斜杠指令）
        ↓
Step 1  边界与输入（prompts/intake.md）
        ↓
Step 2  项目扫描（project_scan.md：.docx/.pptx 先转 MD；裸图目录可跳过）
        ↓
Step 3–4 专利点资产清单 + 轻量相似初筛 + 评分四类分类 + **用户取舍确认**（prompts/patent_points_analyzer.md）
        ↓
Step 5  联网查新（prior_art_search.md：**优先** tools 中国知局 epub 检索 `--type` 按类型过滤，失败再 WebSearch）
        ↓
Step 6  摘要预览与确认（prompts/disclosure_preview.md）
        ↓
Step 7  全文交底书（versioned_output.md + disclosure_builder.md + template_reference.md；含公式时先 formula_plan.yaml 范式校验）
        ↓
Step 8  内部自检（prompts/disclosure_self_check.md）→ 修订后交付
        ↓
Step 9  多件相关专利交付时：专利簇通俗说明清单（prompts/patent_family_explainer.md）
        ↓
交付   用户产出目录 **vN-简短说明-时间戳/** 版本目录下的 .md/.docx：**案件名 + 本地时间戳**（§7.3 第 5/6 点），**含首次定稿与每次迭代**，勿默认覆盖；根目录维护 **版本索引.md**
        ↓
持续   意图为改已有稿时：补充材料（merger.md，含术语族替换）/ 对话纠正（correction_handler.md）；写入下一版本目录；案件根目录 **`交底书修订对话记录.md`** 逐条追加（含时间、用户说明摘要），见 `iteration_context.md`
```

## 3. 目录约定

| 路径 | 说明 |
|------|------|
| `SKILL.md` | 唯一入口：触发条件、工具映射、步骤与 prompts 引用 |
| `prompts/` | 分步脚本化说明，由 Agent `Read` 后执行 |
| `tools/` | 可选脚本；含 `md_to_docx.py`（OMML 公式）、`docx_to_md.py`、`pptx_to_md.py`、`mermaid_render.py`（Playwright）、`cnipa_epub_search.py`（查新一步，`--type` 过滤）、`formula_*` / `check_formula_plan.py`（公式范式校验），见 `tools/README.md` |
| `references/` | 公式范式库 `formulas/paradigms.yaml`、`schemas/formula_plan.schema.yaml` 合同、`patent_type_search.yaml` 类型检索映射 |
| `docs/` | PRD、架构学习笔记等 |
| `outputs/` | 用户定稿导出目录；整目录由 `.gitignore` 忽略；可提交的脱敏范例放在 **`examples/`** |
| `examples/` | 随仓库提交的**原材料**示例（如 `example_batch_job_scheduler/knowledge/`）；流程产出在 `outputs/` |

## 4. 约束

- Office 原材料（Word/PPT）：使用本仓库 `tools/docx_to_md.py`、`tools/pptx_to_md.py` 转换后再扫描（见 `SKILL.md`）。
- 交底书正文**不得**包含「自检清单」章节。
- 脱敏要求见 `disclosure_builder.md` / `template_reference.md`。
- 查新结论须写入 3.1/3.3 并与技术问题、方案呼应；渠道与著录细则见 `prompts/prior_art_search.md`。
- 交底书定稿须**同时**交付 Markdown 与 Word；文件名 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5 点，含首次与迭代）；`tools/mermaid_render.py` 默认调用 `md_to_docx.py`；Word 失败时允许人工补转（见 `tools/README.md`）。

## 5. 环境变量

在 Claude Code、OpenClaw 等环境中，常使用 **`CLAUDE_SKILL_DIR`** 指向技能根目录。使用 Cursor 打开本仓库时，该目录即仓库根目录。
