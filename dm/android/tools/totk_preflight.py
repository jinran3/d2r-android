#!/usr/bin/env python3
"""真机预检：把「设备之前能查的全套闸门」一键跑完，给出「可以推机 / 还差什么」的结论。

Preflight for the device run: run every gate that does not need the phone and
print an evidence line per gate plus a verdict ("ready to push" / "what is
still missing").

只做检查与打印，不改任何东西；退出码 0 = 全绿，1 = 有红项。
Checks and prints only; it changes nothing. Exit code 0 = all green, 1 = a red item.

用法：totk_preflight.py [--package <数据包.zip>] [--shaders <着色器目录>] [--code <机器码目录>]
                        [--bfsha <着色器归档目录>] [--index <着色器索引.tsv>] [--quick]
用法（英文）：totk_preflight.py [--package ...] [--shaders ...] [--code ...] [--bfsha ...] [--index ...] [--quick]
  --quick 跳过耗时的归档侧重算（变体键链那一项）
"""
import argparse, json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[3]
# 用仓里约定的解释器（3.12 的 venv），没有就退回当前解释器。
# Use the project's interpreter (the 3.12 venv) when present, otherwise the current one.
_VENV = pathlib.Path(r"D:\Switch\.tools\venv\Scripts\python.exe")
PY = str(_VENV) if _VENV.is_file() else sys.executable
GREEN, RED, YELLOW = "\033[32m", "\033[31m", "\033[33m"
RESET = "\033[0m"

results = []   # (状态, 名称, 证据行)


GATE_TIMEOUT = 3600   # 每条闸门的超时上限（秒）| per-gate timeout cap in seconds


def run(name, command, cwd=None, timeout=None):
    timeout = GATE_TIMEOUT if timeout is None else timeout
    start = time.time()
    try:
        proc = subprocess.run([str(c) for c in command], cwd=str(cwd or ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        results.append((RED, name, "超时（%d 秒）| timed out" % timeout))
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [l for l in out.splitlines() if l.strip()]
    tail = " | ".join(lines[-3:]) if lines else "(没有输出 | no output)"
    results.append((GREEN if proc.returncode == 0 else RED, name,
                    "exit %d（%.1f 秒）| %s" % (proc.returncode, time.time() - start, tail[:400])))
    return proc


def note(color, name, text):
    results.append((color, name, text))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", type=pathlib.Path, help="数据包 zip | the data package")
    ap.add_argument("--shaders", type=pathlib.Path, help="着色器包目录 | the shader package directory")
    ap.add_argument("--code", type=pathlib.Path, help="机器码目录 | the machine-code directory")
    ap.add_argument("--bfsha", type=pathlib.Path, help="着色器归档目录 | the shader archive directory")
    ap.add_argument("--index", type=pathlib.Path, help="着色器索引 TSV | the shader index TSV")
    ap.add_argument("--quick", action="store_true", help="跳过耗时的归档侧重算 | skip the slow archive recomputation")
    # 每条闸门的超时上限（秒）。变体键链要重解析 47,260 个着色器，本机实测 5~6 分钟；
    # 早先用 1800 秒时它被判超时（红），但同一命令单独跑是 exit 0 —— 那次是机器负载/休眠造成的，
    # 不是数据问题，所以把上限放宽到 3600 秒，别让执行环境冒充数据缺陷。
    # Per-gate timeout. The variant key chain reparses 47,260 shaders (5-6 min on this machine);
    # it once hit the old 1800 s cap and was reported red, while the very same command standalone
    # exits 0 -- that was machine load, not bad data, so the cap is now 3600 s.
    ap.add_argument("--gate-timeout", type=int, default=3600, help="每条闸门的超时秒数 | per-gate timeout in seconds")
    args = ap.parse_args()
    if args.gate_timeout <= 0:
        ap.error("--gate-timeout must be positive")
    global GATE_TIMEOUT
    GATE_TIMEOUT = args.gate_timeout

    # 1) APK
    apk = ROOT / "dm/android/build/D2R-Android-port.apk"
    if apk.is_file():
        note(GREEN, "APK", "%s（%d 字节，%s）| %d bytes" % (apk.name, apk.stat().st_size,
             time.strftime("%Y-%m-%d %H:%M", time.localtime(apk.stat().st_mtime)), apk.stat().st_size))
    else:
        note(RED, "APK", "缺 %s → 先跑 build.py --game-run | missing" % apk)

    # 2) 数据包清单
    if args.package:
        if args.package.is_file():
            proc = run("数据包清单 | package manifest", [PY, ROOT / "dm/android/tools/build_package.py", "inspect", args.package])
            if proc and proc.returncode == 0:
                try:
                    # inspect 的输出是「一段 JSON + 一行摘要」，用 raw_decode 只取第一段 JSON。
                    # The inspect output is a JSON block followed by a summary line; raw_decode takes just the JSON.
                    manifest, _ = json.JSONDecoder().raw_decode(proc.stdout[proc.stdout.index("{"):])
                    counts = manifest.get("counts", {})
                    note(GREEN, "数据包条目 | package entries", "%s（%s 字节）| %s" % (counts, manifest.get("bytes"), counts))
                except Exception as error:
                    note(YELLOW, "数据包条目 | package entries", "清单解析不了：%s | cannot parse: %s" % (error, error))
        else:
            note(RED, "数据包 | package", "找不到 %s | not found" % args.package)

    # 3) 着色器包
    if args.shaders:
        run("着色器包 | shader package", [PY, ROOT / "dm/gfx/tools/totk_shader_package.py", "--verify-shaders",
                                           args.shaders, "--tex-base", "0x20", "--tex-end", "0x120"])

    # 4) 变体键链（要归档与机器码，耗时；--quick 跳过）
    if args.index and args.code and args.shaders and not args.quick:
        command = [PY, ROOT / "dm/gfx/tools/totk_variant_keys.py", "--index", args.index, "--code", args.code,
                   "--shaders", args.shaders]
        if args.bfsha:
            command += ["--bfsha", args.bfsha]
        run("变体键链 | variant key chain", command)
    elif args.quick:
        note(YELLOW, "变体键链 | variant key chain", "跳过了（--quick）→ 真机前最好补跑 | skipped (--quick)")
    else:
        note(YELLOW, "变体键链 | variant key chain", "缺 --index/--code/--shaders → 没跑 | not run (missing arguments)")

    # 5) NVN 接口覆盖
    run("NVN 接口覆盖 | NVN coverage", [PY, ROOT / "dm/gfx/tools/nvn_coverage.py", "--check"])

    # 6) 闸门
    run("闸门 | ci_checks", [PY, ROOT / "dm/android/tools/ci_checks.py"])
    run("交接面 | handoff", [PY, ROOT / "tools/agent_handoff_check.py", "--verify"])

    # 7) 结论
    print("=" * 78)
    red = yellow = 0
    for color, name, evidence in results:
        if color == RED: red += 1
        elif color == YELLOW: yellow += 1
        tag = {GREEN: "绿", RED: "红", YELLOW: "黄"}[color]
        print("%s[%s]%s %-28s %s" % (color, tag, RESET, name, evidence))
    print("=" * 78)
    if red:
        print("%s结论：有 %d 项红 → 现在推机大概率会在红项处出问题，先修红项。%s" % (RED, red, RESET))
        return 1
    if yellow:
        print("%s结论：没有红项，有 %d 项黄 → 可以推机，但黄项要记在待确认清单里（真机上重点看）。%s" % (YELLOW, yellow, RESET))
        return 0
    print("%s结论：全绿 → 可以推机。%s" % (GREEN, RESET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
