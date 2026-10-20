#!/usr/bin/env python3
"""Switch NCA 的读取与解包（纯 Python，Windows 友好）。

为什么自己写：上游 hactool 1.4.0（仓库里实测用的那个二进制）解不开 NCA3 的 BKTR 补丁段
（报 "Invalid BKTR layout!"，它的 bktr_superblock_t 布局早于 NCA3），而本机没有 WSL，
`dm/tools/extract_game.sh` 那条路走不了。本工具按 hactool 的算法重写一遍，只依赖 pycryptodome
（AES-ECB / AES-CTR），能读 NCA3 头、列 / 取 ExeFS 与 RomFS。

算法出处（照 hactool 1.4.0 的 nca.c / aes.c / pki.c）：
  · NCA3 的头与四个段头在文件开头 0xC00 字节里，用 prod.keys 里的 header_key 做 AES-XTS
    加密（每 0x200 一个 sector，tweak = sector 号的小端 16 字节；tweak 不乘 alpha，
    这跟 mbedtls 的实现一致，是任天堂的私有约定）。
  · 段头里的 section_ctr 拼出该段的 CTR：前 8 字节 = section_ctr 反序，后 8 字节 = 段起始
    偏移 >> 4 的小端 64 位；每读一个 16 字节块，整块（16 字节，按小端 128 位）加 1。
  · 段数据用 key area 的第 3 把密钥（decrypted_keys[2]）做 AES-CTR。key area（头里
    0x300 起的 0x40 字节）用 KAK 解密；KAK = generate_kek(master_key[rev],
    aes_kek_generation_source, aes_key_generation_source, key_area_key_application_source)，
    也就是三步 AES-ECB 解密。

本工具只读本机的游戏文件与密钥，不打印也不复制任何密钥内容。

Reads and unpacks Switch NCA files (pure Python, Windows friendly).
Why our own: upstream hactool 1.4.0 cannot open NCA3 BKTR patch sections
("Invalid BKTR layout!" -- its bktr superblock layout predates NCA3), and there is no WSL
on this machine, so the bash path in dm/tools/extract_game.sh is unavailable. This tool
reimplements hactool's algorithms on top of pycryptodome (AES-ECB / AES-CTR) and can read
the NCA3 header, list and extract ExeFS and RomFS.

The algorithms follow hactool 1.4.0 (nca.c / aes.c / pki.c):
  * The NCA3 header and the four section headers live in the first 0xC00 bytes and are
    AES-XTS encrypted with header_key from prod.keys (0x200 per sector, tweak = the sector
    number as a 16-byte little-endian value; the tweak is not multiplied by alpha, which is
    Nintendo's private convention and matches mbedtls).
  * The section CTR is built from section_ctr (first 8 bytes reversed) plus the section
    start offset >> 4 as a little-endian 64-bit value; every 16-byte block increments the
    whole 16-byte counter as a little-endian 128-bit integer.
  * Section data is AES-CTR with key area key 3 (decrypted_keys[2]). The key area (0x40
    bytes at 0x300 of the header) is decrypted with the KAK, which is
    generate_kek(master_key[rev], aes_kek_generation_source, aes_key_generation_source,
    key_area_key_application_source) -- three AES-ECB decryptions.

This tool only reads game files and keys on this machine; it never prints or copies key material.
"""
import argparse
import json
import os
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from Crypto.Cipher import AES

MEDIA = 0x200
NCA_HEADER_SIZE = 0xC00
FS_HEADER_SIZE = 0x200
MAGIC_NCA3 = 0x3341434E
MAGIC_PFS0 = 0x30534650
MAGIC_IVFC = 0x43465649
ROMFS_HEADER_SIZE = 0x50
PARTITION_ROMFS, PARTITION_PFS0 = 0, 1
FS_TYPE_PFS0, FS_TYPE_ROMFS = 2, 3
CRYPT_NONE, CRYPT_XTS, CRYPT_CTR, CRYPT_BKTR = 1, 2, 3, 4
CONTENT_TYPES = ('Program', 'Meta', 'Control', 'Manual', 'Data', 'PublicData')


