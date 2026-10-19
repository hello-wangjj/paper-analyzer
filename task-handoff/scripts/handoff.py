#!/usr/bin/env python3
"""task-handoff 交接契约脚手架与校验器。

只用标准库。三个子命令：
  new   从 assets/template.md 生成一份交接记录
  check 校验结构、占位符、sha:path 可达性、已完成项的证据
  list  列出 .handoff 目录下的交接记录

退出码：0 无错误（可能有 WARN）、1 有 ERROR、2 用法或 IO 错误。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

CONTRACT_VERSION = "1"
STATUSES = ("waiting", "active", "blocked", "done", "abandoned")
BOUNDARIES = ("context-exhaustion", "tool-switch", "agent-handoff", "migration")
REQUIRED_FM = (
    "handoff",
    "task",
    "title",
    "status",
    "boundary",
    "from",
    "to",
    "updated",
)
SECTIONS = (
    "目标与验收",
    "当前状态",
    "在途产物",
    "已锁定决策",
    "已否决路径",
    "环境与重建",
    "授权与风险",
    "下一步",
    "交接链",
)
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "template.md"

# 省略式引用与未完成标记：出现即视为交接未写完（只查围栏外，围栏内是产物原文）
SIMPLE_BAD_MARKERS = (
    (re.compile(r"见上文|同上|如前所述|如上所述|see above|as above|as discussed above", re.I), "省略式引用"),
    (re.compile(r"\bTBD\b|\bTODO\b|待补充|待填写"), "未完成标记"),
    (re.compile(r"\{\{[^}]*\}\}"), "未替换的模板变量"),
    (re.compile(r"（略）|\(略\)"), "省略标记"),
)
PLACEHOLDER_RE = re.compile(r"<([^<>\n]{1,80})>")
TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")
HEADING_RE = re.compile(r"^##(?!#)\s*(?:(\d+)\s*[.、)．]\s*)?(.+?)\s*$")
TOP_BULLET_RE = re.compile(r"^[-*]\s+")
DONE_RE = re.compile(r"^[-*]\s*\[[xX]\]")
VERIFY_RE = re.compile(r"验证\s*[:：]\s*(\S.*)$", re.M)
VERIFY_STRIP_RE = re.compile(r"[\s\-—–:：,，.。;；、`'\"()（）\[\]<>]+")
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
RANGE_RE = re.compile(r"^\d+(?:-\d+)?$")
CHAIN_RE = re.compile(
    r"^[-*]\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})\s*·\s*(.+?)\s*→\s*(.+?)\s*·\s*([a-z-]+)\s*·\s*(.+)$"
)
MSYS_PATH_RE = re.compile(r"^/[A-Za-z]/")
# 与 assets/template.md 内联围栏的占位符措辞对应，改模板时同步改这里
INLINE_TEMPLATE_HINT = "磁盘上不存在的内容"


# ---------------------------------------------------------------- 基础解析


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"[task-handoff] {path} 不是 UTF-8 文本：{exc}") from exc
    except OSError as exc:
        raise SystemExit(f"[task-handoff] 读取失败 {path}：{exc}") from exc


def split_front_matter(text: str):
    """返回 (front_matter_dict|None, body, 起始行号)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, 0
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            meta = {}
            for raw in lines[1:idx]:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if ":" not in raw:
                    continue
                key, _, value = raw.partition(":")
                meta[key.strip()] = value.strip().strip("\"'")
            return meta, "\n".join(lines[idx + 1 :]), idx + 1
    return None, text, 0


def strip_paren(title: str) -> str:
    title = re.sub(r"[（(][^）)]*[）)]", "", title)
    return title.strip()


def fence_state(state, line: str):
    """返回新的围栏状态。state 为 None（围栏外）或 (字符, 长度)。"""
    match = FENCE_RE.match(line)
    if not match:
        return state
    marker = match.group(2)
    char, count = marker[0], len(marker)
    info = match.group(3)
    if state is None:
        # 开围栏：反引号围栏的 info string 不能再含反引号
        if char == "`" and "`" in info:
            return state
        return (char, count)
    # 闭围栏必须同字符、长度不短于开围栏、且后面没有 info
    if char == state[0] and count >= state[1] and not info.strip():
        return None
    return state


