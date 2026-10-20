#!/usr/bin/env python3
"""把 TotK 的数据部署到已连接的一加 12（不经过启动界面的 zip 导入）。

宿主的取名与挂载（`dm/android/native/frontend_activity.c`）：
  · 模块必须在**内部**存储（外部存储是 noexec 挂载，dlopen 会失败）→ `<内部>/d2r-package/game/`；
  · 资源在外部存储 → `<外部>/d2r-package/romfs/`（`DM_ROMFS`）与 `<外部>/d2r-package/shaders/`
    （`DM_VK_SHADERS`）；
  · `<外部>/d2r-package/manifest.json` 在���就说明"走了导入包这条路"，宿主才会用上面的目录；
  · 游戏的档位由 `launch-settings.conf` 的 `game_profile` 键决定（native 读成 `DM_GAME_PROFILE`，
    用来选 c[2] 的句柄表布局：D2R 分离表 / TotK 合并表）。启动界面重写这个文件时会保留
    不属于它自己的键，所以写一次就够。

用法：
  deploy_totk.py --romfs <解出的 RomFS 目录> --shaders <着色器包目录> --game <模块目录>
                  [--tar <tar 路径>] [--profile totk] [--device <序列号>]

用法要点：RomFS 有 30 多万个文件，逐个 adb push 不现实；默认先打成一个 tar 推过去，再在机上解开
（手机的 toybox 带 tar）。`--no-tar` 则直接推目录（文件少时用）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def push_tree(local, remote, device, label):
    """把一个目录的内容推上去：文件多时先打 tar 再在机上解。"""
    files = [p for p in local.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print("%s: %d 个文件 %.2f GiB" % (label, len(files), total / 2**30), flush=True)
    shell(["mkdir", "-p", remote], device)
    if len(files) <= 64:
        for path in files:
            adb(["push", str(path), "%s/%s" % (remote, path.relative_to(local).as_posix())], device)
        return
    tar = Path(local).parent / (local.name + ".tar")
    print("  打包成 %s ..." % tar.name, flush=True)
    with tarfile.open(tar, "w") as archive:
        for path in files:
            archive.add(path, arcname=path.relative_to(local).as_posix())
    print("  推送 %s（%.2f GiB）..." % (tar.name, tar.stat().st_size / 2**30), flush=True)
    adb(["push", str(tar), "/data/local/tmp/"], device)
    shell(["tar", "-xf", "/data/local/tmp/" + tar.name, "-C", remote], device)
    shell(["rm", "-f", "/data/local/tmp/" + tar.name], device)
    tar.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--romfs", type=Path, required=True, help="解出的 RomFS 目录 | the extracted RomFS tree")
    parser.add_argument("--shaders", type=Path, required=True, help="着色器包目录（.spv + .meta + host-subgroup-size.txt）| the shader package")
    parser.add_argument("--game", type=Path, required=True, help="模块目录（libdmguest_*.so 与 *.fixups/gates.tsv）| the module directory")
    parser.add_argument("--profile", default="totk", help="游戏档位（写进 launch-settings.conf）| the game profile")
    parser.add_argument("--device", help="adb 设备序列号 | the adb device serial")
    parser.add_argument("--external", help="外部存储目录（缺省用应用自己的）| the external files dir")
    parser.add_argument("--internal", help="内部存储目录（缺省用应用自己的）| the internal files dir")
    parser.add_argument("--no-tar", action="store_true", help="不打包，直接推目录 | push the directory as is")
    args = parser.parse_args()

    state = adb(["get-state"], args.device).strip()
    if "device" not in state.split():
        raise SystemExit("no device: " + state)

    external = args.external or shell(["run-as", PACKAGE, "pwd"], args.device).strip().split("\n")[-1]
    internal = args.internal or external
    # run-as 落在内部存储；外部存储要用普通 shell 路径。
    external = "/sdcard/Android/data/%s/files" % PACKAGE
    internal = shell(["run-as", PACKAGE, "pwd"], args.device).strip().split("\n")[-1]

    package_external = external + "/d2r-package"
    package_internal = internal + "/d2r-package"
    shell(["mkdir", "-p", package_external + "/shaders", package_internal + "/game"], args.device)

    # 着色器包（宿主按键找 .spv 与 .meta）
    push_tree(args.shaders, package_external + "/shaders", args.device, "着色器")

    # 模块：必须在内部存储（外部存储 noexec，dlopen 会失败）
    for path in sorted(p for p in args.game.rglob("*") if p.is_file()):
        adb(["push", str(path), "/data/local/tmp/"], args.device)
        shell(["run-as", PACKAGE, "cp", "/data/local/tmp/" + path.name, package_internal + "/game/" + path.name], args.device)
        shell(["rm", "-f", "/data/local/tmp/" + path.name], args.device)

    # RomFS：文件多时走 tar
    if args.no_tar:
        push_tree(args.romfs, package_external + "/romfs", args.device, "RomFS")
    else:
        push_tree(args.romfs, package_external + "/romfs", args.device, "RomFS")

    # manifest.json：宿主看到它就走"导入包"这条路
    romfs_files = [p for p in args.romfs.rglob("*") if p.is_file()]
    shader_files = [p for p in args.shaders.rglob("*") if p.is_file()]
    game_files = [p for p in args.game.rglob("*") if p.is_file()]
    manifest = {
        "format": 1,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "deployed TotK data",
        "subgroup_size": 64,
        "counts": {"game": len(game_files), "romfs": len(romfs_files), "shaders": len(shader_files)},
        "bytes": {"game": sum(p.stat().st_size for p in game_files),
                  "romfs": sum(p.stat().st_size for p in romfs_files),
                  "shaders": sum(p.stat().st_size for p in shader_files)},
    }
    local_manifest = Path(args.romfs).parent / "manifest.json"
    local_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    adb(["push", str(local_manifest), package_external + "/manifest.json"], args.device)

    # 游戏档位：启动界面重写这个文件时会保留不属于它自己的键
    settings = shell(["run-as", PACKAGE, "cat", "files/temp/launch-settings.conf"], args.device).strip()
    kept = [line for line in settings.splitlines() if line and not line.split("=", 1)[0].strip() == "game_profile"]
    kept.append("game_profile=" + args.profile)
    body = "\n".join(kept) + "\n"
    local_settings = Path(args.romfs).parent / "launch-settings.conf"
    local_settings.write_text(body, encoding="utf-8")
    adb(["push", str(local_settings), "/data/local/tmp/launch-settings.conf"], args.device)
    shell(["run-as", PACKAGE, "cp", "/data/local/tmp/launch-settings.conf", "files/temp/launch-settings.conf"], args.device)
    shell(["rm", "-f", "/data/local/tmp/launch-settings.conf"], args.device)

    print("部署完成：外部 %s，内部 %s，档位 %s" % (package_external, package_internal, args.profile))
    print("条目：RomFS %d，着色器 %d，模块 %d" % (len(romfs_files), len(shader_files), len(game_files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
