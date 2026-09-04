---
name: customize-patent-disclosure-skill
description: "面向所内《专利技术交底书》模板的专利挖掘与交底书生成全流程：扫描项目文档挖掘专利点并输出含轻量相似专利初筛的资产清单（用户取舍确认后才成文）、讨论融合、对齐所内 docx 模板（封面元数据表+一名称/二技术领域/三背景技术3.1-3.3/四创新点4.1-4.5含代替方案与逻辑论证/五实施方式/六附图）生成技术交底书、联网查新（按发明/实用新型类型过滤）、公式范式计划与可算性校验、版本化目录交付（vN-说明-时间戳+版本索引）、多件交付附专利簇通俗清单、生成后自检含逻辑闭环/标题贯穿与公式参数一致性。适用于需要按真实交底书模板格式产出的场景；图片类多模态理解与附图核对经 multimodal-vision 子智能体。| Patent mining triage gate + disclosure drafting aligned to an in-house docx template, typed prior-art search, formula-paradigm planning, versioned delivery, and consistency self-check."
version: "2.1.1"
user-invocable: true
argument-hint: "[可选：项目路径或技术主题关键词]"
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, Bash
---

# 专利挖掘与交底书生成（对齐所内 docx 模板）

本技能是 `patent-disclosure-skill` 的**定制版**：交底书结构**严格对齐 `【参考】专利技术交底书模板.docx`**（封面元数据表 + 一~六章），相比通用脱敏版补齐了**所属技术领域、3.3 业内克服缺陷的尝试、4.3 代替方案、4.5 技术效果逻辑论证、独立附图章**与**案件管理元数据封面表**。覆盖 **专利点挖掘与资产清单取舍** → **查新与差异化** → **交底书生成** → **自检完善** → **版本化交付与迭代** 全流程；分步指令在 **`prompts/`**，每步执行前 **`Read`** 对应文件，与步骤的对照见「Prompt 文件映射」。

## 环境与约定

