#!/usr/bin/env python3
"""TotK 着色器包：取出 zstd 字典并解开着色器归档（事实表的来源，见计划 §4.4）。

两件事：
1. **任天堂的 zstd 字典在游戏自己里**：`/Pack/ZsDic.pack.zs` 是个 SARC，里面装着若干份
   128 KB 的 zstd 字典（`zs.zsdic` id=1、`bcett.byml.zsdic` id=2、`pack.zsdic` id=3）。
   着色器包的 zstd 帧头写着自己要用哪个字典 id（着色器用的是 1）。没有这份字典，
   `*.bfsha.zs` / `*.sarc.zs` 一律报 "Dictionary mismatch"。
2. **着色器归档解出来是带反射元数据的容器**：`ApplicationPackage.Nin_NX_NVN.release.sarc.zs`
   是 SARC（19 个条目，含 `*.sharcb`），各 `*.bfsha.zs` 是 FSHA 容器；里面的条目带着
   参数名 / 采样器名一类的字符串（例如 `cTexSrc`、`gl_InstanceID`）。也就是说 D2R 那套
   「从 PC 版着色器反射冻结事实表」的路子对 TotK 不成立，但**从游戏自带的着色器归档里取**
   这条路是通的（计划 §4.4 的方案 D）。

用法：switch_shaders.py <RomFS 目录> <输出目录> [--only 名字片段]
游戏文件只在本机读，产物落在仓库外；本工具不打印也不复制任何密钥。

TotK shader packages: fetch the zstd dictionaries and decode the shader archives (the source of
the fact table, see plan §4.4).
Two things:
1. **Nintendo's zstd dictionaries ship inside the game**: `/Pack/ZsDic.pack.zs` is a SARC holding
   several 128 KB zstd dictionaries (`zs.zsdic` id=1, `bcett.byml.zsdic` id=2, `pack.zsdic` id=3).
   The shader packages' zstd frames name the dictionary id they need (the shaders use 1). Without
   that dictionary every `*.bfsha.zs` / `*.sarc.zs` fails with "Dictionary mismatch".
2. **The decoded shader archives carry reflection metadata**: `ApplicationPackage...sarc.zs` is a
   SARC (19 entries, including `*.sharcb`), the `*.bfsha.zs` files are FSHA containers, and the
   entries hold parameter / sampler name strings (`cTexSrc`, `gl_InstanceID`, ...). So D2R's
   "freeze the facts from the PC build's shader reflection" route does not exist for TotK, but
   "take them from the game's own shader archives" does (plan §4.4 option D).

Usage: switch_shaders.py <RomFS directory> <output directory> [--only name fragment]
Game files are only read on this machine and the outputs stay outside the repository; this tool
never prints or copies key material.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import zstandard

SARC_MAGIC = b"SARC"
BNSH_MAGIC = b"BNSH\0\0\0\0"


def sarc_entries(data: bytes) -> dict:
    """解析小端 SARC：{名字: 内容}。 | Parse a little-endian SARC: {name: content}."""
    if data[:4] != SARC_MAGIC or data[6:8] != b"\xff\xfe":
        raise ValueError("不是小端 SARC")
    header, = struct.unpack_from("<H", data, 4)
    length, base = struct.unpack_from("<II", data, 8)
    magic, size, count, _ = struct.unpack_from("<4sHHI", data, 20)
    if header != 20 or magic != b"SFAT" or length != len(data):
        raise ValueError("SARC 头不合法")
    names = 32 + count * 16
    out = {}
    for index in range(count):
        _, attr, start, end = struct.unpack_from("<4I", data, 32 + index * 16)
        pos = names + 8 + (attr & 0xFFFFFF) * 4
        nul = data.find(b"\0", pos, base)
        if nul < 0:
            raise ValueError("SARC 条目名没有结尾")
        name = data[pos:nul].decode("utf-8", "replace")
        out[name] = data[base + start:base + end]
    return out


def zstd_dict_id(blob: bytes):
    """字典头里的 id（zstd 字典格式：魔数 + id + 内容）。 | The id inside a zstd dictionary header."""
    if len(blob) < 8 or struct.unpack_from("<I", blob, 0)[0] != 0xEC30A437:
        return None
    return struct.unpack_from("<I", blob, 4)[0]


def load_dictionaries(pack: bytes) -> dict:
    """从 /Pack/ZsDic.pack.zs 解出 {id: 字典}。 | Extract {id: dictionary} from the dictionary pack."""
    raw = zstandard.ZstdDecompressor().decompress(pack, max_output_size=64 << 20)
    out = {}
    for blob in sarc_entries(raw).values():
        key = zstd_dict_id(blob)
        if key is not None:
            out[key] = zstandard.ZstdCompressionDict(blob)
    return out


def decode(data: bytes, dictionaries: dict) -> bytes:
    """按帧头写的字典 id 解 zstd。 | Decompress with the dictionary the frame names."""
    key = zstandard.get_frame_parameters(data).dict_id
    if key and key not in dictionaries:
        raise ValueError("缺少 zstd 字典 id=%s" % key)
    return zstandard.ZstdDecompressor(dict_data=dictionaries.get(key)).decompress(data, max_output_size=512 << 20)


def shader_paths(romfs: Path):
    """要取的着色器文件（本体 RomFS 里的相对路径）。 | The shader files to take (relative paths in the base RomFS)."""
    out = []
    shader_dir = romfs / "Shader"
    if shader_dir.is_dir():
        out += sorted(shader_dir.glob("*.zs"))
    layout_dir = romfs / "UI" / "LayoutArchive"
    if layout_dir.is_dir():
        out += sorted(layout_dir.glob("*.blarc.zs"))
    lib = romfs / "Lib"
    if lib.is_dir():
        for library in sorted(p for p in lib.iterdir() if p.is_dir()):
            out += sorted(library.glob("*.release.sarc.zs"))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("romfs", type=Path, help="已解出的 RomFS 目录（仓库外） | the extracted RomFS directory (outside the repository)")
    parser.add_argument("output", type=Path, help="输出目录 | the output directory")
    parser.add_argument("--only", default=None, help="只处理名字含这个片段的文件 | only files whose name contains this fragment")
    args = parser.parse_args()

    pack = args.romfs / "Pack" / "ZsDic.pack.zs"
    if not pack.is_file():
        raise SystemExit("缺少 zstd 字典包：%s" % pack)
    dictionaries = load_dictionaries(pack.read_bytes())
    print("zstd 字典：%s" % ", ".join("id=%d" % k for k in sorted(dictionaries)))

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path in shader_paths(args.romfs):
        if args.only and args.only.lower() not in path.name.lower():
            continue
        try:
            content = decode(path.read_bytes(), dictionaries)
        except Exception as error:
            print("跳过 %s：%s" % (path.name, error))
            continue
        if content[:4] == SARC_MAGIC:
            entries = sarc_entries(content)
        else:
            entries = {path.name.removesuffix(".zs"): content}
        for name, blob in entries.items():
            (args.output / name).write_bytes(blob)
            manifest.append({
                "name": name,
                "source": str(path.relative_to(args.romfs)).replace("\\", "/"),
                "size": len(blob),
                "magic": blob[:4].hex(),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "has_bnsh": BNSH_MAGIC in blob,
            })
        print("%-52s -> %d 个条目" % (path.name[:52], len(entries)))
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("共写出 %d 个文件，清单在 %s" % (len(manifest), args.output / "manifest.json"))


if __name__ == "__main__":
    main()
