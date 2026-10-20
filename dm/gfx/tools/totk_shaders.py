#!/usr/bin/env python3
"""TotK 着色器归档的解析：索引（键 / 阶段）与可用的事实（计算着色器的线程组与共享内存）。

计划 §4.4 的事实表（`dm/gfx/nvn/shader_facts.tsv`）要回答翻译器的提问：贴图维度类型、
图像格式、顶点属性与片元输出的分量类型、计算着色器的线程组大小与共享内存字节数。
D2R 的那张表是从 PC 版着色器的反射冻结的；TotK 没有 PC 版，所以事实得从**游戏自己的**
着色器归档里取。

TotK 的归档结构（BNSH / FSHA / BAHS v9）：
  · 每个着色器由一对数据组成：**控制头**（control，NVN 着色器控制头，魔数 0x98761234，
    major 1、minor 9 或 16）与**机器码**（program）+ **C1 块**；
  · 着色器键 = `sha256(control + program + c1)` 的前 16 个十六进制字符（与既有事实表的键格式一致）；
  · 阶段由控制头里的 kind 决定（0 vs / 1 ps / 2 gs / 3 hs / 4 ds / 5 cs）；
  · **计算着色器**的线程组大小与共享内存字节数就在控制头 0x748 处（local x/y/z + shared）——
    这部分事实不需要 PC 反射，TotK 侧直接可得；
  · 贴图维度 / 图像格式 / 属性分量类型所在的位置还没定位（C1 块很小，多半在控制头里的
    描述符表），先把能确定的做出来，剩下��按计划 §4.4 的方案 A（缺省 + 统计补齐）与
    方案 B（运行期在 `hle_nvn.c` 观测 `nvnTextureBuilderSetDims` / `SetFormat` 反填）走。

用法：totk_shaders.py <着色器目录> <输出目录>
产物落在仓库外；游戏内容与密钥都不进仓库。

Parse TotK shader archives: index (key / stage) and the facts we can get (compute shader
workgroup size and shared memory).
The fact table (dm/gfx/nvn/shader_facts.tsv) answers the translator's questions: texture
dimension type, image format, vertex attribute and fragment output component types, compute
thread group size and shared memory bytes. D2R's table was frozen from the PC build's shader
reflection; TotK has no PC build, so the facts have to come from the game's own shader archives.

Archive layout (BNSH / FSHA / BAHS v9): every shader is a **control header** (NVN shader
control header, magic 0x98761234, major 1, minor 9 or 16) plus the **machine code** (program) and
the **C1 block**; the shader key is `sha256(control + program + c1)` truncated to 16 hex chars
(the same key format the existing fact table uses); the stage comes from the kind field in the
control header (0 vs / 1 ps / 2 gs / 3 hs / 4 ds / 5 cs); for **compute** shaders the workgroup
size and the shared memory size sit at 0x748 of the control header (local x/y/z + shared) - those
facts need no PC reflection and are directly available for TotK. Where the texture dimensions /
image formats / attribute component types live is not located yet (the C1 block is tiny, so they
are most likely in the control header's descriptor table); those still go by plan §4.4 option A
(defaults + statistics) and option B (observe nvnTextureBuilderSetDims / SetFormat at run time
and back-fill).

Usage: totk_shaders.py <shader directory> <output directory>
The outputs stay outside the repository; no game content or keys enter it.
"""
import argparse
import hashlib
import struct
from pathlib import Path

STAGES = {0: "vs", 1: "ps", 2: "gs", 3: "hs", 4: "ds", 5: "cs"}
CONTROL_MAGIC = 0x98761234
COMPUTE_FACTS_OFF = 0x748


def _read(data, offset, fmt):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise ValueError("结构越界")
    return struct.unpack_from(fmt, data, offset)


