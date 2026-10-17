# 联网检索查新（Step 5）

## 必做时机

生成交底书全文**之前或生成过程中**必须执行；检索结论写入第三章 **3.1 现有技术** 与 **3.3 业内克服现有技术缺陷的尝试**，及与本案的**区别论述**。**分工**：3.1 偏「最接近的现有技术现状」，3.3 偏「同行针对同一缺陷的改进路线」；同一检索批次的结果按侧重分流到对应小节。

## 检索渠道（**优先国知局公布公告站，再降级 WebSearch**）

### A. 中国专利公布公告（**优先**，官方站点）

1. **站点**：[国家知识产权局 中国专利公布公告](http://epub.cnipa.gov.cn/)（**仅** `epub.cnipa.gov.cn`）。
2. **工具**（本仓库 `tools/`）：**`cnipa_epub_search.py`** —— **一步**完成公布站检索与结果解析（Playwright 过站点 WAF）；结果页 HTML **仅在内存中处理，不落盘**。**一词一页**：脚本在结果页用站点「每页 10 条」切换后取**公布模式第一页**（总数不足 10 则取全部）。成功时终端含 **`EPUB_NOTE:`**（ASCII，如 `html_bytes=… disk=0`）与 **`EPUB_HITS_JSON:`** 一行（JSON 数组：标题、公开号、链接、**`abstract`**、**`ipc_codes` / `loc_codes`** 等）；stderr 可能有 **`EPUB_CLASS_HINT: kind=ipc|loc codes=…`**。
3. **专利类型过滤（与 intake 一致）**：公布站首页支持勾选 **发明公布 / 发明授权 / 实用新型 / 外观设计**。脚本参数 **`--type invention|utility_model|design|all`**（默认 `all`）。本案为发明（默认）时查新应传 **`--type invention`**；实用新型传 `utility_model`。映射见 **`references/patent_type_search.yaml`** 与 **`tools/patent_type.py`**。

3b. **两轮收口与摘要精排（写 3.1 前必做）**

   3.1 只写**精排池**。不自建专利库、不用本地向量索引：第一轮按手段词召回，第二轮按分类号收口，再由 Agent 对照摘要精排。

   1. **第一轮（召回）**：首页 **3～4 个手段短语**（规则见第 4 点；`tools/cnipa_epub_wait.yaml` 的 `home_max_terms` 默认 4，**超过拒绝**）。一词一页、公布模式。命中项 JSON 含 **`ipc_codes` / `loc_codes`**。
   2. **抽出分类号**：发明/实用新型用 IPC 前缀（如 `B01J20`）；外观用 **LOC（洛迦诺）**（如 `26-05`）。取 **1～3 个**高频号（stderr `EPUB_CLASS_HINT` 可直接用）。无分类号则跳过第二轮，仍按手段过滤第一轮。
   3. **第二轮（邻域收口）**：同一 `--type`，加 **`--class`**（`--ipc` / `--loc` 同义），走公布站**高级查询**（分类号 + 名称）。**一次命令 1 个分类号 × 1 个名称词**（`cnipa_epub_wait.yaml` 的 `advanced_max_*` 默认 1×1）；第二个号或第二个词**再发一条命令**，至多 1～2 个手段词。命令行多传会**截断**并在 stderr 提示（`EPUB_HINT: truncated …`），不会 usage 失败。仍用公布模式 10 条首页：

      ```bash
      python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type invention --class B01J20 胺功能化
      python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type invention --class B01D53 胺功能化
      python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type design --class 26-05 台灯
      python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type design --class 26-05
      ```

   4. **候选池**：两轮按 `pub_number` 去重；优先同分类号。
   5. **Google Patents（可选补充）**：外网可能被墙，**至多尝试一次** WebSearch / 浏览器，查询串参考 `tools/patent_type.py` 的 `google_patents_websearch_query(核心词, type, class_codes)`（发明/实用含 `CPC=…/low`，外观带 LOC 号）。超时、被墙、0 条 → 跳过，不阻塞查新。有命中可并入候选池，中国专利 URL 仍抄国知局 `link`。
   6. **精排（必做，LLM 打分）**：对候选每条 **`abstract`** 对照本案「**技术问题 + 手段**」打 0–5 分（推理过程内完成）：

      | 分 | 含义 |
      |----|------|
      | 5 | 同一技术问题，手段/模块明显重叠 |
      | 3 | 同领域、手段相关 |
      | 1 | 仅关键词撞车 |
      | 0 | 远领域噪声 |

      无摘要的条目先补详情/Google 再打分，补不到则标「无摘要」且不得超过 2 分。取 **Top 6～8** 作为精排池，3.1 只写精排池。
   7. **条数保底**：精排后仍 **<4 条** → 从候选池捞**同一 IPC/LOC**、分数≥3 的补到约 4～6 条；还不够 → 仅 `--class`（少用或不用名称词）再查一次，或带上 HINT 里的相邻号；仍然少 → 3.1 如实写「检索范围内近邻较少」。公开号、URL 只写 JSON 或已打开页面里有的。
   8. **D1 锚定**：3.1 需要一篇**最接近的现有技术（D1）**作为区别论述的出发点——从精排池选**摘要与本案方案重叠面最大、解决同一技术问题**的一篇，写一句选定理由；其余条目作技术背景。未钉住时如实写「本次未钉住可作最接近现有技术的对比文件」，区别论述对材料/常规做法写。

4. **国知局检索词（生成阶段必做，须在拼 Bash 之前完成）**

   - **拆分责任在 Agent**：在**生成/构造命令阶段**，从本案技术方案、专利点或用户主题中归纳 **3～4 个与方案相关度高的手段短语**（脚本首页上限 `home_max_terms` 默认 4），**仅用 ASCII 空格分隔**，再写入 `cnipa_epub_search.py` 的参数。每一单位宜为 **有检索意义的语义块**，例如：**专业术语**、**名词短语**、**名动组合（如「批量调度」「异构调度」）**、**业内固定搭配**；**4 个狠词优于 8 个泛词**，**不要**拆成过碎的单字、泛义双字（如单独 `检索`、`增强`、`系统`、`方法` 等泛词），也**不要**把无关联词硬凑成一串。
   - **禁止**把**无空格的一整句长中文**当作**唯一**参数（例如不要：`".../cnipa_epub_search.py" "知识库检索增强大语言模型"`）。长串在公布站单框内易被当作整句 AND，**极易 0 条**。
   - **Agent 执行时**：**一次进程传入全部检索单位**（多个 argv 或空格分隔均可）。脚本在**同一浏览器**内一词一查再按 `pub_number` 去重合并（冷启动更慢，故**禁止**为控时把词拆成多次独立 Playwright 进程）。若单次环境超时，再拆成至多两批，每批仍共用一个浏览器。
   - 示意（须按本案替换；**一次调用、多个词**；类型按 intake）：

     ```bash
     python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type invention 知识库 检索增强 大语言模型
     ```

   - **脚本不做**自动分词或自动拆长中文；若确需**整句一次** AND 检索，改用 **`cnipa_epub_crawler.py`** 单传一句。

   | 场景 | 正例 | 反例 |
   |------|------|------|
   | 检索词 | `知识库 检索增强 大语言模型` | `"知识库检索增强大语言模型"` 整句当唯一参数 |
   | 词粒度 | 「异构调度」 | 单独「系统」「方法」 |
   | 进程 | 一次调用传入 3～4 个词 | 每个词单独起一个 Playwright |

5. **执行方式**（Step 5 在读完本文件后**先探测，再检索**；首次运行 Python 前按 `SKILL.md`「环境与约定 · Python 执行环境」**询问用户 uv 环境选择**并沿用，勿静默 `pip install`）：

   ```bash
   python ${CLAUDE_SKILL_DIR}/tools/browser.py --probe
   # --probe 的 stdout JSON：playwright=false 时本会话最多一次 pip install -r requirements.txt，再 --probe
   # ok=true（系统 Chrome/Edge 或自带 Chromium）→ 直接检索，禁止 python -m playwright install chromium
   # ok=false 且已有 playwright 包、本机无 Chrome/Edge 时，才允许一次 python -m playwright install chromium
   python ${CLAUDE_SKILL_DIR}/tools/cnipa_epub_search.py --type invention 词甲 词乙 词丙
   ```

   - **禁止**把 `pip install` / `python -m playwright install chromium` 写进每次检索的默认命令。
   - **合并**：一次调用若 stderr 含 **`EPUB_MERGE:`**，以 **stdout** 上**唯一一行** **`EPUB_HITS_JSON:`** 为准（脚本已按 `pub_number` 去重）。仅当拆成多批调用时，Agent 再按 **`pub_number`**（无则 **`link`**）合并，得到一份总表后再写入查新笔记与 3.1/3.3。
   - **stderr ≠ 失败**：**退出码 0** 且 stdout 有 `EPUB_HITS_JSON:` 即为成功。PowerShell 可能把 stderr 显示为 `NativeCommandError` 或中文乱码，**禁止**因此判定「未命中」或降级 WebSearch。**禁止** `2>&1` 后再在混合流里找 JSON。`EPUB_MERGE:` / `EPUB_NOTE:` / `EPUB_HINT:` / `EPUB_CLASS_HINT:` / `EPUB_PROGRESS:` / `BROWSER:` / `CNIPA_EPUB_ERROR:` 等在 **stderr** 且多为 **ASCII 机读标记**；脚本已 UTF-8 输出，不必先 `chcp 65001`。
   - 将 JSON 中**可核验**的公开号、标题、**国知局站点内详情链接**写入查新笔记与 3.1/3.3（见下 **`abstract` 必用**）。
   - **三种失败，分开处理**：
     1. **导航失败**（退出码非 0，stderr 有 **`CNIPA_EPUB_ERROR:`** `stage=goto|gate|submit`）：看 `hint=`。`skip_epub`（第一轮首页打不开）→ 进入 **B**；`keep_round1`（第二轮高级查询超时/失败）→ **保留第一轮 JSON**，按 3b.7 回补，**不触发降级**。
     2. **真 0 条**（退出码 0，`EPUB_HITS_JSON: []`）：换词 / 减分类号 / 按条数保底回补后再判断。
     3. **无 Playwright 且安装失败**：进入 **B**。
   - **降级条件**（满足任一才进入 **B**）：第一轮 `hint=skip_epub`、超时、无 Playwright 且安装失败、第一轮 stdout **无** `EPUB_HITS_JSON:`、第一轮 **`EPUB_HITS_JSON` 为空数组**且无法按分类号回补、或条目经人工核对明显与主题无关。**第二轮失败单独不触发降级**。等待上限见 `tools/cnipa_epub_wait.yaml`（可用环境变量 `EPUB_WAIT_YAML` / `EPUB_WAF_MAX_WAIT_SEC` 覆盖）。**仅有 stderr / 乱码 / NativeCommandError 而退出码为 0 且 JSON 非空 → 不降级。**

6. **`abstract` 字段（国知局条目，规定必用）**

   若 **`EPUB_HITS_JSON`** 中某项含非空的 **`abstract`**（解析自公布站结果页摘要），对**该条专利**须同时遵守：

   - **必用**：查新笔记、交底书 **3.1/3.3** 中对该专利的**技术方案概括、应用场景与局限性分析**，**必须先基于对该 `abstract` 的完整阅读与理解**后再撰写；**禁止**仅凭标题、公开号或 URL **臆造**方案要点或与摘要矛盾的表述。
   - **充分理解**：在写入 3.1/3.3 或查新笔记前，Agent 须在**推理过程内**明确：摘要所涉**技术领域、解决什么问题、核心手段/模块、主要效果或流程**；若摘要与标题存在差异，**以摘要为准**概括该技术。
   - **正文呈现**：交底书 3.1/3.3 中**不得**大段逐字粘贴官方摘要（避免抄袭与超字数）；应**消化后**用**自己的话**压缩为「方案概括 + 应用 + 缺点/局限」；查新笔记可保留稍长的摘录供自用核对，但须标注来源于公布站摘要。
   - **缺失时**：若某条 JSON **无** `abstract` 或为空（旧版页面 / 表格布局未解析到等），须在查新笔记中注明「该条无摘要字段」，并改用**详情页**或 **Google Patents** 等可核验来源补全理解后再写 3.1/3.3，**不得**留空理由含糊带过。

   | 场景 | 正例 | 反例 |
   |------|------|------|
   | 3.1 技术方案 | 消化摘要后用自己的话写「方案 + 应用 + 局限」 | 整段粘贴官方摘要，或脱离摘要杜撰手段 |
   | 证据级别 | 摘要级判断写成摘要级 | 写成「已核实全文」 |

6. **链接与著录**：`EPUB_HITS_JSON` 命中项在 3.1/3.3 的「来源链接」**直接使用 JSON 的 `link` 字段**（国知局公布站 `epub.cnipa.gov.cn`）；**禁止编造**，也**不得**用 Google Patents URL **替换**已有 `link`。Google Patents 仅用于 **§B** 降级检索所得条目，或 JSON **无** `link`、仅知 `pub_number` 时的备选取址（如 `https://patents.google.com/patent/CN…/en`，仍须打开校验）。公开号与 URL 须对得上 JSON。

### B. Google 学术与 Google Patents（**降级 / 补充**）

在 **A 不可用或结果不足**时启用。类型过滤能力见 **`references/patent_type_search.yaml`**：

1. **中文文献与学术**：[Google 学术搜索](https://scholar.google.com)（`scholar.google.com`）。
   - 用**中文关键词**、技术方案核心术语、应用场景；可组合 2–3 组查询。
   - 强化「中国」语境时可加：`中国`、`site:.cn`、`专利`、`CN`（与专利号区分使用）等，以实际命中为准。
   - 通过 **WebSearch** 或浏览器检索；优先可打开且与标题/作者匹配的链接。
2. **中国专利公开文献（补充）**：[Google Patents](https://patents.google.com/)。
   - **发明**：界面/参数倾向 **Patent（`type=PATENT`）** + `country:CN`；公开号常见 `CN…A` / `CN…B`。第二轮分类号可拼 `CPC=B01J20/low`（见 3b.5，外网不通则跳过）。
   - **实用新型**：**无独立 Utility Model 类型**；用 Patent 域 + 关键词「实用新型」或公开号 `…U` 收窄，**类型过滤仍以国知局 A 渠道为准**。
   - **外观**：用 **Design（`type=DESIGN`）** + `country:CN`；公开号常见 `…S`。可把 LOC 号（如 `26-05`）当补充词。
   - 每条使用**稳定著录页 URL**；查询串可参考 `tools/patent_type.py` 的 `google_patents_websearch_query`。
3. **其它来源**：英文文献、非中国专利等可继续用 Google Patents、出版社页面、DOI、arXiv 等 + WebSearch。
4. **关键词构造**：技术方案核心术语、应用场景与方法名称，可组合 2–3 组查询。

## 分析要求

对检索到的、与方案**高度相关**的现有专利或公开文献逐项概括：

- 专利号 / 文献标识
- 技术方案要点（**若为国知局 JSON 且含 `abstract`，要点须与摘要理解一致**，见上文「`abstract` 必用」）
- 应用场景
- **局限性**
- **公开源 URL（必填）**：每一条必须附带**至少一个可公开访问、与著录项一致**的链接，写入查新笔记与交底书 3.1/3.3，便于代理人复核。**禁止编造或猜测 URL**；写入前应在浏览器中打开确认页面可访问且对应同一文献/专利。

写入 3.1 的条目须出自**精排池**（见 3b.6）；文末给出：**检索总结**与**本发明与现有技术的本质区别**（以 D1 为出发点逐条对应，见 3b.8），与 3.1 结尾及 3.2 缺点呼应。

### 链接来源与格式（须准确）

| 类型 | 推荐 URL 形式 | 说明 |
|------|----------------|------|
| 美国等专利（公开出版物号） | `https://patents.google.com/patent/US20240118920A1/en` | 将 `US20240118920A1` 替换为实际公开号；以 Google Patents 页面能打开且标题/摘要匹配为准。 |
| 中国专利（**§A 国知局 JSON 命中**） | JSON 的 **`link`**，如 `http://epub.cnipa.gov.cn/patent/CN119781913A` | 3.1/3.3「来源链接」**照抄 `link`**，勿改域名为 `patents.google.com`。 |
| 中国专利（**§B / WebSearch 补条**） | `https://patents.google.com/patent/CNXXXXXXXXXA/en`（或对应 B/U 型等） | 仅无国知局 `link`、经 §B 检索所得条目使用；勿用于替换 §A 命中项的 `link`。 |
| 学术论文（含 Scholar） | Scholar 条目页、出版社官方页或 **`https://doi.org/10.xxxx/...`** | Scholar 链接若重定向或镜像，以最终可长期解析的 DOI/出版社页为准。 |
| arXiv 预印本 | `https://arxiv.org/abs/2008.09213` | `abs` 页为规范条目页；勿用未经验证的镜像域名冒充官方。 |
| 期刊 / 会议 | 出版社 DOI：`https://doi.org/10.xxxx/...` 或官方摘要页 | 以 DOI 解析后页面与文献一致为准。 |

## 记录习惯

便于写进交底书：保留专利号、标题、**消化摘要后的**一两句方案概括（有 **`abstract`** 时概括须可追溯至该摘要）与**精排打分**；**每条另起一行或表格列给出「来源 URL」**。避免大段抄袭权利要求或整段粘贴官方摘要。

### 3.1「检索说明」写法（交付正文，必遵）

写入交底书 **3.1** 开头的「检索说明」时，面向**代理人/审查员**表述，**不要**暴露 Agent 查新流程或本仓库工具实现。

- **须写**：实际使用的**公开数据库或渠道名称**（如「国家知识产权局专利公布公告系统」）、本案**主要检索词**（与 Step 5 用词一致或概括）；若做了分类号收口，可写 IPC 或外观 LOC（如「在 B01J20 类下」）；若部分条目经 **Google Patents** 等公开页复核著录项，可一句带过。
- **禁止写入 3.1 正文**：脚本/文件名（如 **`cnipa_epub_search.py`**、**`cnipa_epub_crawler.py`**）、「查新优先使用…检索工具」「是否触发 Google 学术降级」、Playwright、WebSearch、Agent、技能仓库名等**内部或流程元信息**。
- **示例（须按本案替换检索词与渠道）**：

  > 检索说明：在**国家知识产权局专利公布公告系统**及 **Google Patents** 中，以「批任务调度」「异构集群调度」「任务队列重排」「负载感知调度」等为检索词进行检索（部分检索在 IPC 分类 B01J20 类下收口）；部分条目的公开文本与著录项以 Google Patents 页面复核。

查新笔记（Agent 内部或对话留档）仍可记录是否调用脚本、是否降级 WebSearch；**上述内容不得原样抄进交底书 3.1/3.3**。