def _gf128mul_x_ble(block: bytes) -> bytes:
    """GF(2^128) 乘 x（mbedtls_gf128mul_x_ble 的字节序：小端两字）。 | Multiply by x in GF(2^128) with mbedtls's little-endian word order."""
    a = int.from_bytes(block[0:8], 'little')
    b = int.from_bytes(block[8:16], 'little')
    ra = ((a << 1) & 0xFFFFFFFFFFFFFFFF) ^ (0x87 if (b >> 63) & 1 else 0)
    rb = ((a >> 63) | (b << 1)) & 0xFFFFFFFFFFFFFFFF
    return ra.to_bytes(8, 'little') + rb.to_bytes(8, 'little')


def xts_decrypt(data: bytes, key32: bytes, sector_size: int = 0x200) -> bytes:
    """AES-XTS 解密（tweak = sector 号的小端 16 字节，不乘 alpha）。 | AES-XTS decrypt (tweak = sector number, 16 bytes little endian, no alpha)."""
    if len(data) % sector_size:
        raise ValueError('XTS 长度必须是 sector 的整数倍')
    k1, k2 = key32[:16], key32[16:]
    ecb = AES.new(k2, AES.MODE_ECB)
    out = bytearray(len(data))
    for index, start in enumerate(range(0, len(data), sector_size)):
        tweak = index.to_bytes(16, 'big')   # hactool 的 get_tweak 把 sector 写进 tweak[15]..tweak[0]，即大端字节序 | hactool writes the sector into tweak[15..0], i.e. big-endian byte order
        mask = ecb.encrypt(tweak)
        block = data[start:start + sector_size]
        plain = bytearray(len(block))
        for off in range(0, len(block), 16):
            chunk = bytes(x ^ y for x, y in zip(block[off:off + 16], mask))
            plain[off:off + 16] = bytes(x ^ y for x, y in zip(AES.new(k1, AES.MODE_ECB).decrypt(chunk), mask))
            mask = _gf128mul_x_ble(mask)
        out[start:start + sector_size] = plain
    return bytes(out)


def ctr_decrypt(data: bytes, key: bytes, ctr: bytes) -> bytes:
    """AES-CTR 解密：整块 16 字节按大端 128 位递增（后 8 字节是段内偏移 >> 4 的大端 64 位）。 | AES-CTR decrypt: the whole 16-byte block is incremented as a big-endian 128-bit integer (the last 8 bytes hold the section offset >> 4, big endian)."""
    if not data:
        return b''
    blocks = (len(data) + 15) // 16
    low = int.from_bytes(ctr[8:16], 'big')
    counters = (np.arange(blocks, dtype=np.uint64) + np.uint64(low & 0xFFFFFFFFFFFFFFFF)).astype(np.uint64)
    table = np.empty((blocks, 16), dtype=np.uint8)
    table[:, 0:8] = np.frombuffer(ctr[0:8], dtype=np.uint8)
    table[:, 8:16] = counters.byteswap().view(np.uint8).reshape(blocks, 8)
    stream = AES.new(key, AES.MODE_ECB).encrypt(table.tobytes())
    plain = (np.frombuffer(data, dtype=np.uint8) ^ np.frombuffer(stream[:len(data)], dtype=np.uint8))
    return plain.tobytes()


def read_keys(path) -> dict:
    """读 prod.keys 形式��密钥文件（只取需要的名字，不打印内容）。 | Read a prod.keys style key file (only the names we need; never printed)."""
    wanted = {'header_key', 'aes_kek_generation_source', 'aes_key_generation_source',
              'key_area_key_application_source'}
    keys = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        if '=' not in line or line.strip().startswith('#'):
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip()
        if name in wanted:
            keys[name] = bytes.fromhex(value)
        elif name.startswith('master_key_'):
            keys[name] = bytes.fromhex(value)
    return keys


