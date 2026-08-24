# tools / 可选脚本

本目录存放**可重复执行的辅助脚本**。技能主流程以 `SKILL.md` 与 `prompts/` 为准；本目录侧重格式转换等可执行工具。

## 国知局公布公告检索（epub.cnipa.gov.cn，Step 5 查新优先）

| 脚本 | 作用 |
|------|------|
| **`cnipa_epub_search.py`** | **（Step 5 优先）** 一步：拉取 + 解析，**不写结果页 HTML 落盘**；支持 **`--type invention\|utility_model\|design\|all`**（默认 `all`，对应公布站首页勾选，见 `patent_type.py` 与 `references/patent_type_search.yaml`）。**Agent 一次进程传入全部检索单位**（多个 argv），脚本在**同一浏览器**内一词一查再按 `pub_number` 去重合并（stderr 可见 `EPUB_MERGE:`）；**stdout 仅一行** `EPUB_HITS_JSON:`；stderr 上 `EPUB_*` 为 **ASCII**；**stderr 有字 ≠ 失败**，以退出码与 stdout JSON 为准。 |
| **`cnipa_epub_crawler.py`** | 仅 Playwright 拉取并**默认保存**结果页 HTML；stdout 亦含 **`EPUB_HITS_JSON:`**。 |
| **`cnipa_epub_parse.py`** | 仅解析已保存的 HTML：`python tools/cnipa_epub_parse.py path/to/_last_result_xxx.html`；字段含标题、公开号、链接、**`abstract`**（若有）。 |

依赖：`pip install -r requirements.txt`（含 playwright）。**检索前先探测浏览器**：`python tools/browser.py --probe`——有系统 Chrome/Edge（`ok=true`）**直接检索，勿执行** `python -m playwright install chromium`；仅当本机无系统浏览器且自带 Chromium 缺失时才装一次。环境变量见各脚本文件头。默认结果 HTML 落在 **`tools/_last_result_*.html`**（已 `.gitignore`）。

抓取失败或解析无命中时，Agent 按 **`prompts/prior_art_search.md`** 降级 **WebSearch**（如 Google 学术 / Google Patents）。

---

## Office 文档（Word / PPT）转成可扫描文本

用本仓库 **`docx_to_md.py`**、**`pptx_to_md.py`**（纯 Python + 仓库根目录 `requirements.txt`），见下文各节；与 `SKILL.md`「工具与数据来源」一致。

## mermaid_render.py — mermaid：图示 → PNG + 定稿 Markdown + **默认生成 Word**

将 fenced **mermaid**（`` ```mermaid`` ``）逐块渲染为 PNG；输出 `.md` 中**保留** mermaid 围栏源码，并追加 ``<!-- ![图示 n](mermaid_figures/…) -->`` 供 **`md_to_docx.py`** 嵌入 Word（Word **仅**嵌 PNG，不写 mermaid 代码块）。**4.2.1 系统框图**与 **4.2.3 流程图**均用 mermaid（`flowchart` / `subgraph` 等），交底书正文**不再**要求单独的文字框图或 PlantUML。

**渲染后端：Playwright + 内置 `vendor/mermaid.min.js`**（与国知局查新共用 `browser.py`：系统 Chrome → Edge → 自带 Chromium）。**不调用 Node / mmdc / npx，无需任何 npm 安装**。默认视口 1400×1050、`device_scale_factor=2`；可用 `--mmdc-scale` / `--mmdc-width` / `--mmdc-height`（历史参数名，语义不变）。

**步骤号自动补齐**：流程图节点 id（`S1`）**不会**出现在 PNG 上；成文应按 `S1["S1 采集节点指标"]` 把序号写进可见标签。定稿时脚本会把**缺失**的序号自动补进标签再出图（成文仍应按正确写法写，勿依赖脚本补救）。

**生图失败降级**：某一围栏渲染失败时**不中断**——该处**保留**原 `` ```mermaid`` … `` ``` `` 源码；其余块照常出图。仍写出定稿 `.md`，并**照常尝试**生成 Word（未出图块在 Word 中为 **Consolas 代码块**）。无可用浏览器时同样保留围栏，不阻塞 Markdown 交付。

**文件名带时间戳**：PNG 文件名从输出 `.md` 文件名中提取时间戳（如输出为 `障碍物高度估计_202606091642.md`，则 PNG 为 `fig_202606091642_001.png`），不同版本的图片不会互相覆盖。若输出文件名不含时间戳，则回退为 `fig_001.png`。

**自动保存 .mmd 源文件**：每块 mermaid 渲染成功后，自动在同目录保存同名 `.mmd` 源文件（如 `fig_202606091642_001.mmd`）。后续如需单独修改图示，可直接编辑 `.mmd` 后重跑 `mermaid_render.py`（或用任意 mermaid 渲染器）。

### 依赖

```bash
pip install -r requirements.txt        # playwright 等
python tools/browser.py --probe        # 有系统 Chrome/Edge 即可；缺浏览器才 python -m playwright install chromium
```

### 用法

```bash
# 写出定稿 .md，并在同目录生成同名 .docx（默认）；-o 须为「案件名_YYYYMMDDHHmmss.md」（见 prompts/disclosure_builder.md §7.3 第 5 点）
python3 tools/mermaid_render.py -i draft.md -o "一种XXX方法及系统_20260408143025.md"

