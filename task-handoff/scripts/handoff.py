#!/usr/bin/env python3
"""task-handoff 交接契约脚手架与校验器。

只用标准库。三个子命令：
  new   从 assets/template.md 生成一份交接记录
  check 校验结构、占位符、路径可达性、已完成项的证据
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

# 省略式引用与未完成标记：出现即视为交接未写完
BAD_MARKERS = (
    (re.compile(r"见上文|同上|如前所述|如上所述|see above|as above|as discussed above", re.I), "省略式引用"),
    (re.compile(r"\bTBD\b|\bTODO\b|待补充|待填写"), "未完成标记"),
    (re.compile(r"\{\{[^}]*\}\}"), "未替换的模板变量"),
    (re.compile(r"<[^<>\n]*[\u4e00-\u9fff…][^<>\n]*>"), "未替换的占位符"),
    (re.compile(r"（略）|\(略\)"), "省略标记"),
)
HEADING_RE = re.compile(r"^##(?!#)\s*(?:(\d+)\s*[.、)．]\s*)?(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
DONE_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
VERIFY_RE = re.compile(r"验证\s*[:：]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


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


def iter_sections(body: str):
    """围栏代码块内的 ## 不算标题。返回 [(序号|None, 归一标题, 正文行列表)]。"""
    sections = []
    current = None
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if current is not None:
                current[2].append(line)
            continue
        match = None if in_fence else HEADING_RE.match(line)
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
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def block_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - block_width(text))


def resolve_root(meta: dict, record: Path) -> Path:
    declared = (meta or {}).get("project_root", "").strip()
    if declared and declared != "-":
        return Path(declared).expanduser().resolve()
    return record.parent.parent.resolve()


# ---------------------------------------------------------------- 校验


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
    if meta.get("task") and not SLUG_RE.match(meta["task"]):
        warnings.append(f"task 建议用 ASCII slug（小写字母、数字、- _ .），跨工具更稳：{meta['task']!r}")
    head = meta.get("head", "")
    if head and head != "-" and not re.match(r"^[0-9a-f]{7,40}$", head):
        warnings.append(f"head 不是合法短 sha：{head!r}")
    root = resolve_root(meta, record)
    if not root.exists():
        warnings.append(f"project_root 不存在（记录可能已迁走）：{root}")

    sections = iter_sections(body)
    found = {}
    order = []
    for num, title, lines in sections:
        if title in found:
            errors.append(f"§{title} 重复出现")
            continue
        found[title] = lines
        order.append(title)

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
        joined = "\n".join(lines)
        for pattern, label in BAD_MARKERS:
            hit = pattern.search(joined)
            if hit:
                errors.append(f"§{title} 含{label}：{hit.group(0)!r}")
        if len("".join(lines).strip()) < 12:
            warnings.append(f"§{title} 内容过短，确认是否写清")

    # §2：每个 [x] 必须有验证
    for block in group_blocks(outside_fences(bodies.get("当前状态", []))):
        if DONE_RE.match(block[0]) and not VERIFY_RE.search("\n".join(block)):
            errors.append(f"§2 已完成项缺验证：{block[0].strip()[:60]}")

    # §3：路径必须从接手方可达
    artifact_lines = bodies.get("在途产物", [])
    has_inline = False
    for line in outside_fences(artifact_lines):
        match = BULLET_RE.match(line)
        if not match:
            if line.strip().startswith("```") or line.strip().startswith("~~~"):
                continue
            continue
        item = match.group(1).strip()
        if item.startswith("内联"):
            has_inline = True
            continue
        if not item.startswith("文件"):
            warnings.append(f"§3 条目未以「文件：」或「内联：」开头：{item[:50]}")
            continue
        spans = CODE_SPAN_RE.findall(item)
        if not spans:
            errors.append(f"§3 缺可定位路径（用反引号包住路径）：{item[:60]}")
            continue
        raw = spans[0].strip()
        target = Path(raw).expanduser()
        if not target.is_absolute():
            target = root / target
        if not target.exists():
            errors.append(f"§3 引用路径不可达：{raw}（以 {root} 为基准）")
        if re.search(r"[\\/]Temp[\\/]|/tmp/", raw, re.I):
            warnings.append(f"§3 引用了临时目录，接手方可能读不到：{raw}")
    if has_inline and not any(
        line.strip().startswith(("```", "~~~")) for line in artifact_lines
    ):
        errors.append("§3 有「内联」条目但缺围栏代码块（内容必须整段粘贴）")

    # §9：交接链至少一条
    chain = [line for line in bodies.get("交接链", []) if BULLET_RE.match(line)]
    if not chain:
        errors.append("§9 交接链没有记录，至少写一条本次交接")

    return errors, warnings


def group_blocks(lines):
    """把缩进续行归并到所属 bullet。"""
    blocks = []
    for line in lines:
        if BULLET_RE.match(line) or line.lstrip().startswith(("-", "*")) and not line.startswith((" ", "\t")):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return blocks


# ---------------------------------------------------------------- 子命令


def git_value(root: Path, *args: str) -> str:
    if not (root / ".git").exists():
        return "-"
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "-"
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and value else "-"


def cmd_new(args) -> int:
    root = Path(args.root).expanduser().resolve()
    slug = args.task.strip()
    if not SLUG_RE.match(slug):
        print(f"[task-handoff] task 只能用 ASCII slug（小写字母、数字、- _ .）：{slug!r}", file=sys.stderr)
        return 2
    if not TEMPLATE.exists():
        print(f"[task-handoff] 模板缺失：{TEMPLATE}", file=sys.stderr)
        return 2
    target_dir = root / ".handoff"
    target = target_dir / f"{slug}.md"
    if target.exists() and not args.force:
        print(f"[task-handoff] 已存在：{target}（重复交接请覆盖写；确需重建加 --force）", file=sys.stderr)
        return 2

    now = datetime.now().astimezone()
    stamp = now.strftime("%Y-%m-%dT%H:%M%z")
    stamp = f"{stamp[:-2]}:{stamp[-2:]}"
    values = {
        "task": slug,
        "title": args.title.strip(),
        "boundary": args.boundary,
        "from": args.from_ or "unspecified",
        "to": args.to.strip(),
        "updated": stamp,
        "project_root": root.as_posix(),
        "branch": git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": git_value(root, "rev-parse", "--short", "HEAD"),
    }
    text = read_text(TEMPLATE)
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, value)

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
    parser = argparse.ArgumentParser(prog="handoff.py", description="task-handoff 契约脚手架与校验器")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="生成一份交接记录")
    new.add_argument("--root", default=".", help="工作根（默认当前目录）")
    new.add_argument("--task", required=True, help="任务 slug，跨多次交接保持不变")
    new.add_argument("--title", required=True, help="人读的标题")
    new.add_argument("--boundary", required=True, choices=BOUNDARIES)
    new.add_argument("--to", required=True, help="接手方：工具/模型/人或 agent 名")
    new.add_argument("--from", dest="from_", default=None, help="交接方标识，默认 unspecified")
    new.add_argument("--force", action="store_true", help="覆盖已存在的记录")
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
