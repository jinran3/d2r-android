#!/usr/bin/env python3
"""在真机上实测 Vulkan：编译探针、推送、执行、打印报告。

计划 §4.5 的「驱动选型」要靠这个说话：仓库内置的 Turnip 是 T30/Adreno 830 构建，
而一加 12 是 Adreno 750；与其猜，不如在机器上把加载器、ICD、物理设备、驱动版本、
子组大小与设备扩展逐条读出来。探针只读 Vulkan 的公开接口，不碰游戏。

用法：run_vulkan_probe.py [--device <序列号>] [--keep]
输出：设备上的 Vulkan 报告（stdout）。

Measure Vulkan on the device: build the probe, push it, run it and print the report.
Plan §4.5's driver choice has to be settled by measurement: the bundled Turnip is a
T30/Adreno 830 build while the OnePlus 12 is an Adreno 750, so read the loader, the
ICD, the physical device, the driver version, the subgroup size and the device
extensions off the machine instead of guessing. The probe only uses public Vulkan
interfaces and never touches the game.

Usage: run_vulkan_probe.py [--device <serial>] [--keep]
Output: the Vulkan report from the device (stdout).
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from host_env import HOST_TAG, tool   # Windows: give the NDK wrapper its real suffix

TOOLS = Path(os.environ.get("DM_ANDROID_TOOLS", str(Path.home() / "dm-work/tools/android")))
NDK = TOOLS / "ndk/toolchains/llvm/prebuilt" / HOST_TAG / "bin"
CLANG = tool(NDK / "aarch64-linux-android29-clang")
REMOTE = "/data/local/tmp/dm_vulkan_probe"


def run(command, **kwargs):
    return subprocess.run([str(c) for c in command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", help="adb device serial | adb device serial")
    parser.add_argument("--keep", action="store_true", help="keep the binary on the device | keep the binary on the device")
    args = parser.parse_args()
    # adb 版本要和已连上的设备匹配：优先用 PATH 里的 adb（用户平时用的那个），
    # 没有再用工具目录里的。
    # The adb version must match the connected device: prefer the adb on PATH (the one the user
    # normally uses) and fall back to the one in the tools directory.
    adb = os.environ.get("ADB") or "adb"
    if not (shutil.which(adb) if os.path.sep not in adb else Path(adb).is_file()):
        adb = tool(TOOLS / "platform-tools/adb")
    target = ["-s", args.device] if args.device else []
    devices = run([adb, *target, "get-state"])
    state = (devices.stdout or "")
    # adb 重启旧版守护进程时会把提示打到同一段输出里，所以看"有没有 device"而不是整段相等。
    # adb prints its server-restart notices into the same stream, so look for the state instead of
    # comparing the whole output.
    if devices.returncode != 0 or "device" not in state.split():
        sys.exit("no device: " + state.strip())
    build = ROOT / "build/vulkan-probe"
    build.mkdir(parents=True, exist_ok=True)
    binary = build / "vulkan_probe"
    result = run([CLANG, "-O2", "-o", binary, ROOT / "tools/vulkan_probe.c", "-lvulkan"])
    if result.returncode != 0:
        sys.exit("probe build failed:\n" + result.stdout)
    result = run([adb, *target, "push", binary, REMOTE])
    if result.returncode != 0:
        sys.exit("probe push failed:\n" + result.stdout)
    run([adb, *target, "shell", "chmod", "755", REMOTE])
    result = run([adb, *target, "shell", REMOTE])
    print(result.stdout.rstrip())
    if not args.keep:
        run([adb, *target, "shell", "rm", "-f", REMOTE])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