def iter_sections(body: str):
    """围栏代码块内的 ## 不算标题。返回 [(序号|None, 归一标题, 正文行列表)]。"""
    sections = []
    current = None
    state = None
    for line in body.splitlines():
        was_in_fence = state is not None
        is_fence_line = FENCE_RE.match(line) is not None
        if is_fence_line:
            state = fence_state(state, line)
        match = None if (was_in_fence or is_fence_line) else HEADING_RE.match(line)
        if match:
            if current is not None:
                sections.append(current)
            current = (match.group(1), strip_paren(match.group(2)), [])
        elif current is not None:
            current[2].append(line)
    if current is not None:
        sections.append(current)
    return sections


def meaningful_lines(lines):
    """去掉空行与说明块（以 > 开头），用于判断某节是否真的写了内容。"""
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        out.append(line)
    return out


def outside_fences(lines):
    """围栏内的内容是产物原文，不参与结构判定。"""
    out = []
    state = None
    for line in lines:
        if FENCE_RE.match(line):
            state = fence_state(state, line)
            continue
        if state is None:
            out.append(line)
    return out


def has_unclosed_fence(body: str) -> bool:
    state = None
    for line in body.splitlines():
        state = fence_state(state, line)
    return state is not None


def group_blocks(lines):
    """把缩进续行归并到所属 bullet；只有顶格 bullet 开启新块。"""
    blocks = []
    for line in lines:
        if TOP_BULLET_RE.match(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return blocks


def is_placeholder(inner: str) -> bool:
    """区分「模板占位符」与正文里的比较表达式。"""
    if inner != inner.strip():
        return False
    if "://" in inner:
        return False
    return not any(ch in inner for ch in "=<>")


def find_bad_markers(text: str):
    hits = []
    for pattern, label in SIMPLE_BAD_MARKERS:
        match = pattern.search(text)
        if match:
            hits.append((match.group(0), label))
    for match in PLACEHOLDER_RE.finditer(text):
        if is_placeholder(match.group(1)):
            hits.append((match.group(0), "未替换的占位符"))
    return hits


def has_verify(text: str) -> bool:
    """验证：之后必须有至少两个非标点字符，空值或单个破折号不算。"""
    for match in VERIFY_RE.finditer(text):
        if len(VERIFY_STRIP_RE.sub("", match.group(1))) >= 2:
            return True
    return False


def block_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - block_width(text))


def resolve_root(meta: dict, record: Path) -> tuple[Path, bool]:
    """返回 (工作根, 声明路径是否本机失效)。记录随仓库迁到别的机器后，写死的
    project_root 不存在；此时回退到 .handoff 的上级继续校验，而不是整份报错。"""
    declared = ((meta or {}).get("project_root") or "").strip()
    if declared and declared != "-":
        path = Path(declared)
        if path.is_absolute():
            if path.exists():
                return path, False
            return record.parent.parent.resolve(), True
    return record.parent.parent.resolve(), False


# ---------------------------------------------------------------- git 辅助


def git_run(root: Path, *args: str):
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def git_value(root: Path, *args: str) -> str:
    proc = git_run(root, *args)
    if proc is None or proc.returncode != 0:
        return "-"
    value = proc.stdout.strip()
    return value or "-"


def is_git_repo(root: Path) -> bool:
    proc = git_run(root, "rev-parse", "--is-inside-work-tree")
    return proc is not None and proc.returncode == 0 and proc.stdout.strip() == "true"


def git_has_commit(root: Path, sha: str) -> bool:
    proc = git_run(root, "cat-file", "-e", f"{sha}^{{commit}}")
    return proc is not None and proc.returncode == 0


def git_has_path(root: Path, sha: str, relpath: str) -> bool:
    proc = git_run(root, "cat-file", "-e", f"{sha}:{relpath}")
    return proc is not None and proc.returncode == 0


