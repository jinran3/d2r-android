#!/usr/bin/env python3
"""TotK 着色器包：把翻译好的 SPIR-V 与反射打包成宿主能按**控制段哈希**找到的样子。

宿主的取名口径（`dm/android/native/nvn_vulkan_shader.inc` 的 `shader_get`）：运行期宿主拿到的是
着色器**控制段指针**，按它的前 0x880 字节算 sha256，取前 16 个十六进制字符当键，然后按这个键去
数据包里找 `<键>.meta`（紧凑反射）与 `<键>.spv`（SPIR-V）。

TotK 的麻烦：**同一个控制段会被多个机器码变体共用**（实测 49,089 个变体里只有 5,534 个不同的
控制段哈希，其中 1,640 个控制段对应多种机器码），而流水线给的键是 `sha256(控制段+机器码+c1)`，
两个口径不同 —— 宿主一个也找不到。本工具按宿主口径重新命名，并对歧义的控制段**选一个变体**
（默认取出现次数最多的那个），把每一个歧义控制段的全部候选写进 `ambiguity.tsv`，供真机验证后再调整。

用法：
  totk_shader_package.py --index <shader_index.tsv> --spirv <翻译输出目录> --out <包目录>
                          [--facts <事实表.tsv>] [--ambiguity <歧义报告路径>]
  totk_shader_package.py --verify-shaders <着色器包目录> [--tex-base 0x20] [--tex-end 0x120]

`--verify-shaders` 单独核对着色器包：每个 `.meta` 里贴图/图像绑定的 c[2] 字节偏移
（`(handle & 0x3fff) * 4`）必须落在该档位的句柄表区间内且 8 字节对齐 ——
这是「TotK 用合并句柄表 0x20+8r」这个结论的独立验证：机器码里的贴图立即数真的指着那一张表。
产出（仓库外）：
  <包目录>/shaders/<宿主键>.spv    翻译好的 SPIR-V
  <包目录>/shaders/<宿主键>.meta    紧凑反射（DMVK 格式，与 D2R 侧 build_shaders.py 同格式）
  <包目录>/host-profile.json        宿主要的能力与数量说明
  <歧义报告路径>                    控制段哈希 -> 候选变体（含机器码差异字节数）

TotK shader package: repackage the translated SPIR-V and the reflection under the key the host
looks up (the hash of the control segment).
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
from collections import Counter, defaultdict
from pathlib import Path

STAGE = {"vs": 0, "ps": 1, "gs": 2, "hs": 3, "ds": 4, "cs": 5}


def find(root, name):
    """在翻译输出目录里找文件（分片 out*/ 与平铺两种布局）。 | Find a file in the translation output (sharded out*/ or flat)."""
    direct = root / name
    if direct.is_file():
        return direct
    for shard in sorted(root.glob("out*")):
        candidate = shard / name
        if candidate.is_file():
            return candidate
    return direct


def read_index(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            if not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            rows.append(dict(zip(header, c)))
    return rows


def read_facts(path):
    facts = {}
    if not path:
        return facts
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            key, value = line.rstrip("\n").split("\t", 1)
            facts[key] = json.loads(value)
    return facts


def build_meta(stage, entries, c1, attributes):
    """紧凑反射：与 D2R 侧 dm/android/tools/build_shaders.py 同一格式（DMVK）。"""
    binary = struct.pack("<4s6I", b"DMVK", 1, STAGE[stage], stage_set(stage), len(entries), len(c1), 32)
    for kind, binding in entries:
        values = [kind, binding["binding"], binding.get("slot", 0),
                  binding.get("cb_slot", binding.get("cbuf_slot", 0)), binding.get("cb_offset", 0),
                  binding.get("handle", 0), binding.get("type", 0), binding.get("array", 1),
                  binding.get("flags", 0), binding.get("separate", 0)]
        binary += struct.pack("<10I", *(v & 0xFFFFFFFF for v in values))
    return binary + c1 + struct.pack("<32I", *attributes)


def stage_set(stage):
    """描述符组：与 D2R 侧一致（顶点 0、片元 1、几何 2、外壳 3、域 4、计算 0）。"""
    return {"vs": 0, "ps": 1, "gs": 2, "hs": 3, "ds": 4, "cs": 0}[stage]


def spirv_inputs(code, facts):
    """从 SPIR-V 里取顶点输入的位置与类型（与 D2R 侧同一做法：类型来自事实表，位置来自 SPIR-V）。"""
    words = struct.unpack("<" + "I" * (len(code) // 4), code)
    locations, inputs, position = {}, set(), 5
    while position < len(words):
        length, opcode = words[position] >> 16, words[position] & 0xFFFF
        if not length or position + length > len(words):
            raise ValueError("SPIR-V 指令流不合法")
        if opcode == 71 and length >= 4 and words[position + 2] == 30:
            locations[words[position + 1]] = words[position + 3]
        elif opcode == 59 and length >= 4 and words[position + 3] == 1:
            inputs.add(words[position + 2])
        position += length
    attributes = [0] * 32
    for variable in inputs:
        location = locations.get(variable)
        if location is not None and location < 32:
            attributes[location] = {"float": 1, "sint": 2, "uint": 3}[facts.get(str(location), "float")]
    return attributes


def verify_shaders(directory, tex_base, tex_end):
    """核对着色器包：meta 里的贴图/图像绑定必须落在该档位的句柄表区间内。

    Check the shader package: the texture and image bindings in every .meta must sit inside the
    profile's handle table.
    """
    import struct
    metas = sorted(p for p in directory.iterdir() if p.name.endswith(".meta"))
    if not metas:
        raise SystemExit("no .meta files in " + str(directory))
    offsets = set()
    bad = []
    for path in metas:
        blob = path.read_bytes()
        magic, version, stage, group, count, c1_size, attributes = struct.unpack_from("<4s6I", blob, 0)
        if magic != b"DMVK" or version != 1 or attributes != 32:
            bad.append((path.name, "header"))
            continue
        position = 28
        for _ in range(count):
            kind, binding, slot, cb_slot, cb_offset, handle, type, array, flags, separate = struct.unpack_from("<10I", blob, position)
            if kind in (3, 4):
                offset = (handle & 0x3FFF) * 4
                offsets.add(offset)
                if not tex_base <= offset < tex_end or (offset - tex_base) % 8:
                    bad.append((path.name, hex(offset)))
            position += 40
    print("着色器包 %s：%d 个 meta，贴图/图像用到的 c[2] 偏移 %d 个（%s .. %s）"
          % (directory, len(metas), len(offsets), hex(min(offsets)) if offsets else "-",
             hex(max(offsets)) if offsets else "-"))
    if bad:
        print("不合规 %d 个（前面几个：%s）" % (len(bad), bad[:5]))
        return 1
    print("全部落在 [%#x, %#x) 且 8 字节对齐 ✓" % (tex_base, tex_end))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify-shaders", type=Path, help="只核对着色器包 | only verify the shader package")
    parser.add_argument("--tex-base", type=lambda v: int(v, 0), default=0x20, help="贴图句柄表基址 | the texture handle table base")
    parser.add_argument("--tex-end", type=lambda v: int(v, 0), default=0x120, help="贴图句柄表上界 | the end of the texture handle table")
    parser.add_argument("--index", type=Path, help="totk_shaders.py 产出的索引 TSV | the index TSV")
    parser.add_argument("--spirv", type=Path, help="翻译输出目录（<键>.spv 与 <键>.res.json）| the translation output dir")
    parser.add_argument("--out", type=Path, help="包输出目录 | the package output dir")
    parser.add_argument("--facts", type=Path, help="事实表（属性分量类型）| the fact table")
    parser.add_argument("--ambiguity", type=Path, help="歧义报告路径 | the ambiguity report path")
    args = parser.parse_args()
    if args.verify_shaders:
        return verify_shaders(args.verify_shaders, args.tex_base, args.tex_end)
    for name in ("index", "spirv", "out"):
        if getattr(args, name) is None:
            parser.error("--%s is required unless --verify-shaders is used" % name)

    rows = read_index(args.index)
    facts = read_facts(args.facts)
    by_host = defaultdict(list)
    for row in rows:
        by_host[row["host_key"]].append(row)

    # 同一个控制段哈希下选一个变体：出现次数最多的优先（索引按字典序，取第一个同数的）。
    # Pick one variant per control hash: the most frequent one wins.
    chosen, ambiguous = {}, []
    for host_key, group in by_host.items():
        counts = Counter(row["key"] for row in group)
        best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        chosen[host_key] = best
        if len(counts) > 1:
            ambiguous.append((host_key, sorted(counts.items(), key=lambda item: (-item[1], item[0]))))

    shaders = args.out / "shaders"
    shaders.mkdir(parents=True, exist_ok=True)
    packaged = missing = 0
    for host_key, group in by_host.items():
        key = chosen[host_key]
        row = next(item for item in group if item["key"] == key)
        # 翻译输出可能是分片的（out0..out5/），两种布局都找。
        # The translation output may be sharded (out0..out5/); accept both layouts.
        spv = find(args.spirv, key + ".spv")
        res = find(args.spirv, key + ".res.json")
        if not spv.is_file() or not res.is_file():
            missing += 1
            continue
        meta = json.loads(res.read_text(encoding="utf-8"))
        entries = [(0, {"binding": 0})]
        for kind, label in [(1, "cbufs"), (2, "sbufs"), (3, "textures"), (4, "images")]:
            entries += [(kind, binding) for binding in meta.get(label, [])]
        c1 = bytes.fromhex(row.get("c1") or "")
        code = spv.read_bytes()
        attributes = spirv_inputs(code, facts.get(key, {}).get("attr", {})) if row["stage"] == "vs" else [0] * 32
        (shaders / (host_key + ".spv")).write_bytes(code)
        (shaders / (host_key + ".meta")).write_bytes(build_meta(row["stage"], entries, c1, attributes))
        packaged += 1

    report = args.ambiguity or (args.out / "ambiguity.tsv")
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", encoding="utf-8") as f:
        f.write("host_key\tvariants\tchosen\tcounts\n")
        for host_key, counts in sorted(ambiguous):
            f.write("%s\t%d\t%s\t%s\n" % (host_key, len(counts), chosen[host_key],
                                           ",".join("%s:%d" % item for item in counts)))
    profile = {"schema": 1, "shader_count": packaged, "spirv_target": "vulkan1.1",
               "host_key": "sha256(control[0:0x880])", "control_keys": len(by_host),
               "variant_keys": len(rows), "ambiguous_control_keys": len(ambiguous)}
    (args.out / "host-profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print("着色器包：%d 个宿主键（变体 %d 个），歧义控制键 %d 个；缺翻译结果 %d 个"
          % (packaged, len(rows), len(ambiguous), missing))
    print("包目录：%s；歧义报告：%s" % (shaders, report))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
