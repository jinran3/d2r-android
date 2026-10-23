#!/usr/bin/env python3
# 核对宿主对 NVN 接口的覆盖：TotK 会调用哪些、宿主实现了哪些、还差哪些。
# Check the host's NVN coverage: which interfaces TotK calls, which the host implements, and what is missing.
# 事实来源：
#   dm/gfx/nvn/names.txt          名字表（宿主按名字取址；不在表里 → 取址失败 → 崩溃）
#   dm/gfx/nvn/nvn_calls_totk.tsv TotK 真正调用的接口与调用点数（静态扫描 TotK main 的 .text）
#   dm/gfx/nvn/hle_nvn.c          宿主实现（NVN(...) / NVN_NOPROTO(...) 宏）与空实现名单
# 用法：nvn_coverage.py [--check]
#   --check 有「TotK 调用但宿主没实现」的接口时非零退出（CI 用）
# Verify the host's NVN coverage: the interfaces TotK calls, which ones the host implements, and the gaps.
# Usage: nvn_coverage.py [--check]
import argparse, pathlib, re, sys

ap = argparse.ArgumentParser()
ap.add_argument('--check', action='store_true')
a = ap.parse_args()

root = pathlib.Path(__file__).resolve().parents[2]
nvn = root / 'gfx' / 'nvn'

def raw(path):
    return pathlib.Path(path).read_text(encoding='utf-8')

names = [l.strip() for l in raw(nvn / 'names.txt').splitlines() if l.strip() and not l.startswith('#')]
calls = {}
for line in raw(nvn / 'nvn_calls_totk.tsv').splitlines():
    if line.startswith('#') or not line.strip(): continue
    p = line.split('\t')
    if len(p) == 2 and p[0] != 'name': calls[p[0]] = int(p[1])

src = raw(nvn / 'hle_nvn.c')
impl = set(re.findall(r"\bNVN(?:_NOPROTO)?\((\w+),", src))
nops = set(re.findall(r'"(nvn\w+)"', src[src.index('static const char *const g_nops[]'):src.index('g_nops[]') + 2000]))

unknown = [n for n in calls if n not in names]                    # 取址会失败 → 崩溃
empty = [n for n in calls if n in names and n not in impl and n in nops]   # 有名字，接的是空实现
missing = [n for n in calls if n in names and n not in impl and n not in nops]   # 有名字，但接报红桩
print(f'名字表 {len(names)}；TotK 调用 {len(calls)}；宿主实现 {len(impl)}（其中空实现 {len(nops)}）')
print(f'TotK 调用但名字表里没有：{len(unknown)}')
for n in unknown: print('   [取址失败]', n)
print(f'TotK 调用但宿主是空实现（g_nops）：{len(empty)}')
for n in sorted(empty, key=lambda x: -calls[x]):
    print(f'   [空实现] {n}  调用点 {calls[n]}')
print(f'TotK 调用但宿主没实现：{len(missing)}')
for n in sorted(missing, key=lambda x: -calls[x]):
    print(f'   [缺实现] {n}  调用点 {calls[n]}')
if a.check and (unknown or missing):
    sys.exit(1)
