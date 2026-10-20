#!/usr/bin/env python3
"""TotK 着色器事实表：从**机器码本身**推出贴图维度类型与顶点属性分量类型。

背景（计划 §4.4）：翻译器要问三类事实 —— 贴图槽的维度类型（2d / 3d / cube / buffer …）、
图像槽的格式、顶点属性与片元输出的分量类型。D2R 的那张表是从 PC 版 DXBC 反射冻结的，
TotK 没有 PC 版。NA-033 的实测结论：

* **SPH 里没有这些事实**。图形着色器的 SPH 是 0x50 字节（代码区 +0x30 处；+0x00..0x2F 是
  NVN 头，魔数 0x12345678），字段见仓内 vendored 的 Ryujinx `Translation/ShaderHeader.cs`：
  阶段、MRT、discard、global store、SASS 版本、局部内存、输出拓扑、
  **ImapTypes[32]（顶点属性的输入映射类型）**、**OmapTargets（片元输出数）**。
  贴图维度与图像格式都不在里面；NVN 着色器控制头（0x98761234）里也没有按槽的描述符表
  （9807 个着色器只有 86 种固定布局）。
* **贴图维度类型在机器码里**。Maxwell 的贴图指令自带维度字段，Ryujinx 自己的翻译器就是
  这么做的（`Instructions/InstEmitTexture.cs` 的 `ConvertSamplerType(TexDim)`）：
  TEX / TLD / TLD4 / TMML / TXD 用 `Dim`（第 28..30 位），TEXS 用 `Target`（第 53..56 位），
  TLDS 用 `Target`（第 53..56 位）。贴图槽号由立即数 `TidB`（第 36..48 位）给出：
  它是 c[2] 里的**字偏移**，×4 得字节偏移。

c[2] 的槽表布局（实测）：D2R 的着色器用**分离**贴图（c[2] 的 0x168 + 8r）与分离采样器
（0x568 + 8r）；TotK 的着色器用**合并**句柄（类型 0），落在 0x20 + 8r，一共 32 槽
（0x20..0x120，正好接在图像句柄表 0x120 之前）。所以这里的槽号按合并表算。

用法：totk_facts.py --index <shader_index.tsv> --code <机器码目录> --out <事实表.tsv>
      [--tex-base 0x20] [--no-attr]
产物（事实表）写在仓库外；着色器与由它生成的东西不进仓库。
"""
import argparse
import json
import struct
from pathlib import Path

# Ryujinx `Decoders/InstTable.cs` 的操作码表（14 位编码，'x' = 任意位；位序从最高位起）。
TEX_OPS = {
    "Tex":  ("11000" + "x" * 59, "dim"),
    "TexB": ("1101111010" + "x" * 54, "none"),
    "Texs": ("1101100" + "x" * 57, "texs"),
    "TexsF16": ("1101000" + "x" * 57, "texs"),
    "Tld":  ("11011100" + "x" * 56, "dim"),
    "TldB": ("11011101" + "x" * 56, "none"),
    "Tlds": ("1101101" + "x" * 57, "tlds"),
    "TldsF16": ("1101001" + "x" * 57, "tlds"),
    "Tld4": ("110010" + "x" * 58, "dim"),
    "Tld4s": ("1101111100" + "x" * 54, "none"),
    "Tld4sF16": ("1101111110" + "x" * 54, "none"),
    "Tmml": ("1101111101011" + "x" * 50, "dim"),
    "Txd":  ("110111100" + "x" * 55, "dim"),
}
# Ryujinx `Decoders/InstDecoders.cs` 的 TexDim / TexsTarget / TldsTarget。
TEX_DIM = {0: "1d", 1: "1darray", 2: "2d", 3: "2darray", 4: "3d", 5: "3darray", 6: "cube", 7: "cubearray"}
TEXS_TARGET = {0: "1d", 1: "2d", 2: "2d", 3: "2d", 4: "2ds", 5: "2ds", 6: "2ds",
                7: "2darray", 8: "2darray", 9: "2darrays", 10: "3d", 11: "3d", 12: "cube", 13: "cube"}
TLDS_TARGET = {0: "1d", 1: "1d", 2: "2d", 4: "2d", 5: "2d", 6: "2dms", 7: "3d", 8: "2darray", 12: "2d"}
SPH_SIZE = 0x50            # 图形着色器的 SPH 长度（Ryujinx ShaderHeader 读 0x50 字节）
IMAP_CONSTANT = 1         # ImapPixelType.Constant：整数属性
IMAP_UNUSED = 0


def _match(word, pattern):
    for i, ch in enumerate(pattern):
        if ch != "x" and int(ch) != (word >> (63 - i)) & 1:
            return False
    return True


