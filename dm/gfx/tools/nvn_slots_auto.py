#!/usr/bin/env python3
# 自动定位 main 里的 NVN 取址函数，出「名字 / 槽 / 调用点」表（不写死地址，换版本也能用）。
# nvn_slots.py 把加载函数地址与 .text 尾写死在 D2R 3.3.94012 上；本脚本改为在 .text 里
# 认出「取名字 → 存指针」的那段代码，再从那里解析名字表与槽表。
#
# 加载函数有两种形态（都见过）：
#   A) D2R：adrp xN, 槽页 … str x0,[xN,#imm]        → 槽 = 槽页 + imm*8
#   B) TotK：adrp x8, 表页; ldr x8,[x8,#off]; str x0,[x8]  → 槽 = 表页 + off（表项本身是指针）
# 识别办法：对每条「str x0,[xB]」沿「对 xB 的最近一次写入」回溯，看那次写入是 adrp（形态 A）
# 还是自指的 ldr（形态 B）；两种都取不到就跳过。
#
# 调用点：全 .text 扫「ldr xT,[xN,#imm]」读槽，从读取点往回找 xN 的上一次写入，
# 是 adrp 到槽页才算一次调用点（与 nvn_slots.py 同一判据）。
#
# 用法：nvn_slots_auto.py <main 原映像 .bin> <.text 尾（十六进制，如 0x2ba61f0）> <输出 tsv> [名字表输出]
# Auto-locate the NVN loader in main and emit the name/slot/call-site table (no hard-coded addresses).
# Usage: nvn_slots_auto.py <main raw image .bin> <text end (hex)> <output tsv> [names output]
import struct, sys

img, text_end, out = sys.argv[1], int(sys.argv[2], 0), sys.argv[3]
d = open(img, 'rb').read()
N = text_end // 4
w = struct.unpack_from('<%dI' % N, d, 0)

def adrp(x, pc):
    imm = ((x >> 29) & 3) | (((x >> 5) & 0x7ffff) << 2)
    if imm & (1 << 20): imm -= 1 << 21
    return (pc & ~0xfff) + (imm << 12)

def cstr(a):
    if a < 0 or a >= len(d): return None
    e = d.find(b'\0', a)
    if e < 0 or e - a > 96: return None
    try: return d[a:e].decode('ascii')
    except UnicodeDecodeError: return None

def is_adrp(x): return x & 0x9f000000 == 0x90000000
def is_add_imm(x, rd): return x & 0xffc00000 == 0x91000000 and (x & 31) == rd
def is_str_x0(x): return x & 0xffc00000 == 0xf9000000 and (x & 31) == 0
def is_ldr_u64(x): return x & 0xffc00000 == 0xf9400000

def writes(x, r):
    op0 = (x >> 25) & 0xf
    if x & 0x9f000000 == 0x90000000: return (x & 31) == r          # adrp 写 Rd | adrp writes Rd
    if x & 0xfc000000 == 0x94000000 or x & 0xfffffc1f == 0xd63f0000: return r <= 18
    if op0 in (0b1000, 0b1001, 0b0101, 0b1101): return (x & 31) == r
    if op0 & 0b0101 == 0b0100:
        L = (x >> 22) & 1
        if (x >> 27) & 7 == 0b101:
            wb = (x >> 23) & 3 in (1, 3)
            return (L and ((x & 31) == r or ((x >> 10) & 31) == r)) or (wb and ((x >> 5) & 31) == r)
        if (x >> 27) & 7 == 0b111 and (x >> 24) & 3 == 0:
            wb = (x >> 21) & 1 == 0 and (x >> 10) & 3 in (1, 3)
            return (L and ((x & 31) == r)) or (wb and ((x >> 5) & 31) == r)
        if (x >> 27) & 7 == 0b111: return bool(L) and (x & 31) == r
        if (x >> 27) & 7 == 0b011: return (x & 31) == r
    return False

def adrp_page_for(rn, before):
    for k in range(before - 1, max(before - 12, -1), -1):
        if is_adrp(w[k]) and (w[k] & 31) == rn: return adrp(w[k], k * 4)
    return None

