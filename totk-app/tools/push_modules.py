#!/usr/bin/env python3
"""把三个模块推进新 App 的**内部**私有目录（R1 起要用）。

为什么绕一圈：Android 11+ 的外部存储（/sdcard/Android/data/<pkg>）被 FUSE 挡住，实测 App 里 fopen 直接 EACCES；
而 /data/data/<pkg> 只有本 App 和 run-as 能进。所以先 push 到 /data/local/tmp（全局可读），再用 run-as 拷进去。

Pushes the three modules into the new app's INTERNAL private dir (needed from R1 on).
Why the detour: on Android 11+ the external app dir under /sdcard/Android/data/<pkg> is blocked by FUSE and fopen
returns EACCES inside the app, while /data/data/<pkg> is reachable only by the app and by run-as. So push to
/data/local/tmp (world readable) first and then copy in with run-as.
"""
import os
import subprocess
import sys
from pathlib import Path

PKG = os.environ.get("TOTK_APP_PKG", "org.totk.android.port")
TOOLS = Path(os.environ.get("DM_ANDROID_TOOLS", r"D:\Switch\.tools\android"))
ADB = TOOLS / "platform-tools" / "adb.exe"
SRC = Path(os.environ.get("TOTK_MODULE_DIR", r"D:\Switch\totk-work\patched-android"))
MODULES = ("main", "sdk", "subsdk0")


def run(cmd, what, check=True):
    print(f"-- {what}", flush=True)
    r = subprocess.run([str(c) for c in cmd], capture_output=True)
    out = (r.stdout or b"").decode("utf-8", "replace").strip()
    if out:
        print("   " + out.replace("\n", "\n   "), flush=True)
    if check and r.returncode != 0:
        raise SystemExit(f"FAIL {what}: exit {r.returncode}")
    return out


def main():
    if not ADB.exists():
        raise SystemExit(f"缺少 adb：{ADB}")
    run([ADB, "shell", "run-as", PKG, "mkdir", "-p", "files/modules"], "建内部 modules 目录")
    for name in MODULES:
        src = SRC / f"{name}.patched.bin"
        if not src.exists():
            raise SystemExit(f"缺模块文件：{src}")
        run([ADB, "push", src, "/data/local/tmp/"], f"push {src.name}（{src.stat().st_size} 字节）")
        run([ADB, "shell", "run-as", PKG, "cp",
             f"/data/local/tmp/{src.name}", "files/modules/"], f"拷进内部目录 {src.name}")
    listing = run([ADB, "shell", "run-as", PKG, "ls", "-l", "files/modules"], "核对内部目录")
    for name in MODULES:
        if f"{name}.patched.bin" not in listing:
            raise SystemExit(f"内部目录里没有 {name}.patched.bin")
    print("OK：三个模块都已在 files/modules 里", flush=True)


if __name__ == "__main__":
    main()
