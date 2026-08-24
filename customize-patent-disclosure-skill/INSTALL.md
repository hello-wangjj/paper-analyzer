# 安装说明

本技能遵循 [AgentSkills](https://agentskills.io) 常见布局：仓库根目录即技能根目录，内含 `SKILL.md`。

## Claude Code

在 **git 仓库根目录** 下安装：

```bash
mkdir -p .claude/skills
git clone <本仓库 URL> .claude/skills/patent-disclosure-skill
```

或使用本地路径复制到 `.claude/skills/patent-disclosure-skill`。

运行时环境通常会设置 **`CLAUDE_SKILL_DIR`** 指向该技能目录；`SKILL.md` 中的 `${CLAUDE_SKILL_DIR}/prompts/...` 即解析到此路径。

## Cursor

Cursor 支持 [Agent Skills](https://www.cursor.com/docs/context/skills) 约定：每个技能是一个**子文件夹**，内含根级 `SKILL.md`（`name` 字段须与文件夹名一致，本仓库为 `patent-disclosure-skill`）。可将**本仓库完整内容**（含 `prompts/`、`tools/` 等）放在下列位置之一，重启 Cursor 后在 **Settings → Rules** 中查看是否已被发现；亦可用 Agent 输入 `/` 后选择技能名。

### 用户主目录（全局，所有项目可用）

| 系统 | 推荐路径 |
|------|----------|
| Windows | `%USERPROFILE%\.cursor\skills\patent-disclosure-skill\`（即 `C:\Users\<用户名>\.cursor\skills\patent-disclosure-skill\`） |
| macOS / Linux | `~/.cursor/skills/patent-disclosure-skill/` |

示例（将仓库克隆到全局技能目录）：

```bash
mkdir -p ~/.cursor/skills
git clone <本仓库 URL> ~/.cursor/skills/patent-disclosure-skill
```

Windows（PowerShell）：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills"
git clone <本仓库 URL> "$env:USERPROFILE\.cursor\skills\patent-disclosure-skill"
```

### 项目目录（仅当前仓库）

将本技能放在当前工作区下的：

`<项目根>/.cursor/skills/patent-disclosure-skill/`

（同样需包含完整仓库文件树，且 **`SKILL.md` 中 `name: patent-disclosure-skill` 与文件夹名一致**。）

### 与「仅打开文件夹」等价关系

若未使用上述 `skills/` 布局，也可**直接用 Cursor 打开本仓库根目录**作为工作区；此时将 **`CLAUDE_SKILL_DIR`** 理解为「包含 `SKILL.md` 的目录」，prompts 路径为 `./prompts/*.md`，与 `SKILL.md` 示例命令中的 **`${CLAUDE_SKILL_DIR}`** 同义。

为与 Claude Code 迁移一致，Cursor 也会扫描 **`~/.claude/skills/`**、项目内 **`.claude/skills/`** 等路径；详见 Cursor 官方文档与当前版本设置项。

## 可选依赖

若仅使用交底书 Markdown 流程，不必安装 Python。

若需使用 **`tools/md_to_docx.py`**（Markdown → Word）、**`tools/docx_to_md.py`**（Word → Markdown + 图片）或 **`tools/pptx_to_md.py`**（PPT → Markdown + 图片，供扫描）：

```bash
pip install -r requirements.txt
```

交底书定稿须同时产出 **.md + .docx**，且将 **mermaid**（**4.2.1 系统框图**与 **4.2.3 流程图**）经 **`tools/mermaid_render.py`** 转为 PNG 嵌入。**mermaid 由 Playwright + 内置 `tools/vendor/mermaid.min.js` 渲染，无需 Node.js / npm / mmdc**，与查新共用 `tools/browser.py`（系统 Chrome → Edge → 自带 Chromium）。详见 **`tools/README.md`**。

## 国知局公布公告站抓取（Step 5 查新优先路径）

若需使用 **`tools/cnipa_epub_search.py`**（一步，推荐，支持 `--type invention|utility_model|design|all`）或 **`tools/cnipa_epub_crawler.py`** / **`tools/cnipa_epub_parse.py`**（[epub.cnipa.gov.cn](http://epub.cnipa.gov.cn/)，见 `prompts/prior_art_search.md`）：

```bash
pip install -r requirements.txt      # playwright 已在主依赖中
python tools/browser.py --probe      # 先探测；ok=true（系统 Chrome/Edge 或自带 Chromium）时直接检索，禁止再装浏览器
# 仅当 ok=false 且本机无 Chrome/Edge 时：
python -m playwright install chromium
```

**Windows 终端中文**：`cnipa_epub_search.py` / `cnipa_epub_crawler.py` 已对 stdout/stderr 强制 **UTF-8**，不必先 `chcp 65001`。**stderr 有字不等于失败**：以**退出码 0** 与 stdout 的 `EPUB_HITS_JSON:` 为准；PowerShell 把 stderr 标成 `NativeCommandError` 或乱码时，勿误判为检索失败。勿用 `2>&1` 合并流后找 JSON。

未安装 Playwright 时 Step 5 仍可按该 prompt 降级为 **WebSearch**（如 Google 学术）。