def _span(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError("归档范围越界")
    return data[offset:offset + size]


def _stage(control: bytes, code: bytes) -> dict:
    """解析一个着色器：键、阶段、控制头尺寸、机器码与 C1；计算着色器另给线程组事实。 | Parse one shader: key, stage, control size, code and C1; compute shaders also give the workgroup facts."""
    magic, major, minor = _read(control, 0, "<3I")
    declared, = _read(control, 0x20, "<I")
    if magic != CONTROL_MAGIC or major != 1 or minor not in (9, 16) or not 0x748 <= declared <= len(control):
        raise ValueError("不认识这个 NVN 着色器控制头")
    control = control[:declared]
    program_size, c1_size, c1_offset, total, offset, _, _, kind = _read(control, 0x6F8, "<8I")
    if kind not in STAGES or offset not in (0x30, 0x100) or c1_offset < offset + program_size:
        raise ValueError("着色器机器码布局不对")
    program = _span(code, offset, c1_offset - offset)
    c1 = _span(code, c1_offset, c1_size)
    result = {
        "key": hashlib.sha256(control + program + c1).hexdigest()[:16],
        "stage": STAGES[kind],
        "control_bytes": len(control),
        "program_bytes": len(program),
        "c1_bytes": len(c1),
    }
    if kind == 5:
        x, y, z, shared = _read(control, COMPUTE_FACTS_OFF, "<4I")
        if min(x, y, z) < 1 or x * y * z > 1024 or shared > 49152:
            raise ValueError("计算着色器的线程组参数不合法")
        result["local"] = [x, y, z]
        result["shared"] = shared
    return result, program


def _bnsh(data: bytes):
    """BNSH 容器：逐个程序给出（控制头, 机器码）。 | BNSH container: (control, code) per program."""
    if data[:8] != b"BNSH\0\0\0\0" or _read(data, 12, "<H")[0] != 0xFEFF or _read(data, 28, "<I")[0] != len(data):
        raise ValueError("BNSH 头不合法")
    if _span(data, 0x60, 4) != b"grsc":
        raise ValueError("BNSH 缺着色器块")
    count, table = _read(data, 0x7C, "<IQ")
    _span(data, table, count * 64)
    for index in range(count):
        program, = _read(data, table + index * 64 + 16, "<Q")
        if not program:
            raise ValueError("BNSH 缺机器码")
        for header in _read(data, program + 8, "<6Q"):
            if not header:
                continue
            control, code, code_size, control_size = _read(data, header + 8, "<QQII")
            yield _span(data, control, control_size), _span(data, code, code_size)


def _fsha(data: bytes):
    """FSHA（BFSHA v9）容器。 | FSHA (BFSHA v9) container."""
    if _read(data, 10, "<H")[0] != 9 or _read(data, 28, "<I")[0] != len(data):
        raise ValueError("只支持 BFSHA 版本 9")
    table, = _read(data, 0x48, "<Q")
    count, = _read(data, 0x78, "<H")
    _span(data, table, count * 256)
    for index in range(count):
        offset, = _read(data, table + index * 256 + 0xA8, "<Q")
        size, = _read(data, offset + 28, "<I")
        yield from _bnsh(_span(data, offset, size))


def _bahs(data: bytes):
    """BAHS v9 容器：变体段里每个变体给出（控制头, 机器码）。 | BAHS v9 container: (control, code) per variant."""
    _, version, size, _, endian, alignment, code_size, code_base = _read(data, 0, "<8I")
    if version != 9 or size != len(data) or endian or alignment < 2048 or alignment & (alignment - 1):
        raise ValueError("只支持小端 BAHS 版本 9")
    _span(data, code_base, code_size)
    section = 0x150 + alignment
    size, count = _read(data, section, "<II")
    _span(data, section, size)
    end = section + size
    pos = section + 8
    for _ in range(count):
        entry_size, _, _, payload_size = _read(data, pos, "<4I")
        if entry_size < 16 or payload_size != entry_size - 16 or pos + entry_size > end:
            raise ValueError("BAHS 变体段不合法")
        payload = _span(data, pos + 16, payload_size)
        code, code_pad, control_size, control, control_pad = _read(payload, 0, "<iIIiI")
        if code_pad or control_pad:
            raise ValueError("BAHS 相对偏移的填充不对")
        ctrl = _span(data, pos + 16 + control, control_size)
        shader_size, = _read(ctrl, 0x704, "<I")
        if code + shader_size > code_size:
            raise ValueError("BAHS 着色器越出代码区")
        yield ctrl, _span(data, code_base + code, shader_size)
        pos += entry_size
    if pos != end:
        raise ValueError("BAHS 变体数对不上")


def shaders(data: bytes):
    """按容器类型分派。 | Dispatch by container type."""
    magic = data[:4]
    if magic == b"BNSH":
        yield from _bnsh(data)
    elif magic == b"FSHA":
        yield from _fsha(data)
    elif magic == b"BAHS":
        yield from _bahs(data)
    elif data[:4] == b"\x34\x12\x76\x98":
        length, = _read(data, 0x20, "<I")
        yield _span(data, 0, length), _span(data, length, len(data) - length)
    else:
        raise ValueError("不认识的着色器容器 %s" % magic.hex())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="着色器文件目录（switch_shaders.py 解出来的） | the shader directory (produced by switch_shaders.py)")
    parser.add_argument("output", type=Path, help="输出目录 | the output directory")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    code_dir = args.output / "code"
    code_dir.mkdir(exist_ok=True)
    records = {}
    total = 0
    for path in sorted(args.source.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".bnsh", ".bfsha", ".sharcb", ".nvn"):
            continue
        try:
            entries = list(shaders(path.read_bytes()))
        except Exception as error:
            print("跳过 %s：%s" % (path.name, error))
            continue
        for control, code in entries:
            info, program = _stage(control, code)
            total += 1
            key = info["key"]
            prior = records.get(key)
            if prior and prior["stage"] != info["stage"]:
                print("键冲突（阶段不同）：%s" % key)
                continue
            if prior:
                continue
            records[key] = dict(info, source=path.name)
            (code_dir / (key + ".bin")).write_bytes(program)
    with (args.output / "shader_index.tsv").open("w", encoding="utf-8") as f:
        f.write("key\tstage\tsource\tcontrol_bytes\tprogram_bytes\tc1_bytes\tlocal\tshared\n")
        for key in sorted(records):
            r = records[key]
            local = "x".join(str(v) for v in r["local"]) if "local" in r else "-"
            f.write("%s\t%s\t%s\t%d\t%d\t%d\t%s\t%d\n" % (
                key, r["stage"], r["source"], r["control_bytes"], r["program_bytes"], r["c1_bytes"],
                local, r.get("shared", 0)))
    compute = [r for r in records.values() if r["stage"] == "cs"]
    stages = {}
    for r in records.values():
        stages[r["stage"]] = stages.get(r["stage"], 0) + 1
    print("着色器记录 %d 条（文件里共 %d 条），唯一键 %d 个" % (len(records), total, len(records)))
    print("按阶段：%s" % ", ".join("%s=%d" % (k, stages[k]) for k in sorted(stages)))
    print("计算着色器 %d 个（线程组与共享内存已从控制头 0x748 读出）" % len(compute))
    print("索引：%s" % (args.output / "shader_index.tsv"))


if __name__ == "__main__":
    main()