# 指定 .docx 路径（.md 主名仍须含时间戳）
python3 tools/mermaid_render.py -i draft.md -o out/一种XXX方法及系统_20260408143025.md --docx out/一种XXX方法及系统_20260408143025.docx

# 仅 Markdown，不要 Word
python3 tools/mermaid_render.py -i draft.md -o "一种XXX方法及系统_20260408143025.md" --no-docx

# 更高清晰度（可选）
python3 tools/mermaid_render.py -i draft.md -o "…定稿.md" --mmdc-scale 3 --mmdc-width 1600 --mmdc-height 1200

# 指定 mermaid 图片子目录（相对输出 .md）
python3 tools/mermaid_render.py -i draft.md -o out/一种XXX方法及系统_20260408143025.md --assets-dir figures/mermaid
```

**判读（stderr ≠ 失败）**：以 **退出码 0** 与机读前缀为准——`MERMAID: ok=`、`DOCX: ok=1`。PowerShell 红字 / `NativeCommandError` / 中文乱码**不是**失败；`DOCX: ok=0` 才按 stderr 提示的手动 `md_to_docx.py` 命令补做。

### 与交底书约定

- 技能要求定稿**同时**交付 **Markdown + Word**，且 **`-o` 主文件名须含 `_{YYYYMMDDHHmmss}`**（`prompts/disclosure_builder.md` §7.3 第 5 点，含首次定稿）；**4.2.1 系统框图**与 **4.2.3 流程图**均用 fenced mermaid，**不要** ASCII 文字流程图/框图。
- 交付代理人前：运行 `mermaid_render.py` 一步即可（默认再调 `md_to_docx.py`）；若 Word 失败，按 stderr 提示手动执行 `md_to_docx.py`。

---

## math_render.py — LaTeX 公式 → PNG（可选降级，默认不用）

> **公式主路径**：`md_to_docx.py` 优先经 **`math_to_omml.py`**（`latex2mathml`）把 LaTeX 写成 **Word 可编辑 OMML 公式**，失败则保留原文。**默认不预渲染公式 PNG、不安装 matplotlib**；仅当 stderr 出现 `omml_text_fallback=` / `OMML_FAIL:` 且用户确认后，用 `--math-render` 补 PNG。

将 Markdown 中的 **LaTeX 公式**（``$...$`` / `\(...\)` 行内；``$$...$$`` / `\[...\]` 块级）用 **matplotlib mathtext** 渲染为 PNG；**保留 LaTeX 原文**，图片引用写入 HTML 注释 ``<!-- ![...](math_figures/...) -->``（Markdown 预览不显示图），供 **`md_to_docx.py`** 嵌入 Word。

**mathtext 兼容**：渲染前自动将常见 LaTeX 简写映射为 mathtext 符号（如 ``\ge``→``\geq``、``\le``→``\leq``、``\land``→``\wedge``）；块级式内**换行压成一行**、``\tag{1}`` 转为式末 ``(1)``；仍无法解析的公式保留原文。**注意**：``\begin{cases}`` 等复杂 LaTeX mathtext 不支持，会失败降级。

```bash
pip install matplotlib    # 仅用户确认公式 PNG 后安装
python3 tools/md_to_docx.py -i "<同名.md>" -o "<同名.docx>" --base-dir "<md 所在目录>" --math-render
```

---

## math_to_omml.py — LaTeX → Word 原生公式（OMML，主路径）

被 `md_to_docx.py` 自动调用（一般无需直接使用）：LaTeX → MathML（`latex2mathml`）→ OMML（lxml 递归转换）→ 嵌入 python-docx 段落。公式在 Word 中**可编辑、可缩放、矢量清晰**，无需 PNG 图片。

**支持的 LaTeX 特性**：分数（`\frac`）、根号（`\sqrt`）、上下标（`_`/`^`）、希腊字母、`\mathrm`/`\text`、`\begin{cases}` 分段函数、`\min`/`\max` 函数、`\cdot`/`\land` 运算符等。**不支持**：矩阵（`\begin{matrix}`）、对齐环境（`\begin{aligned}`）等高级 LaTeX（失败保留原文）。

```bash
pip install latex2mathml   # 纯 Python，无编译依赖
```

---

## 公式范式与 formula_plan 校验（Step 7 含公式时）

| 脚本 | 作用 |
|------|------|
| **`formula_paradigms.py`** | 列出 / 展示 **`references/formulas/paradigms.yaml`** 中的可选范式与组合：`python tools/formula_paradigms.py list`、`show weighted_sum`、`combos`。案件目录可放 `formula_paradigms.yaml` 外挂扩展（或环境变量 `PATENT_FORMULA_PARADIGMS`）。 |
| **`check_formula_plan.py`** | 校验案件目录 **`formula_plan.yaml`**（合同：`references/schemas/formula_plan.schema.yaml`）：范式 id 合法、符号齐、**数值例可代入**。`python tools/check_formula_plan.py -i …/formula_plan.yaml --eval`；**不通过不得写 4.2.4**。 |

依赖：`PyYAML`（根目录 `requirements.txt`）。

---

## browser.py — 浏览器探测与共用启动（查新 + mermaid 共用）

Playwright 浏览器选择：**系统 Chrome → Edge → 自带 Chromium**。与国知局查新、mermaid 出图共用，避免再下一套 Puppeteer Chrome。

```bash
python tools/browser.py --probe     # stdout JSON：{"playwright": …, "channel": …, "ok": …}
```

`ok=true` 直接可用；`ok=false` 且有 playwright 包时才 `python -m playwright install chromium`（一次）。

---

## md_to_docx.py — Markdown → Word（含 OMML 公式）

将交底书 Markdown 转为 `.docx`，**`#`–`######` 映射为 Word 内置「标题 1」–「标题 9」**，正文为宋体 10.5pt，代码块为 Consolas，便于交给代理人或所内用 Word 修订。

