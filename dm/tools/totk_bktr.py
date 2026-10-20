#!/usr/bin/env python3
"""读出更新包 RomFS 段（crypt: bktr）的物理布局，并核对 NCA3 的元数据块。

为什么自己写：上游 hactool 1.4.0 的 BKTR 校验早于 NCA3，对本标题报 "Invalid BKTR layout!"；
本机网络只通 github.com 的 git 通路，取不到 hactool 源码。本工具按**实测**出来的布局自己实现：
段数据用与其它段相同的 AES-CTR 解密（content key + 段 CTR），BKTR 的两个头在 NCA 头的 fs_header 里，
NCA3 的元数据块在 fs_header 的 0x1A0/0x1A8/0x1B0。

用法：
  python dm/tools/totk_bktr.py <更新包里的 .nca> [--keys <prod.keys>] [--json]

只读：本工具不写任何文件，也不打印密钥内容。
Read-only: this tool writes nothing and never prints key material.

用法 / Usage:
  python dm/tools/totk_bktr.py <update .nca> [--keys <prod.keys>] [--json]
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import switch_nca as S

# fs_header 里的 BKTR 超块布局（实测）：
#   +0x100 u64 relocation_offset, +0x108 u64 relocation_size, +0x110 'BKTR', +0x114 版本
#   +0x118 u64 relocation 块的总长, +0x120 u64 subsection_offset, +0x128 u64 subsection_size,
#   +0x130 'BKTR', +0x134 版本, +0x138 u64 subsection 块的总长, +0x140 两个 u32
#   +0x1A0 u64 元数据块偏移（段内）, +0x1A8 u64 元数据块长度, +0x1B0 32 字节 sha256
FS_SUPERBLOCK = 0x100
FS_METADATA_OFFSET = 0x1A0
FS_METADATA_SIZE = 0x1A8
FS_METADATA_HASH = 0x1B0
MAGIC_BKTR = 0x52544B42   # 'BKTR' 按小端读出来的值
IVFC_MAGIC = 0x43465649
IVFC_MAX_LEVEL = 7


def bktr_superblock(fs: bytes) -> dict:
    """从 fs_header 里读出 BKTR 的两个头与元数据块的位置。 | Read the two BKTR headers and the metadata placement out of the fs_header."""
    relocation = {
        'offset': struct.unpack_from('<Q', fs, FS_SUPERBLOCK)[0],
        'size': struct.unpack_from('<Q', fs, FS_SUPERBLOCK + 0x08)[0],
        'magic': struct.unpack_from('<I', fs, FS_SUPERBLOCK + 0x10)[0],
        'version': struct.unpack_from('<I', fs, FS_SUPERBLOCK + 0x14)[0],
        'block_total_size': struct.unpack_from('<Q', fs, FS_SUPERBLOCK + 0x18)[0],
    }
    subsection = {
        'offset': struct.unpack_from('<Q', fs, FS_SUPERBLOCK + 0x20)[0],
        'size': struct.unpack_from('<Q', fs, FS_SUPERBLOCK + 0x28)[0],
        'magic': struct.unpack_from('<I', fs, FS_SUPERBLOCK + 0x30)[0],
        'version': struct.unpack_from('<I', fs, FS_SUPERBLOCK + 0x34)[0],
        'block_total_size': struct.unpack_from('<Q', fs, FS_SUPERBLOCK + 0x38)[0],
    }
    return {
        'relocation': relocation,
        'subsection': subsection,
        'counters': list(struct.unpack_from('<II', fs, FS_SUPERBLOCK + 0x40)),
        'metadata_offset': struct.unpack_from('<Q', fs, FS_METADATA_OFFSET)[0],
        'metadata_size': struct.unpack_from('<Q', fs, FS_METADATA_SIZE)[0],
        'metadata_hash': fs[FS_METADATA_HASH:FS_METADATA_HASH + 0x20].hex(),
    }


def read_plain(nca: S.Nca, section: dict, rel: int, count: int) -> bytes:
    """读段内 [rel, rel+count) 的解密后数据。

    BKTR 段的数据用与其它段相同的 AES-CTR（content key + 段 CTR）解密 —— 实测：这样解出来的
    元数据块是一个合法的 IVFC 头（magic / id / master_hash_size 都对），随机密钥不可能凑巧。

    Read the decrypted bytes of [rel, rel+count) inside the section. The BKTR section's data uses
    the same AES-CTR (content key + section CTR) as every other section: the metadata block then
    decodes into a well-formed IVFC header, which no wrong key would produce.
    """
    absolute = section['offset'] + rel
    aligned = absolute & ~0xF
    skip = absolute - aligned
    ctr = bytearray(16)
    for index in range(8):
        ctr[index] = section['section_ctr'][7 - index]
    ctr[8:16] = (aligned >> 4).to_bytes(8, 'big')
    nca.file.seek(aligned)
    raw = nca.file.read(count + skip)
    if len(raw) < count + skip:
        raise SystemExit('读段数据不够（%d < %d）' % (len(raw), count + skip))
    return S.ctr_decrypt(raw, nca.content_key, bytes(ctr))[skip:skip + count]


def parse_ivfc(blob: bytes) -> dict:
    """解析 IVFC 头（magic / id / master_hash_size / num_levels / 各层）。 | Parse an IVFC header."""
    if len(blob) < 0x10:
        raise SystemExit('IVFC 头太短')
    magic, ident = struct.unpack_from('<II', blob, 0)
    master_hash_size, num_levels = struct.unpack_from('<II', blob, 8)
    levels = []
    for index in range(min(num_levels, IVFC_MAX_LEVEL)):
        logical, hash_size, block, sparse = struct.unpack_from('<QQII', blob, 0x10 + index * 0x18)
        levels.append({'logical_offset': logical, 'hash_data_size': hash_size,
                       'block_size_log2': block, 'sparse': sparse})
    return {'magic': magic, 'id': ident, 'master_hash_size': master_hash_size,
            'num_levels': num_levels, 'levels': levels}


def scan_payload(nca: S.Nca, section: dict, romfs: Path, limit: int = 4) -> list:
    """扫载荷里的 zstd 帧，按帧头写的字典 id 解开，并报出解出来的是什么。

    The payload's frames name their dictionary in the frame header; the dictionaries live in the
    game's own /Pack/ZsDic.pack.zs (ids 1/2/3). Decoded frames turn out to be SARC archives --
    the game's pack archives -- so this reports how many frames there are and what they hold.
    """
    import zstandard
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import switch_shaders as SS
    pack = romfs / 'Pack' / 'ZsDic.pack.zs'
    if not pack.is_file():
        raise SystemExit('缺少 zstd 字典包：%s' % pack)
    dictionaries = SS.load_dictionaries(pack.read_bytes())
    payload_end = struct.unpack_from('<Q', section['fs_header'], 0x100)[0]
    frames = []
    offset = 0
    tail = b''
    while offset < payload_end:
        chunk = read_plain(nca, section, offset, min(1 << 24, payload_end - offset))
        if chunk is None:
            break
        buffer = tail + chunk
        base = offset - len(tail)
        at = buffer.find(b'\x28\xb5\x2f\xfd')
        while at >= 0:
            frames.append(base + at)
            at = buffer.find(b'\x28\xb5\x2f\xfd', at + 1)
        tail = buffer[-8:]
        offset += len(chunk)
    out = []
    for position in frames[:limit]:
        data = read_plain(nca, section, position, 1 << 23)
        try:
            parameters = zstandard.get_frame_parameters(data)
            dict_id = parameters.dict_id
            content = parameters.content_size
        except Exception as error:
            out.append({'offset': position, 'error': str(error)[:60]})
            continue
        record = {'offset': position, 'dict_id': dict_id, 'content_size': content}
        failure = '没有匹配的字典'
        for key in list(dictionaries) + [None]:
            try:
                plain = zstandard.ZstdDecompressor(dict_data=dictionaries.get(key)).decompress(
                    data, max_output_size=1 << 26)
            except Exception as error:
                failure = str(error)[:70]
                continue
            record['dictionary'] = key
            if plain[:4] == b'SARC':
                entries = SS.sarc_entries(plain)
                record['kind'] = 'SARC'
                record['entries'] = len(entries)
                record['first_entries'] = list(entries)[:3]
            else:
                record['kind'] = 'plain'
                record['head'] = plain[:16].hex(' ')
            break
        else:
            record['kind'] = 'undecoded'
            record['error'] = failure
        out.append(record)
    return [{'frame_count': len(frames), 'frames': out}]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('nca', type=Path, help='更新包里的 .nca 文件 | the update .nca file')
    parser.add_argument('--keys', type=Path, help='prod.keys | the key file')
    parser.add_argument('--json', action='store_true', help='输出 JSON | print JSON')
    parser.add_argument('--romfs', type=Path,
                        help='本体 RomFS 目录（要带 Pack/ZsDic.pack.zs）：用来读 zstd 字典并扫载荷 | the base RomFS directory (must hold Pack/ZsDic.pack.zs)')
    args = parser.parse_args()

    if not args.keys:
        raise SystemExit('需要 --keys（密钥不回显，本工具只用到它算内容密钥）')
    keys = S.read_keys(str(args.keys))
    nca = S.Nca(str(args.nca), keys)
    sections = [s for s in nca.sections if s['partition_type'] == S.PARTITION_ROMFS]
    if len(sections) != 1:
        raise SystemExit('这一段没有唯一的 RomFS 段（找到 %d 个）' % len(sections))
    section = sections[0]
    if section['crypt_type'] != S.CRYPT_BKTR:
        raise SystemExit('这一段不是 BKTR（crypt=%d）' % section['crypt_type'])

    superblock = bktr_superblock(section['fs_header'])
    meta_offset = superblock['metadata_offset']
    meta_size = superblock['metadata_size']
    metadata = read_plain(nca, section, meta_offset, meta_size)
    digest = hashlib.sha256(metadata).hexdigest()
    hash_ok = digest == superblock['metadata_hash']

    layer_offset = struct.unpack_from('<Q', metadata, 0)[0]
    ivfc = parse_ivfc(metadata[8:])
    ivfc_ok = ivfc['magic'] == IVFC_MAGIC and ivfc['id'] == 0x20000 and ivfc['master_hash_size'] == 0x20

    relocation, subsection = superblock['relocation'], superblock['subsection']
    layout = {
        'title_id': '%016x' % nca.title_id,
        'master_key_revision': '0x%x' % nca.master_revision,
        'section_size': section['size'],
        'superblock': superblock,
        'metadata': {'offset': meta_offset, 'size': meta_size, 'sha256': digest,
                     'hash_matches_header': hash_ok, 'layer_offset': layer_offset, 'ivfc': ivfc},
        'regions': [
            {'name': '补丁数据（被下一段覆盖）', 'offset': 0, 'size': relocation['offset']},
            {'name': '重定位/校验表', 'offset': relocation['offset'], 'size': relocation['size']},
            {'name': 'hash 层 1', 'offset': subsection['offset'], 'size': subsection['size']},
            {'name': 'hash 层 0（主哈希）', 'offset': layer_offset, 'size': 0x4000},
            {'name': '元数据块', 'offset': meta_offset, 'size': meta_size},
        ],
    }
    # 布局自洽性：两个头必须首尾相接，元数据块必须在段的末尾之前。
    layout['consistent'] = bool(
        relocation['offset'] + relocation['size'] == subsection['offset']
        and subsection['offset'] + subsection['size'] == layer_offset
        and meta_offset + meta_size <= section['size']
        and hash_ok and ivfc_ok)

    # 重定位表：只把已知的事实打出来（每页头里的计数值与前几行十六进制），
    # 语义还没解出来 —— 下一轮接着解，别再从头猜。
    # The relocation table: print only the facts we know (the count in each page header and the
    # leading bytes). Its semantics are still unknown; the next round continues from here.
    relocation_start = superblock['relocation']['offset']
    relocation_head = read_plain(nca, section, relocation_start, 0x40)
    relocation_counts = []
    for page in range((superblock['relocation']['size'] + 0x3FFF) // 0x4000):
        head = read_plain(nca, section, relocation_start + page * 0x4000, 8)
        relocation_counts.append(struct.unpack_from('<I', head, 4)[0])
    # 首页那 4 条不是记录（是页头），所以真正的条目数是后面几页的计数之和：
    # 818 + 818 + 818 + 204 = 2,658，与 fs_header 里那个块总长 0xA62 = 2,658 一致 → 交叉印证。
    # The first page's 4 entries are page-header material, not records, so the real count is the
    # sum of the later pages: 818 + 818 + 818 + 204 = 2,658 -- which matches the block total size
    # 0xA62 = 2,658 in the fs_header, so the two agree.
    record_count = sum(relocation_counts[1:])
    layout['relocation'] = {'offset': relocation_start, 'size': superblock['relocation']['size'],
                             'page_counts': relocation_counts, 'record_count': record_count,
                             'fs_header_total': superblock['relocation']['block_total_size'],
                             'head': relocation_head.hex(' ')}

    if args.romfs:
        layout['payload'] = scan_payload(nca, section, args.romfs)
    if args.json:
        print(json.dumps(layout, ensure_ascii=False, indent=2))
    else:
        print('标题 %s  主密钥修订 %s  段 %d 字节' % (layout['title_id'], layout['master_key_revision'], section['size']))
        print('重定位头：偏移 0x%x 长度 0x%x magic %s 版本 %d 块总长 0x%x' % (
            relocation['offset'], relocation['size'],
            'BKTR' if relocation['magic'] == MAGIC_BKTR else hex(relocation['magic']),
            relocation['version'], relocation['block_total_size']))
        print('子段头  ：偏移 0x%x 长度 0x%x magic %s 版本 %d 块总长 0x%x' % (
            subsection['offset'], subsection['size'],
            'BKTR' if subsection['magic'] == MAGIC_BKTR else hex(subsection['magic']),
            subsection['version'], subsection['block_total_size']))
        print('计数    ：%s' % (superblock['counters'],))
        print('元数据块：偏移 0x%x 长度 %d  sha256 %s  与头里的哈希一致=%s' % (
            meta_offset, meta_size, digest, hash_ok))
        print('  layer_offset = 0x%x' % layer_offset)
        print('  IVFC magic=%08x id=0x%x master_hash_size=%d num_levels=%d 合法=%s' % (
            ivfc['magic'], ivfc['id'], ivfc['master_hash_size'], ivfc['num_levels'], ivfc_ok))
        for index, level in enumerate(ivfc['levels']):
            print('    层 %d：logical=0x%x hash_data_size=0x%x block=%d' % (
                index, level['logical_offset'], level['hash_data_size'], level['block_size_log2']))
        print('物理分区：')
        for region in layout['regions']:
            print('  0x%08x .. 0x%08x  %-22s %d 字节' % (
                region['offset'], region['offset'] + region['size'], region['name'], region['size']))
        print('重定位表 @0x%x 长度 0x%x：每 16 KB 一页，各页头里的计数 %s' % (
            relocation_start, superblock['relocation']['size'], relocation_counts[:12]))
        print('  条目数 %d（首页那 4 条是页头，不算记录）；fs_header 里写的块总长 %d（0x%X）'
              % (record_count, superblock['relocation']['block_total_size'],
                 superblock['relocation']['block_total_size']))
        print('  首页前 0x40 字节：%s' % relocation_head.hex(' '))
        if 'payload' in layout:
            payload = layout['payload'][0]
            print('载荷里的 zstd 帧：%d 个' % payload['frame_count'])
            for record in payload['frames']:
                if 'error' in record:
                    print('  0x%08x  帧头解析失败：%s' % (record['offset'], record['error']))
                    continue
                if record.get('kind') == 'undecoded':
                    print('  0x%08x  字典 id=%s 内容 %s → 解不开：%s' % (
                        record['offset'], record['dict_id'], record['content_size'], record.get('error')))
                    continue
                print('  0x%08x  字典 id=%s 内容 %s → %s%s' % (
                    record['offset'], record['dict_id'], record['content_size'],
                    record.get('kind', '?'),
                    ('，%d 条（例：%s）' % (record['entries'], record['first_entries']))
                    if record.get('kind') == 'SARC' else ''))
        print('布局自洽：%s' % layout['consistent'])
    return 0 if layout['consistent'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