def derive_kak(keys: dict, master_revision: int) -> bytes:
    """推导 key area key（application 区）：三步 AES-ECB 解密（照 hactool 的 generate_kek）。 | Derive the application key area key: three AES-ECB decryptions (hactool's generate_kek)."""
    master = keys['master_key_%02x' % master_revision]
    kek = AES.new(master, AES.MODE_ECB).decrypt(keys['aes_kek_generation_source'])
    src_kek = AES.new(kek, AES.MODE_ECB).decrypt(keys['key_area_key_application_source'])
    return AES.new(src_kek, AES.MODE_ECB).decrypt(keys['aes_key_generation_source'])


class Nca:
    """一个 NCA 文件：头、段、段数据解密。 | One NCA file: header, sections, section decryption."""

    def __init__(self, path, keys: dict):
        self.path = Path(path)
        self.keys = keys
        self.file = open(self.path, 'rb')
        self._local = threading.local()   # 每线程一个句柄：共用一个句柄时 seek/read 会串台 | one handle per thread: a shared handle interleaves seek/read
        raw = self.file.read(NCA_HEADER_SIZE)
        if len(raw) < NCA_HEADER_SIZE:
            raise SystemExit('NCA 太小，读不出头：%s' % self.path)
        head = xts_decrypt(raw, keys['header_key'])
        if struct.unpack_from('<I', head, 0x200)[0] != MAGIC_NCA3:
            raise SystemExit('不是 NCA3（或 header_key 不对）：%s' % self.path)
        self.head = head
        self.magic = MAGIC_NCA3
        self.content_type = head[0x205]
        self.crypto_type = head[0x206]
        self.kaek_ind = head[0x207]
        self.title_id = struct.unpack_from('<Q', head, 0x210)[0]
        self.crypto_type2 = head[0x220]
        self.master_revision = max(self.crypto_type, self.crypto_type2) - 1
        self.sections = []
        for index in range(4):
            start, end = struct.unpack_from('<II', head, 0x240 + index * 0x10)
            if not start:
                continue
            fs = head[0x400 + index * FS_HEADER_SIZE: 0x400 + (index + 1) * FS_HEADER_SIZE]
            self.sections.append({
                'index': index,
                'offset': start * MEDIA,
                'size': (end - start) * MEDIA,
                'partition_type': fs[0x02],
                'fs_type': fs[0x03],
                'crypt_type': fs[0x04],
                'section_ctr': fs[0x140:0x148],
                'fs_header': fs,
            })
        kak = derive_kak(keys, self.master_revision)
        self.kak = kak
        self.key_area = AES.new(kak, AES.MODE_ECB).decrypt(head[0x300:0x340])
        self.content_key = self.key_area[0x20:0x30]

    def handle(self):
        """当前线程的读句柄（每个线程一个，避免 seek/read 互相串台）。 | The reading handle of the current thread (one per thread, so seek/read do not interleave)."""
        handle = getattr(self._local, 'handle', None)
        if handle is None:
            handle = open(self.path, 'rb')
            self._local.handle = handle
        return handle

    def close(self):
        self.file.close()

    def describe(self) -> dict:
        out = {
            'path': str(self.path),
            'title_id': '%016x' % self.title_id,
            'content_type': CONTENT_TYPES[self.content_type] if self.content_type < len(CONTENT_TYPES) else str(self.content_type),
            'master_key_revision': '0x%x' % self.master_revision,
            'size': self.path.stat().st_size,
            'sections': [],
        }
        for section in self.sections:
            fs = section['fs_header']
            kind = {CRYPT_NONE: 'none', CRYPT_XTS: 'xts', CRYPT_CTR: 'ctr', CRYPT_BKTR: 'bktr'}.get(section['crypt_type'], str(section['crypt_type']))
            part = {PARTITION_ROMFS: 'romfs', PARTITION_PFS0: 'pfs0'}.get(section['partition_type'], str(section['partition_type']))
            entry = {'index': section['index'], 'offset': section['offset'], 'size': section['size'],
                     'partition': part, 'fs_type': section['fs_type'], 'crypt': kind}
            if section['partition_type'] == PARTITION_ROMFS and section['fs_type'] == FS_TYPE_ROMFS:
                entry['ivfc_levels'] = self._ivfc_levels(fs)
            out['sections'].append(entry)
        return out

    @staticmethod
    def _ivfc_levels(fs: bytes) -> list:
        num_levels = struct.unpack_from('<I', fs, 0x08 + 0x0C)[0]
        levels = []
        for index in range(min(num_levels, 6)):
            logical, hash_size, block, _ = struct.unpack_from('<QQII', fs, 0x08 + 0x10 + index * 0x18)
            levels.append({'data_offset': logical, 'data_size': hash_size, 'hash_block_size': 1 << block})
        return levels

    def read_section(self, section: dict, offset: int, size: int) -> bytes:
        """读段内 [offset, offset+size) 的解密后数据。 | Read decrypted bytes of [offset, offset+size) inside a section."""
        if section['crypt_type'] != CRYPT_CTR:
            raise SystemExit('本工具目前只支持 CTR 加密的段（这一段是 %s）' % section['crypt_type'])
        absolute = section['offset'] + offset
        aligned = absolute & ~0xF
        skip = absolute - aligned
        handle = self.handle()
        handle.seek(aligned)
        raw = handle.read(size + skip)
        if len(raw) < size + skip:
            raise SystemExit('读段数据不够（%d < %d）：%s' % (len(raw), size + skip, self.path))
        ctr = bytearray(16)
        for index in range(8):
            ctr[index] = section['section_ctr'][7 - index]
        ctr[8:16] = (aligned >> 4).to_bytes(8, 'big')
        plain = ctr_decrypt(raw, self.content_key, bytes(ctr))
        return plain[skip:skip + size]

    def pfs0(self, section: dict) -> bytes:
        """取段里的 PFS0（ExeFS 就是 PFS0）。 | Get the PFS0 blob of a section (ExeFS is a PFS0)."""
        fs = section['fs_header']
        offset, size = struct.unpack_from('<QQ', fs, 0x08 + 0x38)
        return self.read_section(section, offset, size)

    def romfs(self, section: dict):
        """取段里的 RomFS：返回 (romfs 数据在段内的偏移, RomFS 头字典, 目录表, 文件表)。 | Get RomFS of a section: (offset in section, header, dir table, file table)."""
        fs = section['fs_header']
        levels = self._ivfc_levels(fs)
        if not levels:
            raise SystemExit('这一段没有 IVFC 头')
        base = levels[-1]['data_offset']
        header = self.read_section(section, base, ROMFS_HEADER_SIZE)
        fields = struct.unpack_from('<10Q', header, 0)
        names = ['header_size', 'dir_hash_table_offset', 'dir_hash_table_size', 'dir_meta_table_offset',
                 'dir_meta_table_size', 'file_hash_table_offset', 'file_hash_table_size',
                 'file_meta_table_offset', 'file_meta_table_size', 'data_offset']
        head = dict(zip(names, fields))
        dirs = self.read_section(section, base + head['dir_meta_table_offset'], head['dir_meta_table_size'])
        files = self.read_section(section, base + head['file_meta_table_offset'], head['file_meta_table_size'])
        return base, head, dirs, files