def _instructions(program, start):
    """Maxwell 指令流：每 4 个 64 位字的第 1 个是调度控制字。 | Maxwell instruction stream: every 4th 64-bit word is a scheduling control word."""
    for k in range(start, len(program) - 7, 8):
        if ((k - start) // 8) % 4 == 0:
            continue
        yield struct.unpack_from("<Q", program, k)[0]


def texture_dims(program, tex_base):
    """机器码 → {c[2] 槽: 维度类型}。 | the machine code → {c[2] slot: dimension type}."""
    out = {}
    for word in _instructions(program, SPH_SIZE):
        for _name, (pattern, kind) in TEX_OPS.items():
            if not _match(word, pattern):
                continue
            if kind == "none":
                break
            if kind == "dim":
                dim = TEX_DIM[(word >> 28) & 0x7]
            elif kind == "texs":
                dim = TEXS_TARGET.get((word >> 53) & 0xF)
            else:
                dim = TLDS_TARGET.get((word >> 53) & 0xF)
            if dim is None:
                break
            byte = ((word >> 36) & 0x1FFF) * 4      # TidB 是 c[2] 的字偏移
            if byte < tex_base or (byte - tex_base) % 8:
                break
            out.setdefault((byte - tex_base) // 8, set()).add(dim)
            break
    return out


def sph_attr_types(program):
    """SPH 的 ImapTypes[32] → {属性号: 'uint' / 'float'}（Constant = 整数属性）。 | SPH ImapTypes[32] → {attribute index: 'uint' / 'float'}."""
    if len(program) < SPH_SIZE:
        return {}
    words = struct.unpack_from("<20I", program, 0)
    out = {}
    for i in range(32):
        byte = (words[6 + (i >> 2)] >> ((i & 3) * 8)) & 0xFF
        mapper = byte & 3                              # X 分量（其余分量同一属性）
        if mapper == IMAP_UNUSED:
            continue
        out[str(i)] = "uint" if mapper == IMAP_CONSTANT else "float"
    return out


def read_index(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            if not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            r = dict(zip(header, c))
            r["local"] = None if r.get("local", "-") in ("-", "") else [int(v) for v in r["local"].split("x")]
            r["shared"] = int(r.get("shared", 0) or 0)
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", type=Path, required=True, help="totk_shaders.py 产出的索引 TSV | the index TSV")
    ap.add_argument("--code", type=Path, required=True, help="机器码目录（code/<键>.bin） | the machine-code dir")
    ap.add_argument("--out", type=Path, required=True, help="事实表输出路径（仓库外） | the fact table (outside the repo)")
    ap.add_argument("--tex-base", type=lambda s: int(s, 0), default=0x20, help="c[2] 合并贴图句柄表的字节基址 | byte base of the combined texture handle table in c[2]")
    ap.add_argument("--no-attr", action="store_true", help="不输出顶点属性事实 | do not emit the vertex attribute facts")
    args = ap.parse_args()

    records = read_index(args.index)
    rows, stats = [], {"tex": 0, "attr": 0, "conflict": 0, "dim": {}}
    for r in records:
        program = (args.code / (r["key"] + ".bin")).read_bytes()
        facts = {"tex": {}, "img": {}, "attr": {}, "fout": {}}
        if r["stage"] != "cs":
            dims = texture_dims(program, args.tex_base)
            for slot, values in dims.items():
                if len(values) > 1:
                    stats["conflict"] += 1
                facts["tex"][str(slot)] = sorted(values)[0]
                stats["dim"][sorted(values)[0]] = stats["dim"].get(sorted(values)[0], 0) + 1
            if facts["tex"]:
                stats["tex"] += 1
            # ImapTypes 只对顶点阶段有意义（片元阶段那里是插值输入，计算阶段没有 SPH）。
            # ImapTypes only applies to the vertex stage (in the pixel stage it describes interpolated inputs, and compute shaders have no SPH).
            if not args.no_attr and r["stage"] == "vs":
                facts["attr"] = sph_attr_types(program)
                if facts["attr"]:
                    stats["attr"] += 1
        if r.get("local"):
            facts["local"] = r["local"]
        if r.get("shared"):
            facts["shared"] = r["shared"]
        rows.append(r["key"] + "\t" + json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("# TotK 翻译查询的作答表（totk_facts.py 生成；不在仓库里）：键 <TAB> 事实 JSON\n"
                        + "\n".join(sorted(rows)) + "\n", encoding="utf-8")
    print("事实表：%s（%d 键）" % (args.out, len(rows)))
    print("有贴图维度事实的键 %d；有属性事实的键 %d；同一槽出现多种维度的 %d" % (stats["tex"], stats["attr"], stats["conflict"]))
    print("维度分布：%s" % ", ".join("%s=%d" % kv for kv in sorted(stats["dim"].items())))


if __name__ == "__main__":
    main()
