#!/usr/bin/env python3
"""NSO 模块的统计（构建号、段大小、动态符号数、重定位数、导入数、依赖库）。

M0 勘察要用：计划 §3 的表要填「动态符号 / 重定位」与「模块数 / 大小」这几格
（D2R 的参考值是 38,837 符号 / 116,034 重定位）。

做法（与仓库里 dm/tools/patch_nso.py、dm/tools/sdis.py 同一套）：
  · 按 NSO 头里的段表把三段（text / rodata / data，LZ4 压缩）解压成一张平铺映像；
  · 映像开头是 MOD0 头（Switch 把 ELF 头换成了 MOD0），里面给出动态表的位置；
  · 动态表（Elf64_Dyn）里读 DT_HASH（nchain = 符号数）、DT_RELASZ / DT_PLTRELSZ
    （重定位数）、DT_SYMTAB 里 st_shndx == 0 的条数（导入数）、DT_NEEDED（依赖库）。

本工具只读本机的游戏文件，不打印也不复制任何密钥或游戏内容。

Statistics of an NSO module (build id, segment sizes, dynamic symbol count, relocation count,
imports, needed libraries).
M0 survey: the plan's §3 table needs the "dynamic symbols / relocations" and "module count / size"
rows (D2R's reference numbers are 38,837 symbols / 116,034 relocations).

Method (same as dm/tools/patch_nso.py and dm/tools/sdis.py in this repository):
  * decompress the three segments (text / rodata / data, LZ4) into one flat image using the
    segment table in the NSO header;
  * the image starts with a MOD0 header (Switch replaced the ELF header with it) that points at
    the dynamic table;
  * from the dynamic table read DT_HASH (nchain = symbol count), DT_RELASZ / DT_PLTRELSZ
    (relocations), the number of DT_SYMTAB entries with st_shndx == 0 (imports) and DT_NEEDED.

This tool only reads game files on this machine; it never prints or copies key material or game content.
"""
import struct
import sys

import lz4.block

DT_NULL, DT_NEEDED, DT_HASH, DT_STRTAB, DT_SYMTAB = 0, 1, 4, 5, 6
DT_RELA, DT_RELASZ, DT_PLTRELSZ, DT_PLTREL, DT_JMPREL = 7, 8, 2, 20, 23
DT_GNU_HASH, DT_STRSZ, DT_SYMENT = 0x6FFFFEF5, 10, 11


def load_nso(path):
    """读 NSO：返回 (平铺映像, 三段大小, 构建号)。 | Read an NSO: (flat image, segment sizes, build id)."""
    data = open(path, 'rb').read()
    flags = struct.unpack_from('<I', data, 0xC)[0]
    segs = [struct.unpack_from('<III', data, 0x10 + i * 0x10) for i in range(3)]
    bss = struct.unpack_from('<I', data, 0x3C)[0]
    build = data[0x40:0x50].hex()
    compressed = [struct.unpack_from('<I', data, 0x60 + i * 4)[0] for i in range(3)]
    end = max(mem_off + size for _, mem_off, size in segs)   # 映像按虚拟地址铺（text 在 0，ro / data 各自 mem_off） | the image is laid out by virtual address
    image = bytearray(end + bss)
    for index, (file_off, mem_off, size) in enumerate(segs):
        raw = data[file_off:file_off + compressed[index]]
        if (flags >> index) & 1:
            raw = lz4.block.decompress(raw, uncompressed_size=size)
        image[mem_off:mem_off + size] = raw
    return bytes(image), [s for _, _, s in segs], build


def dynamic(flat):
    """按 MOD0 头找动态表，返回 {tag: value}。 | Find the dynamic table via the MOD0 header."""
    mod0 = struct.unpack_from('<I', flat, 4)[0]
    if flat[mod0:mod0 + 4] != b'MOD0':
        raise SystemExit('映像里没有 MOD0 头')
    dyn = mod0 + struct.unpack_from('<i', flat, mod0 + 4)[0]
    table = {}
    offset = dyn
    while offset + 16 <= len(flat):
        tag, value = struct.unpack_from('<qQ', flat, offset)
        offset += 16
        if tag == DT_NULL:
            break
        table.setdefault(tag, value)
    return table, mod0


def gnu_hash_symbols(flat, base):
    """GNU_HASH 里的符号数：沿每个桶的链走到末尾（链尾标志是 hash 值的最低位）。 | Symbol count from GNU_HASH: walk each bucket's chain to its end (the chain terminator is the low bit of the hash value)."""
    nbuckets, symoffset, bloom_size, _shift = struct.unpack_from('<IIII', flat, base)
    buckets_at = base + 16 + bloom_size * 8
    chain_at = buckets_at + 4 * nbuckets
    last = symoffset
    for index in range(nbuckets):
        start = struct.unpack_from('<I', flat, buckets_at + 4 * index)[0]
        if start < symoffset:
            continue
        cursor = start
        while True:
            value = struct.unpack_from('<I', flat, chain_at + 4 * (cursor - symoffset))[0]
            if value & 1:
                break
            cursor += 1
        last = max(last, cursor + 1)
    return last


def stats(path):
    flat, segs, build = load_nso(path)
    table, mod0 = dynamic(flat)
    symbols = 0
    if DT_HASH in table:
        symbols = struct.unpack_from('<I', flat, table[DT_HASH] + 4)[0]   # nchain = 符号数 | nchain = symbol count
    elif DT_GNU_HASH in table:
        symbols = gnu_hash_symbols(flat, table[DT_GNU_HASH])
    rela = table.get(DT_RELASZ, 0) // 24
    jmprel = table.get(DT_PLTRELSZ, 0) // 24
    imports = 0
    if DT_SYMTAB in table and symbols:
        symtab = table[DT_SYMTAB]
        limit = min(symbols, max(0, (len(flat) - symtab) // 24))
        for index in range(limit):
            if struct.unpack_from('<H', flat, symtab + index * 24 + 6)[0] == 0:
                imports += 1
    needed = [value for tag, value in table.items() if tag == DT_NEEDED]
    return {
        'path': str(path),
        'build_id': build,
        'text': segs[0], 'rodata': segs[1], 'data': segs[2],
        'image_bytes': len(flat),
        'dynamic_symbols': symbols,
        'relocations': rela + jmprel,
        'rela': rela,
        'jmprel': jmprel,
        'imports': imports,
        'needed': len(needed),
    }


def main():
    total = {'dynamic_symbols': 0, 'relocations': 0, 'imports': 0}
    for path in sys.argv[1:]:
        info = stats(path)
        print('== %s' % info['path'])
        print('  build_id          %s' % info['build_id'])
        print('  text/ro/data      %d / %d / %d 字节（映像 %d）' % (info['text'], info['rodata'], info['data'], info['image_bytes']))
        print('  动态符号          %d（其中未定义 = 导入 %d）' % (info['dynamic_symbols'], info['imports']))
        print('  重定位            %d（RELA %d + PLT %d）' % (info['relocations'], info['rela'], info['jmprel']))
        print('  NEEDED 库         %d 个' % info['needed'])
        for key in total:
            total[key] += info[key]
    if len(sys.argv) > 2:
        print('== 合计：动态符号 %d / 重定位 %d / 导入 %d' % (total['dynamic_symbols'], total['relocations'], total['imports']))


if __name__ == '__main__':
    main()
