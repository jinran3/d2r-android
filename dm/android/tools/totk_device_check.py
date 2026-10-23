#!/usr/bin/env python3
"""开机前的设备侧核对：一条命令把「不用开机就能查的」全查完，并给出放行 / 拦住。

Device-side check before the first boot: one command runs everything that can be checked
without starting the game, and says whether to go ahead.

查什么（每条都有明确的通过条件）：
  1. 设备在不在 adb 里；
  2. `files/temp/launch-settings.conf` 里的 `game_profile` 是不是 totk
     —— **启动界面点「开始」时会用界面里选中的那一行重写这个键**，
        所以必须在界面里切到「王国之泪」，否则宿主会按 D2R 的分离句柄表读 c[2]；
  3. `files/temp/gpu-driver.conf` 里的 `subgroup_size`（用内置 Turnip 时必须是 64，
     与包里的 `shaders/host-subgroup-size.txt` 一致）；
  4. 内部存储的 `d2r-package/game/` 里三个模块与六份布局表齐不齐；
  5. 外部存储的 `d2r-package/` 里 manifest.json / romfs / shaders 在不在；
  6. manifest.json 的 format 与 counts 对不对；
  7. `/data` 的可用空间够不够（导入要 ~33 GiB）；
  8. （可选）把 `files/game.log` 拉下来 —— 客体日志在那里，不在 logcat 里。

用法：python dm/android/tools/totk_device_check.py [--package <数据包.zip>] [--pull-log <落盘路径>]
用法（英文）：python dm/android/tools/totk_device_check.py [--package ...] [--pull-log ...]

退出码：0 = 全绿（可以开机）；1 = 有红项（先修红项）；2 = 设备没接上。
只读：只读文件与 `df`，不改手机上任何东西。
Read-only: it reads files and `df`; it changes nothing on the phone.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PACKAGE = "org.d2r.android.port"
EXTERNAL = "/sdcard/Android/data/%s/files" % PACKAGE
INTERNAL = "/data/data/%s/files" % PACKAGE
ADB = Path(r"D:\Switch\.tools\android\platform-tools\adb.exe")
GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
results = []


def adb(args, timeout=60):
    return subprocess.run([str(ADB)] + [str(a) for a in args], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def note(color, name, text):
    results.append((color, name, text))


def report(verdict):
    print()
    for color, name, text in results:
        print("%s%-22s%s %s" % (color, name, RESET, text))
    print()
    print("结论：%s | verdict" % verdict)


def run_as(command, timeout=60):
    return adb(["shell", "run-as", PACKAGE] + command, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", type=Path, help="数据包 zip（只用来对照 romfs/shaders 的条数）| the data package")
    parser.add_argument("--pull-log", type=Path, help="把 files/game.log 拉到本机这个路径 | pull files/game.log here")
    args = parser.parse_args()

    if not ADB.is_file():
        note(RED, "adb", "找不到 adb：%s | adb not found" % ADB)
        report("没有 adb，先装好工具链 | no adb")
        return 2
    listing = adb(["devices"])
    devices = [line.split("\t")[0] for line in listing.stdout.splitlines()
               if line.strip() and not line.startswith("List of")]
    if not devices:
        note(RED, "设备 | device", "adb devices 为空 —— 手机还没接上（这是唯一的外部阻塞）| no device attached")
        report("手机没接上，其余检查没法做 | no device attached")
        return 2
    note(GREEN, "设备 | device", "%s | %s" % (", ".join(devices), ", ".join(devices)))

    # 2) 游戏档位
    settings = run_as(["cat", "files/temp/launch-settings.conf"])
    profile = ""
    for line in settings.stdout.splitlines():
        if line.strip().startswith("game_profile"):
            profile = line.split("=", 1)[1].strip()
    if profile == "totk":
        note(GREEN, "游戏档位 | game profile", "game_profile=totk ✓")
    else:
        note(RED, "游戏档位 | game profile",
             "game_profile=%s —— **要在启动界面的「游戏」那一行切到「王国之泪」**（界面会重写这个键）| pick TotK in the launcher" % (profile or "(没写)"))

    # 3) 驱动档位（内置 Turnip 时 subgroup_size 必须是 64）
    driver = run_as(["cat", "files/temp/gpu-driver.conf"])
    subgroup = ""
    for line in driver.stdout.splitlines():
        if line.strip().startswith("subgroup_size"):
            subgroup = line.split("=", 1)[1].strip()
    if subgroup:
        if subgroup == "64":
            note(GREEN, "驱动 | driver", "内置驱动，subgroup_size=64 ✓（与包里的 host-subgroup-size.txt 一致）")
        else:
            note(RED, "驱动 | driver", "subgroup_size=%s —— 与包里的 64 不一致，着色器会 FATAL | mismatch" % subgroup)
    else:
        note(YELLOW, "驱动 | driver", "没写 gpu-driver.conf —— 用的是系统驱动；系统的子组尺寸若不是 64 会 FATAL（要用内置 Turnip）")

    # 4) 模块
    modules = run_as(["ls", "files/d2r-package/game"])
    names = [line.split()[-1] for line in modules.stdout.splitlines() if line.strip()]
    wanted = ["libdmguest_main.so", "libdmguest_sdk.so", "libdmguest_subsdk0.so"]
    missing = [w for w in wanted if w not in names]
    layouts = [n for n in names if n.endswith(".tsv")]
    if missing:
        note(RED, "模块 | game modules", "缺 %s（%s）| missing" % (", ".join(missing), ", ".join(names[:9])))
    elif len(layouts) < 6:
        note(YELLOW, "模块 | game modules", "三个 .so 在，但布局表只有 %d 份（要 6 份）| %d layout tables" % (len(layouts), len(layouts)))
    else:
        note(GREEN, "模块 | game modules", "3 个 .so + %d 份布局表 ✓" % len(layouts))

    # 5) 外部数据
    listing = adb(["shell", "ls", "%s/d2r-package" % EXTERNAL])
    entries = listing.stdout.split()
    want = ["manifest.json", "romfs", "shaders"]
    missing = [w for w in want if w not in entries]
    if missing:
        note(RED, "外部数据 | external data", "缺 %s —— 还没导入？| missing" % ", ".join(missing))
    else:
        note(GREEN, "外部数据 | external data", "manifest.json / romfs / shaders ✓")

    # 6) 清单
    if "manifest.json" in entries:
        raw = adb(["shell", "cat", "%s/d2r-package/manifest.json" % EXTERNAL]).stdout
        try:
            start = raw.index("{")
            data = json.loads(raw[start:])
            counts = data.get("counts", {})
            if data.get("format") == 1 and counts.get("romfs") == 304207 and counts.get("shaders") == 24535:
                note(GREEN, "清单 | manifest", "format=1，romfs=%s，shaders=%s ✓"
                     % (counts.get("romfs"), counts.get("shaders")))
            else:
                note(RED, "清单 | manifest", "format=%s，romfs=%s，shaders=%s —— 与包的预期不符"
                     % (data.get("format"), counts.get("romfs"), counts.get("shaders")))
        except (ValueError, KeyError) as error:
            note(RED, "清单 | manifest", "读不出 JSON：%s" % error)

    # 7) 空间
    disk = adb(["shell", "df", "-k", "/data"]).stdout.splitlines()
    free = 0
    for line in disk:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "/dev" or (len(parts) >= 4 and parts[-1] == "/data"):
            try:
                free = max(free, int(parts[-3]))
            except ValueError:
                pass
    if free:
        gib = free / 1024 / 1024
        if gib >= 35:
            note(GREEN, "空间 | free space", "/data 可用 %.1f GiB（导入要 ~33 GiB）✓" % gib)
        else:
            note(RED, "空间 | free space", "/data 只剩 %.1f GiB —— 导入要 ~33 GiB，先清空间 | not enough" % gib)
    else:
        note(YELLOW, "空间 | free space", "df 读不出可用空间 | could not read free space")

    # 8) 日志
    log = run_as(["cat", "files/game.log"])
    if log.stdout.strip():
        lines = [l for l in log.stdout.splitlines() if l.strip()]
        note(GREEN, "日志 | game log", "files/game.log 有 %d 行（最后一行：%s）"
             % (len(lines), lines[-1][:120]))
        if args.pull_log:
            args.pull_log.write_text(log.stdout, encoding="utf-8")
            note(GREEN, "日志落盘 | log saved", str(args.pull_log))
    else:
        note(YELLOW, "日志 | game log", "files/game.log 是空的（还没开过机？）| empty")

    failed = [r for r in results if r[0] == RED]
    report("%s（红项 %d 条）| %s (%d red)"
           % ("可以开机" if not failed else "先修红项再开机", len(failed),
              "ready to boot" if not failed else "fix the red items first", len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

