#!/usr/bin/env python3
# 核对「变体键」这条链：流水线算的键、宿主运行期算的键、包里的变体名单，三者必须逐字节一致。
# Verify the variant-key chain: the key the pipeline computes, the key the host computes at run time
# and the variant lists in the package must agree byte for byte.
#
# 关键代数：流水线键 = sha256(控制段 + 机器码 + c1)；
# 宿主运行期算的是 sha256(控制段前 0x880 字节 + 机器码 + c1) —— 控制段恰好就是 0x880 字节，
# 机器码与 c1 在代码区里首尾相接，所以两边的字节完全一样 → 键相同。
# The key algebra: the pipeline key is sha256(control + machine code + c1); the host computes
# sha256(control[0:0x880] + machine code + c1). The control block is exactly 0x880 bytes and the machine
# code and c1 are adjacent in the code area, so both sides hash the same bytes → the same key.
#
# 用法：totk_variant_keys.py --index <shader_index.tsv> --code <代码区目录> --shaders <包里的着色器目录> [--bfsha <目录>]
# Usage: totk_variant_keys.py --index <shader_index.tsv> --code <code dir> --shaders <package shader dir> [--bfsha <dir>]
import argparse, hashlib, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import totk_shaders  # noqa: E402  (the archive parser lives next to this tool)

ap = argparse.ArgumentParser()
ap.add_argument('--index', type=pathlib.Path, required=True)
ap.add_argument('--code', type=pathlib.Path, required=True)
ap.add_argument('--shaders', type=pathlib.Path, required=True)
ap.add_argument('--bfsha', type=pathlib.Path, default=None)
a = ap.parse_args()

rows = []
with a.index.open(encoding='utf-8') as f:
    header = f.readline().rstrip('\n').split('\t')
    for line in f:
        if line.strip():
            rows.append(dict(zip(header, line.rstrip('\n').split('\t'))))
index = {r['key']: r for r in rows}

# 1) 代码区里的机器码要与归档里的一致（按键取）
code_mismatch = 0
for row in rows:
    path = a.code / (row['key'] + '.bin')
    if path.is_file() and path.stat().st_size != int(row['program_bytes']):
        code_mismatch += 1
print('索引 %d 行；代码区里机器码长度对不上的 %d 个' % (len(rows), code_mismatch))

# 2) 归档侧重算：宿主口径的完整键必须等于流水线的键；c1 必须与索引一致
key_mismatch = c1_mismatch = control_mismatch = pairs = 0
if a.bfsha:
    for path in sorted(a.bfsha.glob('*.bfsha')):
        for control, code in totk_shaders.shaders(path.read_bytes()):
            info, program = totk_shaders._stage(control, code)
            row = index.get(info['key'])
            if row is None:
                continue
            pairs += 1
            c1 = code[info['c1_offset']:info['total']] if 'c1_offset' in info else None
            # _stage 已经把 c1 放进 info["c1"]
            if info['c1'] != (row.get('c1') or ''):
                c1_mismatch += 1
            if info['control_bytes'] != int(row['control_bytes']):
                control_mismatch += 1
            # 宿主运行期的算法：控制段前 0x880 字节 + 机器码 + c1
            host_full = hashlib.sha256(control[:0x880] + program + bytes.fromhex(info['c1'])).hexdigest()[:16]
            if host_full != info['key']:
                key_mismatch += 1
    print('归档里核对 %d 个着色器：宿主口径完整键对不上的 %d 个，c1 对不上的 %d 个，控制段长度对不上的 %d 个'
          % (pairs, key_mismatch, c1_mismatch, control_mismatch))
else:
    print('（没给 --bfsha，跳过归档侧核对）')

# 3) 包里的变体名单：名单里的键必须都有文件，且每个键都在索引里
listed = missing_file = unknown = 0
for path in sorted(a.shaders.glob('*.variants')):
    for line in path.read_text(encoding='utf-8').splitlines():
        key = line.strip()
        if not key:
            continue
        listed += 1
        if not (a.shaders / (key + '.spv')).is_file() or not (a.shaders / (key + '.meta')).is_file():
            missing_file += 1
        if key not in index:
            unknown += 1
print('变体名单列了 %d 个键：缺文件 %d 个，不在索引里 %d 个' % (listed, missing_file, unknown))

bad = code_mismatch or key_mismatch or c1_mismatch or control_mismatch or missing_file or unknown
print('结果：%s' % ('一致 ✓' if not bad else '有不一致 ✗'))
sys.exit(1 if bad else 0)
