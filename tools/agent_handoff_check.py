#!/usr/bin/env python3
"""Validate and summarize the repository's agent handoff control plane.

Usage:
  python tools/agent_handoff_check.py --verify
  python tools/agent_handoff_check.py --resume

The checker deliberately uses only the standard library.  It validates the
facts that must survive a context compaction: branch, recorded commits,
code-only worktree state, the next-action contract, secret hygiene, local
links, and unmatched BEGIN/END long-operation records.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOFF = ROOT / "docs" / "HANDOFF.zh-CN.md"
DEFAULT_LOG = ROOT / "docs" / "HANDOFF_LOG.zh-CN.md"

CONTROL_PLANE = {
    "AGENTS.md",
    "docs/HANDOFF.zh-CN.md",
    "docs/HANDOFF_LOG.zh-CN.md",
    "docs/TOTK_PORT_PROGRESS.zh-CN.md",
    "docs/TOTK_PORT_SCAFFOLD.zh-CN.md",   # 计划文档与进度文档一样属交接控制面 | the plan document is part of the control plane just like the progress document
    "dm/android/tools/ci_checks.py",
    "tools/agent_handoff_check.py",
    "tools/test_agent_handoff_check.py",
}

REQUIRED_FRONTMATTER = (
    "protocol",
    "updated_at",
    "phase",
    "state",
    "branch",
    "observed_head",
    "origin_ref",
    "origin_head_at_checkpoint",
    "code_worktree",
    "next_action_id",
)

REQUIRED_SNAPSHOT_FIELDS = (
    "快照时间",
    "当前阶段",
    "当前分支",
    "观测 HEAD",
    "origin 对应分支",
    "代码工作区",
    "未提交代码文件",
    "未跟踪代码文件",
    "被忽略但重要的产物",
    "本次会话目标",
    "已完成（带证据）",
    "未完成",
    "最近一次成功命令",
    "最近一次失败命令及原因",
    "已验证产物路径",
    "当前阻塞",
    "需要用户提供的材料",
    "回滚点",
    "禁止事项",
)

REQUIRED_ACTION_FIELDS = (
    "ID",
    "状态",
    "工作目录",
    "前置条件",
    "动作",
    "命令或编辑目标",
    "成功判据",
    "失败判据",
    "回滚点",
    "需要写入的证据",
)

ALLOWED_STATES = {
    "ACTIVE",
    "CHECKPOINTING",
    "READY_FOR_HANDOFF",
    "BLOCKED_USER",
    "BLOCKED_EXTERNAL",
    "RECOVERING",
    "DONE",
}
ALLOWED_ACTION_STATES = {"READY", "BLOCKED", "DONE"}


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "git %s failed: %s"
            % (" ".join(args), result.stderr.decode("utf-8", "replace").strip())
        )
    return result.stdout.decode("utf-8", "replace").strip()


def git_ok(*args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return git_ok("merge-base", "--is-ancestor", ancestor, descendant)


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("HANDOFF 缺少 YAML frontmatter 起始行 ---")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("HANDOFF 缺少 YAML frontmatter 结束行 ---") from exc
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError("frontmatter 行无法解析: " + line)
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def section(text: str, heading: str) -> str:
    pattern = re.compile(r"(?m)^" + re.escape(heading) + r"\s*$")
    match = pattern.search(text)
    if not match:
        raise ValueError("缺少章节: " + heading)
    level = len(heading) - len(heading.lstrip("#"))
    rest = text[match.end():]
    next_heading = re.search(r"(?m)^#{1,%d} .+$" % level, rest)
    return rest[: next_heading.start()] if next_heading else rest


def bullet_value(body: str, label: str) -> str:
    pattern = re.compile(r"(?m)^\s*-\s*" + re.escape(label) + r"\s*[：:]\s*(.*)$")
    match = pattern.search(body)
    if not match:
        raise ValueError("缺少字段: " + label)
    value = match.group(1).strip()
    lines = body[match.end():].splitlines()
    for line in lines:
        if not line.strip():
            continue
        if re.match(r"^\s*-\s+", line):
            break
        if line.startswith("  ") or line.startswith("\t"):
            value += " " + line.strip()
            continue
        break
    # Markdown inline code is documentation formatting, not part of the value.
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def fenced_block_after(body: str) -> list[str]:
    match = re.search(r"(?ms)^```(?:text)?\s*\n(.*?)^```\s*$", body)
    if not match:
        raise ValueError("缺少工作区状态 fenced code block")
    return [line.rstrip() for line in match.group(1).splitlines() if line.strip()]


def normalize_status_line(line: str) -> str:
    line = line.rstrip()
    if len(line) < 4:
        return line
    status, path = line[:2], line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    path = path.strip('"').replace("\\", "/")
    return status + " " + path


def code_status_lines() -> list[str]:
    raw = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--short", "--untracked-files=all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if raw.returncode:
        raise RuntimeError(raw.stderr.decode("utf-8", "replace").strip())
    result: list[str] = []
    for line in raw.stdout.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        normalized = normalize_status_line(line)
        path = normalized[3:].strip() if len(normalized) >= 4 else ""
        if path in CONTROL_PLANE:
            continue
        result.append(normalized)
    return sorted(result)


def check_required_snapshot(body: str) -> list[str]:
    errors: list[str] = []
    for label in REQUIRED_SNAPSHOT_FIELDS:
        try:
            bullet_value(body, label)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def check_action(body: str, expected_id: str) -> list[str]:
    errors: list[str] = []
    values: dict[str, str] = {}
    for label in REQUIRED_ACTION_FIELDS:
        try:
            values[label] = bullet_value(body, label)
        except ValueError as exc:
            errors.append(str(exc))
    if values.get("ID") and values["ID"] != expected_id:
        errors.append("下一步动作 ID 与 frontmatter 不一致: %s != %s" % (values["ID"], expected_id))
    if values.get("状态") and values["状态"] not in ALLOWED_ACTION_STATES:
        errors.append("下一步动作状态非法: " + values["状态"])
    if values.get("状态") == "READY":
        for label in ("命令或编辑目标", "成功判据", "失败判据", "回滚点", "需要写入的证据"):
            if not values.get(label) or values[label] in {"N/A", "UNKNOWN", "TBD"}:
                errors.append("READY 动作缺少可执行字段: " + label)
    if values.get("工作目录") and values["工作目录"] != str(ROOT):
        errors.append("下一步动作工作目录不是仓库根目录: " + values["工作目录"])
    return errors


def check_local_links(text: str, base: Path) -> list[str]:
    errors: list[str] = []
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = target.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = (base / target.split("#", 1)[0]).resolve()
        if not path.exists():
            errors.append("本地链接不存在: " + target)
    return errors


def check_secrets(text: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
        errors.append("检测到私钥块")
    if re.search(r"(?im)^\s*(header_key|titlekek_[0-9a-f]{2}|key_area_key_application_[0-9a-f]{2})\s*=\s*[0-9a-f]{32,}\s*$", text):
        errors.append("检测到疑似 prod.keys 内容")
    tracked = run_git("ls-files")
    forbidden = (".nsp", ".nsz", ".xci", ".nca", ".keys", ".tik", ".cert")
    for path in tracked.splitlines():
        if path.lower().endswith(forbidden):
            errors.append("仓库跟踪了禁止的游戏/密钥文件: " + path)
    return errors


def check_long_operations(log_text: str) -> list[str]:
    errors: list[str] = []
    begins = re.findall(r"\[BEGIN\]\s+([A-Za-z0-9._-]+)", log_text)
    ends = re.findall(r"\[END\]\s+([A-Za-z0-9._-]+)", log_text)
    for op in sorted(set(begins) - set(ends)):
        errors.append("长操作 BEGIN 未闭合: " + op)
    for op in sorted(set(ends) - set(begins)):
        errors.append("长操作 END 无对应 BEGIN: " + op)
    return errors


def verify(handoff_path: Path, log_path: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        text = handoff_path.read_text(encoding="utf-8")
        log_text = log_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
    except Exception as exc:
        print("FAIL:", exc)
        return 1

    for key in REQUIRED_FRONTMATTER:
        if not fm.get(key):
            errors.append("frontmatter 缺少字段: " + key)

    state = fm.get("state", "")
    if state not in ALLOWED_STATES:
        errors.append("state 非法: " + state)

    try:
        branch = run_git("branch", "--show-current")
        head = run_git("rev-parse", "HEAD")
        origin_ref = fm.get("origin_ref", "")
        origin_head = run_git("rev-parse", origin_ref) if origin_ref else ""
    except Exception as exc:
        print("FAIL:", exc)
        return 1

    if fm.get("branch") and fm["branch"] != branch:
        errors.append("分支不一致: HANDOFF=%s Git=%s" % (fm["branch"], branch))
    observed = fm.get("observed_head", "")
    if observed:
        if not git_ok("cat-file", "-e", observed + "^{commit}"):
            errors.append("observed_head 不是有效提交: " + observed)
        elif not is_ancestor(observed, head):
            errors.append("observed_head 不是当前 HEAD 的祖先: " + observed)
    recorded_origin = fm.get("origin_head_at_checkpoint", "")
    if recorded_origin:
        if not git_ok("cat-file", "-e", recorded_origin + "^{commit}"):
            errors.append("origin_head_at_checkpoint 不是有效提交: " + recorded_origin)
        elif origin_head and not is_ancestor(recorded_origin, origin_head):
            errors.append("origin_head_at_checkpoint 不是远端 HEAD 的祖先: " + recorded_origin)
        elif origin_head and recorded_origin != origin_head:
            changed = [
                path for path in run_git("diff", "--name-only", recorded_origin + ".." + origin_head).splitlines()
                if path
            ]
            if not changed or not all(path in CONTROL_PLANE for path in changed):
                warnings.append("远端在快照后已前进且包含非控制面改动: %s -> %s" % (recorded_origin[:12], origin_head[:12]))

    actual_code = code_status_lines()
    actual_worktree = "DIRTY" if actual_code else "CLEAN"
    if fm.get("code_worktree") != actual_worktree:
        errors.append("代码工作区状态不一致: HANDOFF=%s Git=%s" % (fm.get("code_worktree"), actual_worktree))

    try:
        snapshot = section(text, "## 当前快照")
        errors.extend(check_required_snapshot(snapshot))
        status_body = section(text, "### 代码工作区（排除交接控制面）")
        documented_code = sorted(normalize_status_line(x) for x in fenced_block_after(status_body))
        if documented_code != actual_code:
            errors.append("代码工作区文件清单与 git status 不一致")
            errors.append("  HANDOFF: " + repr(documented_code))
            errors.append("  Git    : " + repr(actual_code))
    except ValueError as exc:
        errors.append(str(exc))

    action_count = len(re.findall(r"(?m)^## 下一步唯一动作\s*$", text))
    if action_count != 1:
        errors.append("必须且只能有一个“## 下一步唯一动作”，实际 %d 个" % action_count)
    else:
        try:
            errors.extend(check_action(section(text, "## 下一步唯一动作"), fm.get("next_action_id", "")))
        except ValueError as exc:
            errors.append(str(exc))

    errors.extend(check_local_links(text, handoff_path.parent))
    errors.extend(check_secrets(text))
    errors.extend(check_long_operations(log_text))

    for marker in ("TBD", "TODO"):
        if re.search(r"(?i)\b" + marker + r"\b", text):
            errors.append("HANDOFF 仍有未完成标记: " + marker)

    print("HANDOFF:", handoff_path)
    print("branch:", branch)
    print("HEAD:", head)
    print("origin:", origin_ref, origin_head)
    print("code_worktree:", actual_worktree)
    print("state:", state)
    print("next_action_id:", fm.get("next_action_id"))
    for warning in warnings:
        print("WARN:", warning)
    for error in errors:
        print("FAIL:", error)
    if errors:
        print("== VERIFY FAILED: %d error(s) ==" % len(errors))
        return 1
    print("== VERIFY OK ==")
    return 0


def resume(handoff_path: Path) -> int:
    text = handoff_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    snapshot = section(text, "## 当前快照")
    action = section(text, "## 下一步唯一动作")
    print("branch:", fm.get("branch", ""))
    print("observed_head:", fm.get("observed_head", ""))
    print("state:", fm.get("state", ""))
    print("phase:", fm.get("phase", ""))
    print("code_worktree:", fm.get("code_worktree", ""))
    print("next_action_id:", fm.get("next_action_id", ""))
    print("next_action:", bullet_value(action, "动作"))
    print("command_or_edit:", bullet_value(action, "命令或编辑目标"))
    print("success:", bullet_value(action, "成功判据"))
    print("blocker:", bullet_value(snapshot, "当前阻塞"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    if args.verify:
        return verify(args.handoff.resolve(), args.log.resolve())
    return resume(args.handoff.resolve())


if __name__ == "__main__":
    sys.exit(main())