#!/usr/bin/env python3
"""把 TotK 的数据包推上一加 12，并设好游戏档位。

包的内部结构由启动界面的导入流程处理：`game/`（三个模块与布局表）落到**内部**存储 ——
外部存储是 noexec 挂载，dlopen 会失败；`romfs/` 与 `shaders/` 落到外部存储；
`manifest.json` 最后落盘，作为"这个包可用"的标记。所以本脚本只做两件事：
把 zip 推到外部存储，再把游戏档位写进 `launch-settings.conf`。

用法：
  deploy_totk.py --package <数据包.zip> [--profile totk] [--device <序列号>]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = "org.d2r.android.port"


def run(command, **kwargs):
    return subprocess.run([str(c) for c in command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", **kwargs)


def adb(args, device=None):
    command = ["adb"] + (["-s", device] if device else []) + [str(a) for a in args]
    result = run(command)
    if result.returncode != 0:
        raise SystemExit("adb %s failed: %s" % (" ".join(str(a) for a in args), result.stdout.strip()))
    return result.stdout


def shell(args, device=None):
    return adb(["shell"] + list(args), device)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", type=Path, required=True, help="数据包 zip | the data package")
    parser.add_argument("--profile", default="totk", help="游戏档位（d2r / totk）| the game profile")
    parser.add_argument("--device", help="adb 设备序列号 | the adb device serial")
    parser.add_argument("--external", help="外部存储目录（缺省用应用自己的）| the external files dir")
    parser.add_argument("--no-push", action="store_true", help="只写档位，不推包 | only set the profile")
    args = parser.parse_args()

    state = adb(["get-state"], args.device).strip()
    if "device" not in state.split():
        raise SystemExit("no device: " + state)

    external = args.external or ("/sdcard/Android/data/%s/files" % PACKAGE)
    internal = shell(["run-as", PACKAGE, "pwd"], args.device).strip().split("\n")[-1]
    shell(["mkdir", "-p", external], args.device)

    if not args.no_push:
        size = args.package.stat().st_size / 2**30
        print("推送数据包 %s（%.2f GiB，USB 上要一会儿）..." % (args.package.name, size), flush=True)
        adb(["push", str(args.package), external + "/"], args.device)
        print("已推到 %s" % external)

    # 游戏档位：native 读 launch-settings.conf 的 game_profile 来选 c[2] 的句柄表布局。
    # 启动界面重写这个文件时会保留不属于它自己的键，所以写一次就够。
    settings = shell(["run-as", PACKAGE, "cat", "files/temp/launch-settings.conf"], args.device).strip()
    kept = [line for line in settings.splitlines()
            if line.strip() and line.split("=", 1)[0].strip() != "game_profile"]
    kept.append("game_profile=" + args.profile)
    body = "\n".join(kept) + "\n"
    local = args.package.parent / "launch-settings.conf"
    local.write_text(body, encoding="utf-8")
    adb(["push", str(local), "/data/local/tmp/launch-settings.conf"], args.device)
    shell(["run-as", PACKAGE, "cp", "/data/local/tmp/launch-settings.conf", "files/temp/launch-settings.conf"], args.device)
    shell(["rm", "-f", "/data/local/tmp/launch-settings.conf"], args.device)
    print("游戏档位已设为 %s（%s）" % (args.profile, internal))
    print("下一步：在启动界面「导入数据包」里选 %s，然后「游戏」那一行选到 %s，再启动游戏。"
          % (args.package.name, args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