def pfs0_entries(blob: bytes) -> list:
    """解析 PFS0：返回 [(名字, 数据偏移, 大小)]。 | Parse a PFS0: [(name, data offset, size)]."""
    magic, num_files, string_size, _ = struct.unpack_from('<4I', blob, 0)
    if magic != MAGIC_PFS0:
        raise SystemExit('不是 PFS0（magic %08x）' % magic)
    entries = []
    for index in range(num_files):
        offset, size, name_offset, _ = struct.unpack_from('<QQII', blob, 0x10 + index * 0x18)
        end = blob.index(b'\0', 0x10 + num_files * 0x18 + name_offset)
        name = blob[0x10 + num_files * 0x18 + name_offset:end].decode('utf-8', 'replace')
        entries.append((name, offset, size))
    data_start = 0x10 + num_files * 0x18 + string_size
    return [(name, data_start + offset, size) for name, offset, size in entries]


def romfs_entries(base: int, head: dict, dirs: bytes, files: bytes) -> list:
    """解析 RomFS 目录树：返回 [(路径, 文件在 RomFS 里的偏移, 大小)]。 | Walk the RomFS tree: [(path, offset in RomFS, size)]."""
    data_offset = base + head['data_offset']

    def dir_entry(offset):
        parent, sibling, child, file, _hash, name_size = struct.unpack_from('<6I', dirs, offset)
        name = dirs[offset + 24: offset + 24 + name_size].split(b'\0')[0].decode('utf-8', 'replace')
        return parent, sibling, child, file, name

    def file_entry(offset):
        parent, sibling, data_off, size, _hash, name_size = struct.unpack_from('<IIQQII', files, offset)
        name = files[offset + 32: offset + 32 + name_size].split(b'\0')[0].decode('utf-8', 'replace')
        return data_off, size, name

    out = []
    stack = [dir_entry(0)]
    while stack:
        parent, sibling, child, file, name = stack.pop()
        prefix = '' if name == '' else name + '/'
        # 文件
        entry = file
        while entry != 0xFFFFFFFF:
            data_off, size, fname = file_entry(entry)
            out.append((prefix + fname, data_offset + data_off, size))
            entry = struct.unpack_from('<I', files, entry + 4)[0]
        # 子目录
        child_entry = child
        while child_entry != 0xFFFFFFFF:
            stack.append(dir_entry(child_entry))
            child_entry = struct.unpack_from('<I', dirs, child_entry + 4)[0]   # 兄弟目录在 +4（+8 是子目录） | the sibling directory is at +4 (+8 is the child)
    return out


