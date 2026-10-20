#!/usr/bin/env python3
"""客体的导入符号是否都能落地：宿主 HLE 表 ∪ 其它模块的导出。

真机开机的第一道门就是这个 —— 少一个符号，游戏连 `nnMain` 都走不到。
判定口径与宿主装载器一致（dm/android/native/game_modules.c）：先查宿主登记的 HLE 名字，
再查其它模块的导出；两处都没有的才算「无人提供」。

用法：check_guest_imports.py --modules <NSO 目录> [--names main sdk subsdk0]
      [--inventory <HLE 清单.tsv>]
产物：只读核对，不写任何文件；无人提供的符号会逐个列出并以非零码退出。
"""
import argparse
import collections
import csv
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nso_stats as N


def module_symbols(path):
    """一个 NSO 模块的 (导入, 导出) 符号名集合。 | The (imports, exports) of one NSO module."""
    flat, _segments, _build = N.load_nso(path)
    table, _mod0 = N.dynamic(flat)
    symtab = table[N.DT_SYMTAB]
    strtab = table[N.DT_STRTAB]
    if N.DT_HASH in table:
        count = struct.unpack_from("<I", flat, table[N.DT_HASH] + 4)[0]
    else:
        count = N.gnu_hash_symbols(flat, table[N.DT_GNU_HASH])
    imports, exports = set(), set()
    for index in range(count):
        offset = symtab + index * 24
        if offset + 24 > len(flat):
            break
        st_name, _info, _other, st_shndx = struct.unpack_from("<IBBH", flat, offset)
        if not st_name:
            continue
        raw = flat[strtab + st_name:]
        name = raw[:raw.index(b"\0")].decode("utf-8", "replace")
        (imports if st_shndx == 0 else exports).add(name)
    return imports, exports


def host_names(path):
    if not path or not Path(path).is_file():
        return set()
    with open(path, encoding="utf-8") as f:
        return {row["改编名"] for row in csv.DictReader(f, delimiter="\t")}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modules", type=Path, required=True, help="放着 NSO 的目录 | the directory holding the NSO files")
    parser.add_argument("--names", nargs="*", default=["main", "sdk", "subsdk0"])
    parser.add_argument("--inventory", type=Path, help="HLE 清单 TSV（默认用仓库自带的）| the HLE inventory TSV")
    parser.add_argument("--allow-prefix", nargs="*", default=["glslc"],
                        help="允许无人提供的前缀（默认 glslc：NVIDIA 的运行时 GLSL 编译器，着色器已离线预译，游戏不会调）"
                             " | prefixes allowed to have no provider (glslc by default: NVIDIA's runtime GLSL compiler, unused because the shaders are pre-translated)")
    args = parser.parse_args()
    inventory = args.inventory or Path(__file__).resolve().parents[2] / "handoff-hle-inventory.tsv"
    host = host_names(inventory)
    modules = {}
    for name in args.names:
        path = args.modules / name
        if not path.is_file():
            print("%-8s 缺少 %s，跳过" % (name, path))
            continue
        modules[name] = module_symbols(path)
        print("%-8s 导入 %d，导出 %d" % (name, len(modules[name][0]), len(modules[name][1])))
    exports = set()
    for _name, (_imports, provided) in modules.items():
        exports |= provided
    missing = collections.Counter()
    total = from_host = from_module = 0
    for _name, (imports, _provided) in modules.items():
        for symbol in imports:
            total += 1
            if symbol in host:
                from_host += 1
            elif symbol in exports:
                from_module += 1
            elif not any(symbol.startswith(prefix) for prefix in args.allow_prefix):
                missing[symbol] += 1
    print("导入共 %d 个：宿主 HLE 提供 %d，其它模块提供 %d，无人提供 %d"
          % (total, from_host, from_module, sum(missing.values())))
    if missing:
        for symbol, count in missing.most_common(60):
            print("   %-62s %d" % (symbol, count))
        return 1
    print("全部导入都有提供者（%s 除外，本就不该被调用）✓" % (", ".join(args.allow_prefix) or "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
