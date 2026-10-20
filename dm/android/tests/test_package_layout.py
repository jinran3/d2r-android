#!/usr/bin/env python3
"""数据包里的 RomFS 布局闸门：D2R 走 data/（平铺归档），TotK 走整棵树（保留相对路径）。

D2R 的 RomFS 里游戏只按 `data/<名字>` 开文件，所以包里的 romfs/ 下是平铺的归档；
TotK 的 RomFS 本身是一棵深目录树（Shader/、Pack/、…），包里的路径必须和游戏要开的路径一致，
否则游戏读到的每个文件都是"不存在"。这条测试用两棵合成目录各打一个包，核对包内条目。

用法：python3 dm/android/tests/test_package_layout.py
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILDER = ROOT / "dm/android/tools/build_package.py"
MODULES = ("libdmguest_main.so", "libdmguest_sdk.so", "libdmguest_subsdk0.so")
LAYOUTS = tuple("%s.%s.tsv" % (module, kind) for module in ("main", "sdk", "subsdk0") for kind in ("fixups", "gates"))


def main():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        totk = work / "totk-romfs"
        (totk / "Shader" / "sub").mkdir(parents=True)
        (totk / "Pack").mkdir()
        (totk / "Shader" / "a.bfsha.zs").write_bytes(b"a" * 10)
        (totk / "Shader" / "sub" / "b.bfsha.zs").write_bytes(b"b" * 20)
        (totk / "Pack" / "c.pack.zs").write_bytes(b"c" * 30)
        d2r = work / "d2r-romfs"
        (d2r / "data").mkdir(parents=True)
        (d2r / "data" / "00-00000001.data").write_bytes(b"x" * 10)
        game = work / "game"
        game.mkdir()
        for name in MODULES:
            (game / name).write_bytes(b"m" * 5)
        for name in LAYOUTS:
            (game / name).write_text("x\n", encoding="utf-8")
        shaders = work / "shaders"
        shaders.mkdir()
        (shaders / "host-subgroup-size.txt").write_text("64\n", encoding="utf-8")
        (shaders / "aa.spv").write_bytes(b"s" * 4)
        (shaders / "aa.meta").write_bytes(b"m" * 4)
        for layout, source, expected in (
                ("root", totk, ("romfs/Shader/a.bfsha.zs", "romfs/Shader/sub/b.bfsha.zs", "romfs/Pack/c.pack.zs")),
                ("data", d2r, ("romfs/data/00-00000001.data",))):
            output = work / ("package-%s.zip" % layout)
            result = subprocess.run([sys.executable, str(BUILDER), "assemble", str(output), "--game", str(game),
                                     "--romfs", str(source), "--shaders", str(shaders), "--romfs-layout", layout],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                print("%s layout: package failed: %s %s" % (layout, result.stdout, result.stderr))
                return 1
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            missing = [name for name in expected if name not in names]
            if missing:
                print("%s layout: missing %s" % (layout, missing))
                return 1
            for name in MODULES + LAYOUTS:
                if ("game/" + name) not in names:
                    print("%s layout: missing game/%s" % (layout, name))
                    return 1
            if "shaders/host-subgroup-size.txt" not in names:
                print("%s layout: missing the subgroup profile" % layout)
                return 1
    print("package layout: D2R data/ and TotK root tree both pack with the paths the game opens PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