def git_line_count(root: Path, sha: str, relpath: str):
    proc = git_run(root, "show", f"{sha}:{relpath}")
    if proc is None or proc.returncode != 0:
        return None
    if "\x00" in proc.stdout:  # 二进制内容按行校验没有意义
        return None
    return len(proc.stdout.splitlines())


# ---------------------------------------------------------------- 校验


def check_artifact(item: str, root: Path, errors: list[str], warnings: list[str]) -> None:
    """§3 条目：路径必须能在 project_root 的 Git 对象里定位到同一份内容。"""
    spans = CODE_SPAN_RE.findall(item)
    if not spans:
        errors.append(f"§3 缺可定位路径（用反引号包住路径）：{item[:60]}")
        return

    raw = spans[0].strip()
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = root / target

    # 目录产物：目录存在即可，不要求 sha 与行号
    if target.is_dir():
        return

    sha = spans[1].strip() if len(spans) > 1 else ""
    rng = spans[2].strip() if len(spans) > 2 else ""
    if not SHA_RE.match(sha):
        errors.append(f"§3 缺 sha 或格式不对（应写 路径 @ sha : 起-止行）：{item[:60]}")
        return
    if not RANGE_RE.match(rng):
        errors.append(f"§3 缺行号区间（应写 路径 @ sha : 起-止行）：{item[:60]}")
        return

    if not is_git_repo(root):
        if not target.exists():
            errors.append(f"§3 引用路径不可达：{raw}（以 {root} 为基准）")
        else:
            warnings.append(f"§3 非 git 仓库，无法校验 sha:path：{raw}")
        return

    try:
        relpath = target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        if target.exists():
            warnings.append(f"§3 跨仓路径只校验了本机存在性，无法校验 sha:path：{raw}")
        else:
            errors.append(f"§3 引用路径不可达：{raw}")
        return

    if not git_has_commit(root, sha):
        errors.append(f"§3 sha 不存在于仓库：{sha}")
        return
    if not git_has_path(root, sha, relpath):
        errors.append(
            f"§3 文件在 {sha} 中不存在（未提交？未提交产物请内联粘贴，或先提交）：{relpath}"
        )
        return

    total = git_line_count(root, sha, relpath)
    if total is None:
        warnings.append(f"§3 无法按行校验（二进制或读取失败），行号未检查：{raw}")
    else:
        bounds = rng.split("-")
        start = int(bounds[0])
        end = int(bounds[-1])
        if start < 1 or end < start:
            errors.append(f"§3 行号区间非法：{rng}")
        elif end > total:
            errors.append(f"§3 行号 {rng} 超出 {sha}:{relpath} 的 {total} 行")