def slot_of_store(i):
    """返回 (槽地址, 形态) 或 None。| Slot address of a candidate store, or None."""
    x = w[i]
    rn = (x >> 5) & 31
    imm = ((x >> 10) & 0xfff)
    for j in range(i - 1, max(i - 600, -1), -1):
        y = w[j]
        if y == 0xd65f03c0: return None                     # 函数尾 | end of function
        if not writes(y, rn): continue
        if is_adrp(y):                                      # 形态 A | form A
            return adrp(y, j * 4) + imm * 8, 'A'
        if is_ldr_u64(y) and (y & 31) == rn and ((y >> 5) & 31) == rn:   # 形态 B | form B
            page = adrp_page_for(rn, j)
            if page is None: return None
            return page + ((y >> 10) & 0xfff) * 8, 'B'
        if is_add_imm(y, rn) and ((y >> 5) & 31) == rn:
            page = adrp_page_for(rn, j)
            if page is None: return None
            return page + ((y >> 10) & 0xfff) + imm * 8, 'A+'
        return None
    return None

# 1) 候选：str x0,[xB]，其前面紧邻的 add x1 拼出 "nvn..." 字符串
cands = []
for i in range(N):
    x = w[i]
    if not is_str_x0(x): continue
    for j in range(i - 1, max(i - 12, -1), -1):
        y = w[j]
        if not is_add_imm(y, 1): continue
        rm = (y >> 5) & 31
        page = adrp_page_for(rm, j)
        if page is None: continue
        s = cstr(page + ((y >> 10) & 0xfff))
        if s and s.startswith('nvn'):
            cands.append((i, j, s))
        break

if not cands:
    sys.exit('没有找到 NVN 取址候选 | no NVN loader candidate found')

# 连续成簇（间隔 < 96 条指令），取最长的一簇
clusters, cur = [], [cands[0]]
for c in cands[1:]:
    if c[0] - cur[-1][0] < 96: cur.append(c)
    else: clusters.append(cur); cur = [c]
clusters.append(cur)
cluster = max(clusters, key=len)

# 2) 槽
slot, unresolved, forms = {}, 0, {}
for i, j, s in cluster:
    r = slot_of_store(i)
    if r is None:
        unresolved += 1; continue
    a, form = r
    slot[a] = s; forms[form] = forms.get(form, 0) + 1

# 3) 调用点。TotK 的调用点基址寄存器常来自内存加载（`ldr xN,[xM]`），静态拿不到页号，
#    所以先按「槽地址低 12 位」匹配；同一页内偏移唯一，跨页重名时按全部候选计（并在汇总里报出冲突数）。
#    能静态拿到页号（adrp）时按全地址精确匹配。
by_off = {}
for a in slot: by_off.setdefault(a & 0xfff, []).append(a)
collide = sum(1 for v in by_off.values() if len(v) > 1)
uses = {a: [] for a in slot}
for i in range(N):
    x = w[i]
    if x & 0xfc000000 != 0xf9400000: continue
    off = ((x >> 10) & 0xfff) * 8
    rn = (x >> 5) & 31
    if off not in by_off or rn == 31: continue
    page = None
    for j in range(i - 1, max(i - 4000, -1), -1):
        y = w[j]
        if y == 0xd65f03c0: break
        if writes(y, rn):
            if is_adrp(y): page = adrp(y, j * 4)
            break
    for a in by_off[off]:
        if page is None or (page + off) == a:
            uses[a].append(i * 4)

with open(out, 'w', encoding='utf-8') as f:
    f.write('# kind: evidence  main NVN 取址槽与静态调用点（nvn_slots_auto.py 自动定位加载函数）\nname\tslot\tnuses\tfirst_use\n')
    for a in sorted(slot):
        u = uses[a]; f.write('%s\t%x\t%d\t%s\n' % (slot[a], a, len(u), '%x' % u[0] if u else '-'))
if len(sys.argv) > 4: open(sys.argv[4], 'w', encoding='utf-8').write(''.join(slot[a] + '\n' for a in sorted(slot)))
used = sum(1 for a in slot if uses[a])
print('簇 %d 条（未解析槽 %d）；形态 %s；槽 %d，有调用点 %d，调用点 %d；偏移冲突 %d' % (len(cluster), unresolved, forms, len(slot), used, sum(len(v) for v in uses.values()), collide))
print('加载函数位置 0x%x' % (cluster[0][0] * 4))