def cmd_info(args):
    nca = Nca(args.nca, read_keys(args.prod_keys))
    print(json.dumps(nca.describe(), indent=2, ensure_ascii=False))
    nca.close()


def cmd_exefs(args):
    nca = Nca(args.nca, read_keys(args.prod_keys))
    section = nca.sections[0]
    blob = nca.pfs0(section)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, offset, size in pfs0_entries(blob):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = blob[offset:offset + size]
        target.write_bytes(data)
        total += size
        print('%s  %d 字节' % (name, size))
    print('ExeFS 共 %d 个文件，%d 字节 -> %s' % (len(pfs0_entries(blob)), total, out))
    nca.close()


def cmd_romfs_list(args):
    nca = Nca(args.nca, read_keys(args.prod_keys))
    section = [s for s in nca.sections if s['partition_type'] == PARTITION_ROMFS and s['fs_type'] == FS_TYPE_ROMFS][0]
    base, head, dirs, files = nca.romfs(section)
    entries = romfs_entries(base, head, dirs, files)
    total = sum(size for _, _, size in entries)
    print('RomFS：%d 个文件，%d 字节（%.2f GB）' % (len(entries), total, total / 1024 / 1024 / 1024))
    for path, offset, size in entries:
        if args.filter and args.filter.lower() not in path.lower():
            continue
        print('%12d  %s' % (size, path))
    nca.close()