**公式处理（OMML 优先）**：自动将 LaTeX 公式经 **`math_to_omml.py`**（`latex2mathml`）转为 **Word 原生 OMML 公式**——可编辑、矢量清晰。支持 `$...$`、`\(...\)` 行内公式和 `$$...$$`、`\[...\]` 块级公式，包括 `\begin{cases}` 等。转换失败则**保留 LaTeX 原文**；stderr 机读统计：`MATH: omml=… png=… text=…`、`OMML_FAIL: <式>`、`omml_text_fallback=N`。公式 PNG 仅在用户确认后经 `--math-render`（须 matplotlib）补做。

**有序列表重计**：被标题、段落、表格等隔开的 Markdown 有序列表在 Word 中**各自从 1 重计**，避免跨章串号。

**图示**：定稿应用 **`mermaid_render.py`** 将 mermaid 转为 PNG；若个别块生图失败被降级保留围栏，本脚本会将**仍存在的** `` ```mermaid`` 块按**代码块**写入 Word。本脚本不渲染 mermaid。

### 依赖

```bash
pip install -r requirements.txt   # python-docx + latex2mathml 等
```

### 用法

```bash
python3 tools/md_to_docx.py --input path/to/交底书.md --output path/to/交底书.docx
# OMML 失败且用户确认后补公式 PNG（须 matplotlib）：
python3 tools/md_to_docx.py -i "<同名.md>" -o "<同名.docx>" --base-dir "<md 所在目录>" --math-render
```

图片 `![](相对路径.png)`：默认相对 **Markdown 文件所在目录**；也可指定根目录：

```bash
python3 tools/md_to_docx.py -i ./outputs/case/disclosure.md -o ./outputs/case/disclosure.docx --base-dir ./outputs/case
```

**插图**：对 PNG/GIF/JPEG 会读取像素尺寸，在默认 **最大宽 5.5" × 最大高 8.2"** 内**等比缩放**并同时指定 `width`/`height`，避免竖长流程图仅按宽度放大后**高度超出版心**、打印或阅读时像被裁切。可按纸张边距调整，例如：

```bash
python3 tools/md_to_docx.py -i a.md -o a.docx --image-max-width-inches 6 --image-max-height-inches 9
```

在 Claude Code 中可将 `tools` 换为 `${CLAUDE_SKILL_DIR}/tools`。

### 支持的 Markdown 子集

| 元素 | 行为 |
|------|------|
| `#`–`######` | Word 标题 1–9 |
| 段落 | 宋体正文，支持 `**粗体**`、`` `行内代码` ``；**相邻非空行（中间无空行）各自成段**，「（1）…（2）…」会分行显示 |
| `-` / `*` 列表 | 项目符号列表 |
| `1.` 列表 | 编号列表；被标题/段落/表格隔开时各自从 1 重计 |
| ` ``` ` 围栏 | 等宽代码块 |
| `\| 表格 \|` | 简单表格（Table Grid）；单元格内 ``\\(...\\)``、``$...$``、``<!-- -->`` 及 ``\\|`` 中的 ``|`` **不会**被当作列分隔符 |
| `> ` | 左缩进引用 |
| `---` 等 | 浅色分隔线 |
| `![](path)` | 嵌入图片（路径需存在；默认宽/高上限内等比缩放；公式图与正文混排） |
| `$` / `\\(...\\)` / `$$` / `\\[...\\]` LaTeX | **OMML 原生公式优先**；失败保留原文（`--math-render` 时才 PNG） |

**未完整支持**：复杂嵌套列表、HTML 块、**未预渲染的** mermaid 围栏（仍为代码块）、脚注、任务列表等。定稿前请运行 **`mermaid_render.py`**；若仅用外部工具导出 PNG，可直接写 `![](...)`。

### 版式说明（md_to_docx）

- 不同语言 Word 中「标题 1」显示名可能为「Heading 1」或「标题 1」，样式仍为大纲级别标题，可用导航窗格与目录域。
- 若需所内固定模版（页眉、首页不同），可在本脚本生成后套用单位 `.dotx`，或后续扩展 `python-docx` 打开模版再写入。

---

## iteration_dialog_log.py — 修订对话记录（迭代用）

每轮 **`merger.md` / `correction_handler.md`** 交付后，在**案件目录**追加一条 **`交底书修订对话记录.md`**：含**本地时间与 UTC**、用户说明摘要、本轮交付文件名、合并/纠正摘要摘录。规则见 **`prompts/iteration_context.md`**。

**依赖**：仅标准库。

```bash
python3 tools/iteration_dialog_log.py --case-dir outputs/某案件 --kind merge \
  --user "补充了调度装置资料，合并进第三章" \
  --summary "已扩写 3.4，并更新实施例；未改保护点表述。" \
  --artifacts "一种XXX方法及系统_20260408143025.md,一种XXX方法及系统_20260408143025.docx"
