#!/usr/bin/env python3
"""TotK 模块流水线：改写 → 打成 ELF 库 → 宿主同款解析核对。

M1 的第一步（不碰图形）：把 TotK 的三个模块（main / sdk / subsdk0）用
`DM_RULESET=totk-run-v1 DM_TARGET=android` 改写（补丁器按真实构建号取表、CUTS/OBS 为空），
再用 `guest_elf.py` 打成宿主能装载的 `libdmguest_*.so`，最后照
`dm/android/native/game_modules.c` 的 `parse()` 在本机复刻一遍宿主的解析，确认
「模块能被宿主读出」，并列出跨模块未解析的导入符号（宿主对它们有未实现桩兜底，
真机上用 DM_HLECOUNT 看有没有被调用过）。

游戏文件与密钥只在本机读，产物落在仓库外；本工具不打印也不复制任何密钥。

TotK module pipeline: rewrite → pack into ELF libraries → verify with the host's own parser.
M1's first step (no graphics): rewrite TotK's three modules (main / sdk / subsdk0) with
DM_RULESET=totk-run-v1 DM_TARGET=android (the patcher keys the tables by the real build ids and
the CUTS/OBS tables are empty), pack them with guest_elf.py into libdmguest_*.so, then replicate
the host's parse() (dm/android/native/game_modules.c) locally to confirm the host can read them,
and list the cross-module unresolved imports (the host has unimplemented stubs for them; DM_HLECOUNT
on a device shows whether they are ever called).

Game files and keys are only read on this machine and the outputs stay outside the repository;
this tool never prints or copies key material.
"""
import argparse
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REWRITER = ROOT / "tools" / "patch_nso.py"
PACKER = HERE / "guest_elf.py"
MODULES = ("main", "sdk", "subsdk0")


def run(command, **kwargs):
    print("+", " ".join(str(c) for c in command), flush=True)
    subprocess.run([str(c) for c in command], check=True, **kwargs)


def elf_sections(raw):
    """节表（含名字）。 | Section headers with names."""
    shoff = struct.unpack_from("<Q", raw, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", raw, 58)
    table = []
    for index in range(shnum):
        base = shoff + index * shentsize
        name, stype, flags, addr, offset, size = struct.unpack_from("<IIQQQQ", raw, base)
        table.append((name, stype, offset, size))
    stroff = table[shstrndx][2]
    out = {}
    for name, stype, offset, size in table:
        end = raw.index(b"\0", stroff + name)
        out[raw[stroff + name:end].decode()] = (offset, size)
    return out


def host_parse(image):
    """照 dm/android/native/game_modules.c 的 parse() 复刻。 | Replicate the host's parse()."""
    if len(image) < 8:
        raise SystemExit("客体映像太小")
    mod0 = struct.unpack_from("<I", image, 4)[0]
    if image[mod0:mod0 + 4] != b"MOD0":
        raise SystemExit("映像里没有 MOD0 头")
    dynamic = mod0 + struct.unpack_from("<i", image, mod0 + 4)[0]
    sym = strt = rela = jmprel = 0
    relasz = jmprel_size = strsz = 0
    ended = False
    for index in range(4096):
        offset = dynamic + index * 16
        if offset + 16 > len(image):
            raise SystemExit("动态表越界")
        tag, value = struct.unpack_from("<qQ", image, offset)
        if tag == 0:
            ended = True
            break
        if tag == 6: sym = value
        elif tag == 5: strt = value
        elif tag == 10: strsz = value
        elif tag == 8: relasz = value
        elif tag == 7: rela = value
        elif tag == 23: jmprel = value
        elif tag == 2: jmprel_size = value
    if not ended or not sym or strt < sym or (strt - sym) % 24 or relasz % 24 or jmprel_size % 24:
        raise SystemExit("动态元数据不合法")
    count = (strt - sym) // 24
    defined, undefined = set(), []
    for index in range(count):
        st_name, _info, _other, shndx, _value, _size = struct.unpack_from("<IBBHQQ", image, sym + index * 24)
        end = image.index(b"\0", strt + st_name)
        name = image[strt + st_name:end].decode("utf-8", "replace")
        if shndx:
            defined.add(name)
        else:
            undefined.append(name)
    return {
        "symbols": count,
        "rela": relasz // 24,
        "jmprel": jmprel_size // 24,
        "imports": len(undefined),
        "defined": defined,
        "undefined": undefined,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exefs", type=Path, required=True, help="TotK 的 ExeFS 目录（里面有 main / sdk / subsdk0 / rtld） | the TotK ExeFS directory")
    parser.add_argument("--work", type=Path, required=True, help="工作目录（改写产物与 ELF 库，仓库外） | the work directory (rewritten images and ELF libraries, outside the repository)")
    parser.add_argument("--patched", type=Path, default=None, help="改写产物目录（缺省 <work>/patched） | directory of the rewritten images (default <work>/patched)")
    parser.add_argument("--libraries", type=Path, default=None, help="ELF 库目录（缺省 <work>/guest-so） | directory of the ELF libraries (default <work>/guest-so)")
    parser.add_argument("--reuse", action="store_true", help="已有改写产物就跳过改写 | skip rewriting when the outputs already exist")
    args = parser.parse_args()

    work = args.work
    patched = args.patched or (work / "patched")
    libraries = args.libraries or (work / "guest-so")
    patched.mkdir(parents=True, exist_ok=True)
    libraries.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, DM_RULESET="totk-run-v1", DM_TARGET="android")
    for module in ("main", "sdk", "subsdk0", "rtld"):
        source = args.exefs / module
        if not source.is_file():
            print("缺少模块文件：%s" % source)
            continue
        if args.reuse and (patched / (module + ".patched.bin")).is_file():
            print("跳过改写（复用）：%s" % module)
            continue
        run([sys.executable, REWRITER, source, patched, module], env=environment)
    run([sys.executable, PACKER, patched, libraries, *MODULES], env=environment)

    total = {"symbols": 0, "rela": 0, "jmprel": 0, "imports": 0}
    defined = set()
    undefined = {}
    for module in MODULES:
        path = libraries / ("libdmguest_%s.so" % module)
        if not path.is_file():
            print("缺模块库：%s" % path)
            continue
        raw = path.read_bytes()
        sections = elf_sections(raw)
        offset, size = sections[".image"]
        info = host_parse(raw[offset:offset + size])
        defined |= info["defined"]
        for name in info["undefined"]:
            undefined.setdefault(name, []).append(module)
        total["symbols"] += info["symbols"]
        total["rela"] += info["rela"]
        total["jmprel"] += info["jmprel"]
        total["imports"] += info["imports"]
        print("%-8s 符号 %-6d 重定位 %-6d（RELA %d + PLT %d）导入 %d" %
              (module, info["symbols"], info["rela"] + info["jmprel"], info["rela"], info["jmprel"], info["imports"]))
    missing = sorted(name for name in undefined if name not in defined)
    print("== 合计：符号 %d，重定位 %d，导入 %d" % (total["symbols"], total["rela"] + total["jmprel"], total["imports"]))
    print("== 跨模块未解析的导入 %d 个（宿主对它们有未实现桩兜底）:" % len(missing))
    for name in missing:
        print("   %-40s 来自 %s" % (name, ",".join(undefined[name])))


if __name__ == "__main__":
    main()