def cmd_romfs_export(args):
    """把 RomFS 段**解密后**导出成一个整文件：宿主或手机端不必再解 30 多万个小文件。

    TotK 的 RomFS 是一棵深目录树（304,207 个文件）。逐个取出再逐个推给手机既慢又占地方；
    直接导出解密后的整段（RomFS 映像），由读取器按路径取文件即可。

    Export the decrypted RomFS section as one file: the host (or the phone) then reads files
    by path instead of dealing with more than 300k separate files.
    """
    nca = Nca(args.nca, read_keys(args.prod_keys))
    section = [s for s in nca.sections if s['partition_type'] == PARTITION_ROMFS and s['fs_type'] == FS_TYPE_ROMFS][0]
    if section['crypt_type'] != CRYPT_CTR:
        raise SystemExit('这一段不是 CTR 加密的（%s），导不出来' % section['crypt_type'])
    base, head, dirs, files = nca.romfs(section)
    total = section['size']
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # IVFC 头本身在 NCA 的头区（不在段数据里），所以映像旁边要另存一份，读取方才知道
    # 去哪里找 RomFS 头与各级偏移。
    # The IVFC header lives in the NCA header, not in the section data, so it is written next to the image:
    # without it a reader cannot find the RomFS header or the level offsets.
    (out.with_suffix(out.suffix + ".ivfc")).write_bytes(section['fs_header'])
    written = 0
    with out.open('wb') as target:
        while written < total:
            size = min(1 << 26, total - written)
            target.write(nca.read_section(section, written, size))
            written += size
            if written % (1 << 28) < size:
                print('  已导出 %.2f / %.2f GiB' % (written / 2**30, total / 2**30), flush=True)
    print('已导出 %s（%.2f GiB，%d 个文件）' % (out, total / 2**30, len(romfs_entries(base, head, dirs, files))))


def cmd_romfs_extract(args):
    nca = Nca(args.nca, read_keys(args.prod_keys))
    section = [s for s in nca.sections if s['partition_type'] == PARTITION_ROMFS and s['fs_type'] == FS_TYPE_ROMFS][0]
    base, head, dirs, files = nca.romfs(section)
    entries = romfs_entries(base, head, dirs, files)
    if args.filter:
        entries = [e for e in entries if args.filter.lower() in e[0].lower()]
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    done = [0]

    def pull(entry):
        path, offset, size = entry
        target = out / path
        if target.exists() and target.stat().st_size == size:
            done[0] += 1          # 断点续传：已取过的（大小一致）跳过 | resume: skip files already extracted (same size)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        data = nca.read_section(section, offset, size)
        target.write_bytes(data)
        done[0] += 1
        if done[0] % 5000 == 0:
            print('  已取 %d / %d' % (done[0], len(entries)), flush=True)

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(pull, entries))
    print('取完 %d 个文件 -> %s' % (done[0], out))
    nca.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--prod-keys', required=True, help='prod.keys 路径（只在本机读） | path to prod.keys (read locally only)')
    sub = parser.add_subparsers(dest='command', required=True)
    info = sub.add_parser('info', help='打印 NCA 头信息 | print NCA header info')
    info.add_argument('nca')
    info.set_defaults(func=cmd_info)
    exefs = sub.add_parser('exefs', help='取出 ExeFS | extract the ExeFS')
    exefs.add_argument('nca')
    exefs.add_argument('--outdir', required=True)
    exefs.set_defaults(func=cmd_exefs)
    rlist = sub.add_parser('romfs-list', help='列出 RomFS 文件 | list RomFS files')
    rlist.add_argument('nca')
    rlist.add_argument('--filter', default=None)
    rlist.set_defaults(func=cmd_romfs_list)
    rext = sub.add_parser('romfs-extract', help='取出 RomFS 文件 | extract RomFS files')
    rext.add_argument('nca')
    rext.add_argument('--outdir', required=True)
    rext.add_argument('--filter', default=None)
    rext.add_argument('--jobs', type=int, default=8)
    rext.set_defaults(func=cmd_romfs_extract)
    rexp = sub.add_parser('romfs-export', help='把解密后的 RomFS 段导出成一个整文件 | export the decrypted RomFS section as one file')
    rexp.add_argument('nca')
    rexp.add_argument('--out', required=True)
    rexp.set_defaults(func=cmd_romfs_export)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