```

- `--kind`：`merge` 或 `correct`。  
- `--log-name`：可选，默认 `交底书修订对话记录.md`；英文环境可改用 `disclosure_revision_log.md`。  
- 无法执行脚本时，由 Agent 按同结构手工追加。

---

## docx_to_md.py — Word → Markdown + 抽取图片

将 **.docx**（Word / WPS 等另存为 docx）转为 **Markdown**，并把文档内嵌图片落到磁盘，便于 **`Read` 与 Step 2 扫描**（与直接读二进制 .docx 相比更稳）。**Step 2** 对扫描树内**每一个** `.docx` 都应先转换再读产出 `.md`，见 `prompts/project_scan.md`。

### 依赖

与 `md_to_docx` 共用根目录 `requirements.txt`（`python-docx` + **`mammoth`**）。

```bash
pip install -r requirements.txt
```

### 用法

```bash
python3 tools/docx_to_md.py --input path/to/设计说明.docx --output outputs/case/design.md
```

- 默认图片目录：`outputs/case/design_media/`，Markdown 内为相对路径 `![](design_media/img_0001.png)`。
- 自定义图片目录：

```bash
python3 tools/docx_to_md.py -i ./raw/spec.docx -o ./knowledge/spec.md --media-dir ./knowledge/spec_assets
```

转换警告（如部分样式、WMF 图）会输出到 **stderr**，仍可能生成可用 `.md`。

### 局限（mammoth）

- 仅 **`.docx`**（OOXML）；老版 **`.doc`** 不支持。
- **Markdown 输出在 mammoth 侧标记为 deprecated**，复杂排版可能弱于「先导出 HTML 再转 MD」；专利扫描一般足够。若版式崩坏，建议所内 **另存为 PDF 或纯文本** 再扫。
- **WMF/EMF** 等 Windows 图元可能需单独处理（见 [mammoth WMF 配方](https://github.com/mwilliamson/python-mammoth)）。

在 Claude Code 中可将 `tools` 换为 `${CLAUDE_SKILL_DIR}/tools`。Windows 无 `python3` 时用 `python`。

---

## pptx_to_md.py — PowerPoint → Markdown + 抽取图片

将 **.pptx** / **.ppsx** 按**幻灯片页**导出为 Markdown，并抽取幻灯片中的**嵌入位图**（`PICTURE` 形状），便于 **`Read` 与 Step 2 扫描**。**Step 2** 对扫描树内**每一个** `.pptx` 均应先转换再读 `.md`，见 `prompts/project_scan.md`。

### 依赖

根目录 `requirements.txt` 中的 **`python-pptx`**。

```bash
pip install -r requirements.txt
```

### 用法

```bash
python3 tools/pptx_to_md.py --input path/to/评审材料.pptx --output outputs/case/review.md
```

- 默认图片目录：`outputs/case/review_media/`，文件名形如 `slide03_img0001.png`。
- 自定义图片目录：

```bash
python3 tools/pptx_to_md.py -i ./raw/deck.pptx -o ./knowledge/deck.md --media-dir ./knowledge/deck_media
```

每页输出二级标题 `## 第 N 页`，其后为该页形状中的**文本与表格**（简化为管道表）及图片引用；若存在**演讲者备注**，以「**备注**」小节附于该页末尾。

### 局限（python-pptx）

- 仅 **`.pptx` / `.ppsx`**（OOXML）；**`.ppt`** 不支持，请先另存。
- **图表、SmartArt、嵌入 OLE** 等若未以普通图片形状存在，**不会**自动栅格化为 PNG；可先在 PowerPoint 中另存为图片或导出 PDF 作补充材料。
- 文本按形状遍历顺序输出，与视觉阅读顺序可能略有差异。

在 Claude Code 中可将 `tools` 换为 `${CLAUDE_SKILL_DIR}/tools`。Windows 无 `python3` 时用 `python`。

---

## 扩展其它脚本时

- Word / PPT 转换依赖写在 `requirements.txt`。
- 在 `SKILL.md`「工具与数据来源」表中增加一行调用说明。
- 勿将密钥写入仓库；配置使用环境变量或用户主目录。