def validate(record: Path):
    errors: list[str] = []
    warnings: list[str] = []
    text = read_text(record)
    meta, body, _ = split_front_matter(text)

    if meta is None:
        errors.append("缺 front matter（文件须以 --- 开头，含契约版本与状态字段）")
        meta = {}

    if meta.get("handoff") != CONTRACT_VERSION:
        errors.append(f"front matter handoff 必须是 {CONTRACT_VERSION}，实为 {meta.get('handoff')!r}")
    for key in REQUIRED_FM:
        if not meta.get(key):
            errors.append(f"front matter 缺字段：{key}")
    if meta.get("status") and meta["status"] not in STATUSES:
        errors.append(f"status 非法：{meta['status']!r}（可选 {' / '.join(STATUSES)}）")
    if meta.get("boundary") and meta["boundary"] not in BOUNDARIES:
        errors.append(f"boundary 非法：{meta['boundary']!r}（可选 {' / '.join(BOUNDARIES)}）")
    if meta.get("updated") and not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", meta["updated"]):
        errors.append(f"updated 须为 ISO 时间（YYYY-MM-DDTHH:MM+08:00），实为 {meta['updated']!r}")

    task = (meta.get("task") or "").strip()
    if task and not SLUG_RE.match(task):
        warnings.append(f"task 建议用 ASCII slug（小写字母、数字、- _ .），跨工具更稳：{task!r}")
    if task and task != record.stem:
        errors.append(f"task 字段 {task!r} 与文件名 {record.stem!r} 不一致（契约要求两者相等）")

    declared_root = (meta.get("project_root") or "").strip()
    if declared_root and declared_root != "-":
        if MSYS_PATH_RE.match(declared_root):
            errors.append(f"project_root 是 MSYS 路径，请写盘符路径（C:/...）：{declared_root}")
        elif not Path(declared_root).is_absolute():
            errors.append(f"project_root 必须是绝对路径：{declared_root!r}")

    root, stale_root = resolve_root(meta, record)
    if stale_root:
        warnings.append(
            f"project_root 在本机不存在，已回退到记录所在目录：{meta.get('project_root')} → {root.as_posix()}"
        )

    head = (meta.get("head") or "").strip()
    if head and head != "-":
        if not SHA_RE.match(head):
            errors.append(f"head 不是合法短 sha：{head!r}")
        elif is_git_repo(root):
            if not git_has_commit(root, head):
                errors.append(f"head 不存在于仓库：{head}")
            else:
                current = git_value(root, "rev-parse", "--short", "HEAD")
                if current != "-" and not (current.startswith(head) or head.startswith(current)):
                    warnings.append(f"head {head} 与当前 HEAD {current} 不一致，接手方应先看差异")

    sections = iter_sections(body)
    if has_unclosed_fence(body):
        errors.append("存在未闭合的围栏代码块，其后的节会被吞掉（检查内联内容里的 ``` 数量）")
    found = {}
    order = []
    for num, title, lines in sections:
        if title in found:
            errors.append(f"§{title} 重复出现")
            continue
        found[title] = lines
        order.append(title)
        if title in SECTIONS:
            expected = SECTIONS.index(title) + 1
            if num is None:
                errors.append(f"§{title} 缺序号（应为 {expected}）")
            elif int(num) != expected:
                errors.append(f"§{title} 序号应为 {expected}，实为 {num}")

    for title in SECTIONS:
        if title not in found:
            errors.append(f"缺节：§{title}")
    indices = [SECTIONS.index(t) for t in order if t in SECTIONS]
    if indices != sorted(indices):
        errors.append("节顺序与契约不一致（应按 §1–§9 排列）")

    bodies = {title: meaningful_lines(found.get(title, [])) for title in SECTIONS}

    for title, lines in bodies.items():
        if title not in found:
            continue
        if not lines:
            errors.append(f"§{title} 为空（说明行不计入内容）")
            continue
        # 坏标记只查围栏外：围栏内是 verbatim 产物原文，TODO/<vector>/「见上文」是内容不是缺陷
        joined = "\n".join(outside_fences(lines))
        for hit_text, label in find_bad_markers(joined):
            errors.append(f"§{title} 含{label}：{hit_text!r}")
        if len("".join(lines).strip()) < 12:
            warnings.append(f"§{title} 内容过短，确认是否写清")

    # §2：每个 [x] 必须有可读的验证内容
    for block in group_blocks(outside_fences(bodies.get("当前状态", []))):
        if DONE_RE.match(block[0]) and not has_verify("\n".join(block)):
            errors.append(f"§2 已完成项缺验证：{block[0].strip()[:60]}")

    # §3：路径必须在 sha 对应的 Git 对象中存在，行号不得越界
    artifact_lines = bodies.get("在途产物", [])
    has_inline = False
    for line in outside_fences(artifact_lines):
        match = TOP_BULLET_RE.match(line)
        if not match:
            continue
        item = line[match.end() :].strip()
        if item.startswith("内联"):
            has_inline = True
            continue
        if not item.startswith("文件"):
            warnings.append(f"§3 条目未以「文件：」或「内联：」开头：{item[:50]}")
            continue
        check_artifact(item, root, errors, warnings)
    if has_inline and not any(FENCE_RE.match(line) for line in artifact_lines):
        errors.append("§3 有「内联」条目但缺围栏代码块（内容必须整段粘贴）")

    # 围栏内容不参与坏标记扫描，这里单独兜住没真贴内容的内联条目
    fenced: list[str] = []
    state = None
    for line in artifact_lines:
        if FENCE_RE.match(line):
            state = fence_state(state, line)
            continue
        if state is not None:
            fenced.append(line)
    fenced_text = "\n".join(fenced)
    if INLINE_TEMPLATE_HINT in fenced_text:
        errors.append("§3 内联围栏仍是模板占位符（整段粘贴实际内容，或删掉该条目与围栏）")
    elif has_inline and not fenced_text.strip():
        errors.append("§3 有「内联」条目但围栏内容为空")

    # §9：交接链至少一条，且每行格式可审计
    chain_lines = [line for line in bodies.get("交接链", []) if TOP_BULLET_RE.match(line)]
    if not chain_lines:
        errors.append("§9 交接链没有记录，至少写一条本次交接")
    for line in chain_lines:
        match = CHAIN_RE.match(line.strip())
        if not match:
            errors.append(f"§9 格式不符（时间 · 从 → 到 · boundary · 摘要）：{line.strip()[:60]}")
        elif match.group(4) not in BOUNDARIES:
            errors.append(f"§9 boundary 非法：{match.group(4)!r}（可选 {' / '.join(BOUNDARIES)}）")

    # status 与 §8 的一致性：完成态不该还留着待办
    if meta.get("status") == "done":
        next_lines = bodies.get("下一步", [])
        first = next((line.strip() for line in next_lines if line.strip()), "")
        if first and not first.startswith("无"):
            warnings.append("status 为 done 但 §8 仍有下一步内容，确认是否应保持 waiting/active")

    return errors, warnings


