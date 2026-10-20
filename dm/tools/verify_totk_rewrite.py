#!/usr/bin/env python3
"""核对 TotK 模块的改写是不是「只改了该改的地方」。

规则域 totk-run-v1 **不做 x18 改写**（TotK 把 x18 当普通寄存器用），这条决定此前没有实测过
——万一改写器顺手动了 x18 相关的指令，游戏里就会出说不清的怪问题。这个脚本给出硬证据：

  · 把原始 NSO 的 .text 与改写后的映像逐字节比，列出所有差异区间；
  · 与 <名>.sites.tsv 里登记的改写点对照，确认**每一处差异都在改写点上**（没有旁改）；
  · 反汇编每个改写点，确认**没有一个改写点涉及 x18 / w18**。

用法：verify_totk_rewrite.py --exefs <解出的 ExeFS 目录> --patched <改写产物目录>
                      [--modules main sdk subsdk0]
产物：只读核对，不写任何文件。
"""
import argparse
import os
import struct
from pathlib import Path

import lz4.block
from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs


def text_section(nso: Path):
    """从 NSO 里取出 .text（解压后的原始字节）。 | The original .text out of an NSO."""
    data = nso.read_bytes()
    flags = struct.unpack_from("<I", data, 0xC)[0]
    segments = [struct.unpack_from("<III", data, 0x10 + index * 0x10) for index in range(3)]
    compressed = struct.unpack_from("<III", data, 0x60)
    file_offset, memory_offset, size = segments[0]
    raw = data[file_offset:file_offset + compressed[0]]
    if flags & 1:
        raw = lz4.block.decompress(raw, uncompressed_size=size)
    return raw, memory_offset, size


def sites(path: Path):
    out = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        offset, kind = line.split("\t")
        out.append((int(offset, 16), kind))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exefs", type=Path, required=True, help="解出的 ExeFS 目录 | the extracted ExeFS directory")
    parser.add_argument("--patched", type=Path, required=True, help="改写产物目录（<名>.patched.bin / <名>.sites.tsv）| the rewrite output directory")
    parser.add_argument("--modules", nargs="*", default=["main", "sdk", "subsdk0"])
    args = parser.parse_args()
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    decoder.detail = True
    failures = []
    for name in args.modules:
        nso = args.exefs / name
        patched = args.patched / (name + ".patched.bin")
        if not nso.is_file() or not patched.is_file():
            print("%-8s 缺少原始或改写产物，跳过" % name)
            continue
        original, memory_offset, size = text_section(nso)
        image = patched.read_bytes()
        rewritten = image[memory_offset:memory_offset + size]
        limit = min(len(original), len(rewritten))
        differences = [i for i in range(limit) if original[i] != rewritten[i]]
        ranges = []
        for offset in differences:
            if ranges and offset <= ranges[-1][1] + 4:
                ranges[-1][1] = offset
            else:
                ranges.append([offset, offset])
        marks = sites(args.patched / (name + ".sites.tsv"))
        kinds = {}
        for offset, kind in marks:
            kinds[kind] = kinds.get(kind, 0) + 1
        offsets = {offset for offset, _ in marks}
        covered = sum(1 for start, end in ranges if any(abs(o - start) <= 4 for o in offsets))
        touching_x18 = []
        for offset, kind in marks:
            begin = max(0, offset - 8)
            for instruction in decoder.disasm(original[begin:begin + 16], begin):
                if instruction.address <= offset < instruction.address + instruction.size:
                    accessed = instruction.regs_access()
                    names = set(instruction.reg_name(r) for r in list(accessed[0]) + list(accessed[1]))
                    if "x18" in names or "w18" in names:
                        touching_x18.append((offset, kind, instruction.mnemonic, instruction.op_str))
        print("%-8s .text %d 字节；改动 %d 字节 / %d 段；改写点 %d 个 %s；差异落在改写点附近 %d/%d 段；改写点涉及 x18 的 %d 个"
              % (name, size, len(differences), len(ranges), len(marks), kinds, covered, len(ranges), len(touching_x18)))
        for item in touching_x18[:5]:
            print("      ", item)
        if covered != len(ranges) or touching_x18:
            failures.append(name)
    if failures:
        print("不合格：%s（存在改写点之外的改动，或改写点动了 x18）" % "、".join(failures))
        return 1
    print("全部模块：改动只在改写点上，且没有改写点涉及 x18 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
