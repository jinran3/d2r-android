#!/usr/bin/env python3
"""TotK 着色器包的格式闸门：meta 必须与宿主（nvn_vulkan_shader.inc 的 shader_load_by_key）读的一致。

宿主读反射时的校验是：魔数 DMVK、版本 1、绑定数 ≤ 256、c1 长度 ≤ 65536、属性数 32，
且**总字节数必须正好等于 28 + 绑定数×40 + c1 长度 + 128**。这条测试就用合成的 res.json 与
SPIR-V 走一遍打包工具，再按宿主那条规则逐字节核对。

用法：python3 dm/gfx/tools/test_totk_shader_package.py
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "dm/gfx/tools/totk_shader_package.py"


def spirv_with_input(location):
    """造一个带一个顶点输入（Location = location）的最小 SPIR-V 模块。"""
    words = [0x07230203, 0x00010000, 0, 8, 0]
    # 每条指令的头一个字是 (长度 << 16) | 操作码，后面才是操作数。
    # The first word of each instruction is (length << 16) | opcode, the operands follow.
    words += [(4 << 16) | 71, 2, 30, location]   # OpDecorate：目标 2（下面那个变量），Location = location
    words += [(5 << 16) | 59, 1, 2, 1, 0]        # OpVariable：类型 1，结果 2，Input
    return struct.pack("<" + "I" * len(words), *words)


def main():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        index = work / "shader_index.tsv"
        index.write_text(
            "key\tstage\tsource\tcontrol_bytes\tprogram_bytes\tc1_bytes\tlocal\tshared\tc1\thost_key\n"
            "0123456789abcdef\tvs\tsample.bin\t2176\t64\t4\t-\t0\t01020304\thost0123456789ab\n",
            encoding="utf-8")
        spirv = work / "spirv"
        spirv.mkdir()
        (spirv / "0123456789abcdef.spv").write_bytes(spirv_with_input(7))
        (spirv / "0123456789abcdef.res.json").write_text(json.dumps({
            "cbufs": [{"binding": 1, "slot": 3}],
            "sbufs": [{"binding": 2, "slot": 1, "cb_slot": 2, "cb_offset": 4, "flags": 1}],
            "textures": [{"binding": 3, "type": 1, "cbuf_slot": 2, "handle": 90, "array": 1, "flags": 0, "separate": 0}],
            "images": [],
        }), encoding="utf-8")
        facts = work / "facts.tsv"
        facts.write_text("# facts\n0123456789abcdef\t{\"attr\":{\"7\":\"uint\"}}\n", encoding="utf-8")
        out = work / "package"
        result = subprocess.run([sys.executable, str(TOOL), "--index", str(index), "--spirv", str(spirv),
                                 "--out", str(out), "--facts", str(facts)], capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0:
            print("打包工具失败：", result.stdout, result.stderr)
            return 1
        meta = (out / "shaders" / "host0123456789ab.meta").read_bytes()
        magic, version, stage, group, count, c1_size, attributes = struct.unpack_from("<4s6I", meta, 0)
        assert magic == b"DMVK", magic
        assert version == 1
        assert stage == 0 and group == 0, (stage, group)
        assert count == 4, count          # 一条占位 + cbuf + ssbo + texture
        assert c1_size == 4, c1_size
        assert attributes == 32, attributes
        assert len(meta) == 28 + count * 40 + c1_size + 128, len(meta)
        # c1 与属性数组按宿主读法排在绑定表之后。
        assert meta[28 + count * 40:28 + count * 40 + 4] == b"\x01\x02\x03\x04"
        attribute_types = struct.unpack_from("<32I", meta, 28 + count * 40 + 4)
        assert attribute_types[7] == 3, attribute_types[7]   # uint
        assert sum(attribute_types) == 3
        assert (out / "shaders" / "host0123456789ab.spv").is_file()
        assert (out / "ambiguity.tsv").is_file()
    print("TotK shader package: DMVK meta matches the host layout, c1 and attribute types PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