# ---------------------------------------------------------------- 子命令


def single_line(value: str, name: str):
    text = (value or "").strip()
    if not text:
        return None, f"{name} 不能为空"
    if "\n" in value or "\r" in value:
        return None, f"{name} 不能包含换行"
    return text, None


def cmd_new(args) -> int:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"[task-handoff] 工作根不存在：{root}", file=sys.stderr)
        return 2

    slug = args.task.strip()
    if not SLUG_RE.match(slug):
        print(f"[task-handoff] task 只能用 ASCII slug（小写字母、数字、- _ .）：{slug!r}", file=sys.stderr)
        return 2

    title, err = single_line(args.title, "--title")
    if err:
        print(f"[task-handoff] {err}", file=sys.stderr)
        return 2
    to, err = single_line(args.to, "--to")
    if err:
        print(f"[task-handoff] {err}", file=sys.stderr)
        return 2
    from_, err = single_line(args.from_ or "unspecified", "--from")
    if err:
        print(f"[task-handoff] {err}", file=sys.stderr)
        return 2

    if not TEMPLATE.exists():
        print(f"[task-handoff] 模板缺失：{TEMPLATE}", file=sys.stderr)
        return 2

    target_dir = root / ".handoff"
    target = target_dir / f"{slug}.md"
    if target.exists():
        print(f"[task-handoff] 已存在：{target}", file=sys.stderr)
        print(
            "[task-handoff] 重复交接请直接编辑该文件：更新 front matter 并追加 §9；不要重建（会丢历史）",
            file=sys.stderr,
        )
        return 2

    now = datetime.now().astimezone()
    stamp = now.strftime("%Y-%m-%dT%H:%M%z")
    stamp = f"{stamp[:-2]}:{stamp[-2:]}"
    values = {
        "task": slug,
        "title": title,
        "boundary": args.boundary,
        "from": from_,
        "to": to,
        "updated": stamp,
        "project_root": root.as_posix(),
        "branch": git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": git_value(root, "rev-parse", "--short", "HEAD"),
    }
    text = TEMPLATE_VAR_RE.sub(
        lambda match: values.get(match.group(1), match.group(0)), read_text(TEMPLATE)
    )

    prefix = git_value(root, "rev-parse", "--show-prefix")
    if prefix not in ("-", ""):
        print(
            f"[task-handoff] 提示：工作根位于仓库子目录（{prefix}），project_root 按当前路径写入",
            file=sys.stderr,
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"[task-handoff] 已创建：{target}")
    print(f"[task-handoff] 填完后校验：python scripts/handoff.py check {target_dir.as_posix()}")
    return 0