- **语言**：默认与用户语种一致；专利与法律术语采用行业常用表述。
- **脚本判读（尤其 Windows）**：stderr 有字 **不等于** 失败。以 **退出码 0** 和机读前缀为准：`EPUB_HITS_JSON:` / `EPUB_MERGE:` / `BROWSER:`、`MERMAID: ok=`、`DOCX: ok=1`、`MATH:`、`omml_text_fallback=`。PowerShell 可能把 stderr 标成 `NativeCommandError` 或乱码；**禁止**因此重跑安装、认定 Word 未生成、或把查新降级 WebSearch。勿用 `2>&1` 把 JSON 混进错误流。
- **专利类型**：封面「申报类型」未显式指定时**默认发明**（`invention`）；材料明显更偏产品形状/构造改进时在汇总或预览阶段**反问**是否改实用新型（见 `intake.md`）。查新 `--type` 与之一致。
- **图片等多模态任务（经 multimodal-vision 子智能体）**：凡需「看图」的场景——Step 2 理解关键图片材料（架构图/流程图/截图）、Step 8 定稿后核对 mermaid PNG 附图、检查图片内敏感信息——委派 **`multimodal-vision`** 子智能体（Agent 工具，`subagent_type: multimodal-vision`）：prompt 给足**图片路径 + 具体问题**（勿泛泛「分析这张图」）；子智能体返回的属**报告推断**，涉及专利点/技术事实的结论须与文本材料**交叉核对**。当前环境无该子智能体时，回退为主代理直接读图。
- **图示定稿（Step 7）**：**4.2.1 系统框图**/**4.2.3 流程图**用 fenced **mermaid**（**Playwright + 内置 `tools/vendor/mermaid.min.js`** 渲染，与查新共用 `tools/browser.py`，**无需 Node/mmdc/npm**）；步骤号须写进**可见标签**（`S1["S1 …"]`）。执行方式与降级规则见下表「交底书定稿交付」行及 **`tools/README.md`**。

---

## 触发条件

在用户使用以下任一方式时启用本技能：

- 明确提及：专利挖掘、专利点、技术交底书、交底书、专利交底书、查新、现有技术对比、**所内交底书模板**、专利点资产清单等
- 斜杠或简短指令：如 `/customize-patent-disclosure-skill`、`/patent-disclosure`、`/交底书`
- **迭代模式（按意图识别）**：当用户意图明显是在**已有交底书或上一轮输出**上继续工作（如改章节、补实施例、补材料、修正参数/事实、调整表述、换术语等），**无需**用户写出「迭代」等固定词，也**不必**询问是否进入迭代——Agent 应 **`Read`** **`prompts/versioned_output.md`** 与 **`prompts/iteration_context.md`**，再 **`Read`** `prompts/merger.md`（侧重**新材料、扩展合并**）或 `prompts/correction_handler.md`（侧重**纠错、与事实或风格不符**），**严格按该文件开头的「执行门禁」**（优先执行，不可跳过）**做完合并或纠正**，在**下一个版本目录**中另存为新文件：**`{案件名}_{YYYYMMDDHHmmss}.md`** 与同名 **`.docx`**（与首次定稿同一命名规则，见 **`disclosure_builder.md` §7.3 第 5/6 点**），**不覆盖**旧稿（除非用户明确要求）。**禁止**在迭代意图已成立时默认回到 Step 3–4 专利点全文分析（除非用户明确要求重新挖掘专利点）。对话中**已出现**交底书路径、附件或上文刚交付的草稿时，优先按迭代处理。

---

## 工具与数据来源

按任务选用能力；具体工具名称以当前 Agent 环境为准。

若扫描范围内含 **Word（.docx）** 或 **PowerPoint（.pptx）**，须在 Step 2 纳入阅读前用本仓库 **`docx_to_md.py`** / **`pptx_to_md.py`** 转为 Markdown；依赖 **`pip install -r requirements.txt`**，命令与说明见下表对应行。

### 常见任务与建议方式

| 任务 | 建议方式 |
|------|----------|
| 加载分步指令 | **`Read`** → `${CLAUDE_SKILL_DIR}/prompts/*.md`，见下表 |
| 读代码、设计文档、PDF、图片 | 文件读取工具；大仓库先用搜索/语义检索定位再精读 |
| Word（.docx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/docx_to_md.py --input {path}.docx --output {dir}/{name}.md`；图片默认写入与 `.md` 同级的 `{name}_media/`；需 `pip install -r requirements.txt`（含 mammoth）；复杂版式可改由所内导出 PDF/MD 再扫 |
| PowerPoint（.pptx）→ Markdown + 抽取图片（扫描前） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/pptx_to_md.py --input {path}.pptx --output {dir}/{name}.md`；默认 `{name}_media/`；需 `pip install -r requirements.txt`（含 python-pptx）；**旧版 .ppt 不支持**，请先另存为 `.pptx`；图表/SmartArt 等若未以图片形状嵌入则可能仅能从备注或另行导出补全 |
| 罗列目录、按名找文件 | 目录列举 / 按文件名搜索 |
| 轻量相似专利初筛（Step 3–4） | 执行前 **`Read`** `prompts/patent_points_analyzer.md`。优先 Google Patents + WebSearch 搜每个拟申请候选点的 1–3 组关键词；网络不可用时在清单中标注「轻量检索未完成，不作为最终可申请结论」 |
| 联网查新（Step 5） | 执行前 **`Read`** `prompts/prior_art_search.md`。**中国专利公布公告**：**先探测** `python tools/browser.py --probe`（系统 Chrome/Edge 可用即**禁止** `playwright install chromium`），再优先 **`Bash`** 运行 `cnipa_epub_search.py --type invention|utility_model`（类型与封面一致）；**须在生成命令前**归纳 **2～8 个相关度高的语义块**；**一次进程传入全部词块**（脚本同一浏览器内一词一查、按 `pub_number` 合并，stderr `EPUB_MERGE:`）；单次超时才拆至多两批。一步拉取+解析、**不写 HTML 落盘**；依赖根目录 `requirements.txt`。**`abstract` 规定必用**同该 prompt。需整句一次 AND 或保存 HTML 时用 `cnipa_epub_crawler.py`；异常或无果再 **WebSearch**（仅退出码非 0 / 无 JSON / 空数组才降级）。检索结论分流写入 **3.1 现有技术** 与 **3.3 业内尝试** |
| 图片理解 / 视觉核对（多模态任务） | 委派 **multimodal-vision** 子智能体（Agent 工具，`subagent_type: multimodal-vision`），给图片路径 + 具体问题：Step 2 关键图片（「这是方案架构图，提取模块名、连接关系与数据流」）；Step 8 附图 PNG（「核对流程图 PNG：S1—Sn 步骤号是否在可见标签、节点名是否为标题领域词、有无中文乱码/缺字」）；图片脱敏（「识别图中公司名/产品名/敏感数值」）。结论与文本交叉核对；无该子智能体时回退主代理直接读图 |
| 公式范式计划与校验（Step 7 含公式时） | 成文前 **`Read`** `references/formulas/paradigms.yaml`（或 `python tools/formula_paradigms.py list`），在案件目录写 **`formula_plan.yaml`**（合同 `references/schemas/formula_plan.schema.yaml`），`python tools/check_formula_plan.py -i …/formula_plan.yaml --eval` 通过后才写 4.2.4；见 `disclosure_builder.md` §7.7 |
| 交底书定稿交付（**须同时** .md + .docx） | **4.2.1 系统框图**与 **4.2.3 流程图**均用 fenced ``mermaid``（**Playwright 渲染，免 Node/mmdc**），**不要** ASCII 文字流程图/框图。定稿执行 **`tools/mermaid_render.py`**：mermaid 转 PNG（失败块保留围栏）后默认生成同名 **.docx**；PNG 文件名带时间戳防止版本间覆盖。**公式处理**：`md_to_docx.py` 优先经 `math_to_omml.py` 把 LaTeX 转为 **Word 原生 OMML 公式**（可编辑、矢量清晰），失败保留原文；**默认不装 matplotlib**，stderr 出现 `omml_text_fallback=` 时按 `disclosure_builder.md`「OMML 失败后的公式 PNG」在交付末尾反问一次。若 Word 失败，按 stderr 提示手动运行 **`md_to_docx.py`**。详见 **`tools/README.md`** |
| 保存交底书路径 | 写入用户指定路径；未指定时可建议 `./outputs/{案件标识}/`。交付前 **`Read`** `prompts/versioned_output.md`：产物写入 **`vN-简短说明-YYYYMMDDHHMMSS/`** 版本文件夹，根目录只维护 **`版本索引.md`** 与修订日志。**凡交付的** `.md` / `.docx` 须为 **`{案件名}_{YYYYMMDDHHmmss}`**（§7.3 第 5/6 点，**含首次定稿与迭代**），勿默认覆盖旧稿；`outputs/` 整目录默认由 `.gitignore` 忽略 |
| 迭代对话留档 | 每轮 **merger / correction** 交付后，在案件根目录追加 **`交底书修订对话记录.md`** 并更新 **`版本索引.md`**（**`tools/iteration_dialog_log.py`** 或等价手工），见 **`prompts/iteration_context.md`** |

---

## Prompt 文件映射

| 步骤 | 文件 | 用途 |
|------|------|------|
| Step 1 | `prompts/intake.md` | 边界与输入问题；**专利类型默认发明**，材料偏实用新型时反问 |
| Step 2 | `prompts/project_scan.md` | 项目文档扫描；**须**对 `.docx`/`.pptx` 先转换再读（见该文件「Office 文档」节）；独立图片目录可跳过 |
| Step 3–4 | `prompts/patent_points_analyzer.md` | **专利点资产清单**（含轻量相似专利初筛、评分、四类分类）、用户**取舍确认门禁**、融合与推荐组合 |
| Step 5 | `prompts/prior_art_search.md` | 联网查新（`--type` 类型过滤）与分析要求；结论分流至 **3.1/3.3** |
| Step 6 | `prompts/disclosure_preview.md` | 全文前的摘要预览 |
| Step 7 | `prompts/versioned_output.md` + `prompts/disclosure_builder.md` + `prompts/template_reference.md` | 版本目录规范；交底书结构（对齐 docx 模板）、脱敏、**符号与公式体例（§7.7）**、**场景术语与标题贯穿（§7.9）**与图示规范；mermaid 与 4.2.4 符号/公式范例在 template_reference |
| Step 8 | `prompts/disclosure_self_check.md` | 内部自检（含封面表/字数下限/新章节齐全/标题贯穿/公式可算性检查），不写入正文 |
| Step 9 | `prompts/patent_family_explainer.md` | 一次交付 **2 件及以上**相关专利时的通俗说明清单：侧重点、方法/系统区别、交叉与边界、阅读路线 |
| 迭代 | `prompts/versioned_output.md` | 版本化目录：`vN-说明-时间戳/`、`版本索引.md`、版本内产物与图片资源 |
| 迭代 | `prompts/iteration_context.md` | 迭代意图、落盘命名、**修订对话记录 md**（含对话/记录时间） |
| 迭代 | `prompts/merger.md` | 新材料增量合并、术语族替换；**文首含门禁**；输出下一版本目录内 `{案件名}_{时间戳}.md`/`.docx` |
| 迭代 | `prompts/correction_handler.md` | 对话纠正；**文首含门禁**；输出下一版本目录内 `{案件名}_{时间戳}.md`/`.docx` |

---

## 主流程（执行顺序）

1. **`Read`** `intake.md` → 执行 Step 1（专利类型未指定时默认发明）  
2. **`Read`** `project_scan.md` → 执行 Step 2  
3. **`Read`** `patent_points_analyzer.md` → 执行 Step 3–4：先输出含**轻量相似专利初筛**的**专利点资产清单**（候选盘点 / 评分 / 四类分类 / 推荐组合），**等待用户取舍确认**；用户明确要求跳过时，仍须用 3–6 行说明「已按用户要求跳过清单与轻量初筛」  
4. 用户确认拟申请的专利点后，**`Read`** `prior_art_search.md` → 执行 Step 5 深度查新（`--type` 与封面类型一致）；被标为**商业秘密保护**的点**不得**生成交底书正文或公开化描述  
5. **`Read`** `disclosure_preview.md` → 执行 Step 6；用户可跳过  
6. **`Read`** `versioned_output.md`、`disclosure_builder.md` 与 **`Read`** `template_reference.md` → 执行 Step 7：先创建当前 `vN-简短说明-时间戳/` 版本目录；含公式时先写 **`formula_plan.yaml`** 并通过 **`check_formula_plan.py --eval`**（§7.7），再成文（**首次交付**的 `.md`/`.docx` 亦须 **`{案件名}_{YYYYMMDDHHmmss}`**，§7.3 第 5 点）；交付对话中**须**按 **`disclosure_builder.md` §7.6** 补充「权利要求偏向点」建议交互（**仅对话**，不入正文）  
7. **`Read`** `disclosure_self_check.md` → 内部执行 Step 8，修订后交付  
8. 若本轮交付 **2 件及以上**相关专利，**`Read`** `patent_family_explainer.md` → 执行 Step 9，通俗说明清单写入当前版本目录（文件名带时间戳）；最后更新根目录 **`版本索引.md`**  

**禁止**：未经过 Step 3–4 专利点资产清单与用户取舍确认就默认直接成文；交底书正文中包含「自检清单」章节；自检仅内部使用。

---

## 迭代模式（摘要）

**启用方式**：根据用户**自然语言意图**判断（见上文「触发条件」），**不要求**固定关键词，**默认不**为「是否迭代」打断用户。

- **补充材料 / 扩展章节**或 **§7.6 第四章 4.3 代替方案 / 第五章实施方式权利要求书式强化（用户已声明侧重点）**：`Read` → `versioned_output.md` → `iteration_context.md` → `merger.md`；合并结果写入**下一个版本目录**并另存为带时间戳的 `.md`/`.docx`（§7.3 第 5/6 点）；**追加** `交底书修订对话记录.md` 并更新 `版本索引.md`（`iteration_dialog_log.py` 或手工）；完成后**必须**输出「合并摘要」留档；若本轮亦为定稿交付，**仍建议**简短附带 §7.6 类引导  
- **指出错误 / 与事实或参数不符 / 术语太抽象与标题不对齐**：`Read` → `versioned_output.md` → `iteration_context.md` → `correction_handler.md`；纠正结果写入**下一个版本目录**并另存为带时间戳的 `.md`/`.docx`；**追加**对话记录并更新 `版本索引.md`；完成后**必须**输出「纠正摘要」留档；定稿交付时**还须**按 **`disclosure_builder.md` §7.6** 附「权利要求偏向点」引导（见 **`correction_handler.md`** 末尾）  
- 用户换叫法/指出话题错位术语时，按 `merger.md`「**术语族替换**」整族对齐，机制不丢。

主流程 Step 7→8 的 **`disclosure_self_check.md`** 仍在新稿定稿路径上内部执行。

---

## Agent 自用工作流检查清单

```
□ 已按步骤 Read 对应 prompts；Step 2 若目录含 Office，已执行 docx_to_md / pptx_to_md 并读了产出 `.md`
□ Step 3–4 已先输出专利点资产清单：含轻量相似专利初筛结果、四类分类（建议申请/可合并/暂不适合/商业秘密）、评分、理由与推荐组合；已获得用户确认要写的点（除非用户明确跳过清单并已说明）；商业秘密点未写入任何交底正文
□ 专利类型未指定时已默认发明；材料偏实用新型已按需反问；查新已带与封面一致的 --type
□ 查新完成且写入 3.1/3.3 与区别论述（符合 `prior_art_search.md`：**优先** `tools/cnipa_epub_search.py`，**先 browser.py --probe、一次进程多词共用浏览器、按 pub_number 合并**；**`abstract` 必用且已充分理解后再概括**；国知局命中项照抄 JSON `link`；仅退出码非 0/无 JSON/空数组才降级 WebSearch）；未因 stderr/乱码误判失败
□ 除用户明确跳过外，完成摘要预览
□ 交付前已 Read `versioned_output.md`；产物已写入 `vN-简短说明-时间戳/` 版本目录，根目录无新增平铺定稿文件，`版本索引.md` 已创建/更新
□ 结构对齐 docx 模板：封面表齐全（敏感字段 [待填写]、申报类型与查新 --type 一致）、一~六章齐全（含二技术领域/3.3 业内尝试/4.3 代替方案/4.5 逻辑论证/六附图）、名称≤25字、3.2≥100/3.3≥100/4.2≥200/4.5≥100字
□ 标题领域实词贯穿 4.2.1 框图、4.2.3 流程、第五章实施例（未被空上位词替换）；4.2.2 按框图一模块一项；4.2.3 逐项对应 S1—Sn 且步骤号在可见标签内；第五章有 2～3 个具名实例覆盖主路径+一条分支；无话题错位术语残留
□ 脱敏/模糊化标注、mermaid（Playwright 渲染为 PNG，未装/未跑 npm）、章节引用符合 template_reference；含公式时已写 formula_plan（范式∈references/formulas）且 check_formula_plan --eval 通过、可算数值例、无装饰音；4.2.4 符号表、§7.7 体例（维度下标、无字母多义、LaTeX 分隔符统一）及 4.2.5 符号列同形已满足；**已交付 .md 与 .docx**，且**文件名符合 §7.3 第 5 点**（**凡交付均含**时间戳后缀）；**正文无**技能/示例仓库类文末脚注
□ 涉及「看图」的环节（关键图片材料理解、渲染后 mermaid PNG 附图核对、图片敏感信息检查）已委派 multimodal-vision 子智能体，且其报告结论已与文本材料交叉核对（无该子智能体时已回退主代理直接读图）
□ 定稿类对话已含 **`disclosure_builder.md` §7.6**「权利要求偏向点」建议交互（**不入正文**、**不捏造**未在稿内出现的保护取向，优先基于 4.3 代替方案）；OMML 失败留原文时已按 builder 反问一次（未得「是」未装 matplotlib）；迭代再走 merger 时见 **`iteration_context.md`** 表格补充行
□ 一次交付 2 件及以上相关专利时，已生成专利簇通俗说明清单（写入当前版本目录、文件名带时间戳）
□ 识别到「在已有交底书上修改」类意图时，已 Read `versioned_output.md` + `iteration_context.md` 并选用 merger 或 correction_handler（而非从头跑扫描）；交付为下一版本目录内的**新** `{案件名}_{时间戳}.md`/`.docx`，未无故覆盖旧稿；已在对话中输出留档摘要（合并摘要/纠正摘要）并追加 `交底书修订对话记录.md`、更新 `版本索引.md`
□ 自检在后台完成，正文无自检清单章节；含公式时已按 **`disclosure_self_check.md` §8.2** 复核**公式正确性、可算性与公式逻辑**（有误已在 Step 8 直接改稿并联动 formula_plan）
```