def collect(path: str | None) -> list[Path]:
    if path:
        base = Path(path).expanduser()
        if base.is_file():
            return [base]
        if base.is_dir():
            return sorted(p for p in base.glob("*.md") if p.is_file())
        print(f"[task-handoff] 路径不存在：{base}", file=sys.stderr)
        return []
    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        candidate = parent / ".handoff"
        if candidate.is_dir():
            return sorted(p for p in candidate.glob("*.md") if p.is_file())
    return []


def report_missing(path: str | None) -> int:
    if path:
        print(f"[task-handoff] 目录下没有 .md 记录：{path}", file=sys.stderr)
    else:
        print("[task-handoff] 未找到交接记录（未给路径时从当前目录向上查找 .handoff/）", file=sys.stderr)
    return 2


def cmd_check(args) -> int:
    records = collect(args.path)
    if not records:
        return report_missing(args.path)
    total_err = 0
    total_warn = 0
    print(f"[task-handoff] 检查 {len(records)} 个文件")
    for record in records:
        errors, warnings = validate(record)
        total_err += len(errors)
        total_warn += len(warnings)
        print(f"\n{record.name}")
        if not errors and not warnings:
            print("  [OK]   结构完整，无待补内容")
        for item in errors:
            print(f"  [ERROR] {item}")
        for item in warnings:
            print(f"  [WARN]  {item}")
    print(f"\n汇总：{total_err} 错误 · {total_warn} 警告")
    return 1 if total_err else 0


def cmd_list(args) -> int:
    records = collect(args.path)
    if not records:
        return report_missing(args.path)
    rows = []
    for record in records:
        meta, _, _ = split_front_matter(read_text(record))
        meta = meta or {}
        rows.append(
            (
                meta.get("task") or record.stem,
                meta.get("status") or "?",
                meta.get("boundary") or "?",
                meta.get("updated") or "?",
                meta.get("to") or "?",
                record.name,
            )
        )
    rows.sort(key=lambda row: (row[3], row[0]), reverse=True)
    headers = ("TASK", "STATUS", "BOUNDARY", "UPDATED", "TO", "FILE")
    widths = [max(block_width(r[i]) for r in rows + [headers]) for i in range(len(headers))]
    line = "  ".join(pad(headers[i], widths[i]) for i in range(len(headers)))
    print(line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(pad(row[i], widths[i]) for i in range(len(row))))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            # GBK 管道下遇不可编码字符替换为 ? ，不让校验结果本身打不出来
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass
    parser = argparse.ArgumentParser(prog="handoff.py", description="task-handoff 契约脚手架与校验器")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="生成一份交接记录")
    new.add_argument("--root", default=".", help="工作根（默认当前目录）")
    new.add_argument("--task", required=True, help="任务 slug，跨多次交接保持不变")
    new.add_argument("--title", required=True, help="人读的标题（单行）")
    new.add_argument("--boundary", required=True, choices=BOUNDARIES)
    new.add_argument("--to", required=True, help="接手方：工具/模型/人或 agent 名")
    new.add_argument("--from", dest="from_", default=None, help="交接方标识，默认 unspecified")
    new.set_defaults(func=cmd_new)

    check = sub.add_parser("check", help="校验交接记录")
    check.add_argument("path", nargs="?", help="文件或 .handoff 目录；省略时向上查找")
    check.set_defaults(func=cmd_check)

    listing = sub.add_parser("list", help="列出交接记录")
    listing.add_argument("path", nargs="?", help="文件或 .handoff 目录；省略时向上查找")
    listing.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
