#!/usr/bin/env python3
"""直接从**解密后的 RomFS 映像**打出可导入的数据包（TotK 用）。

为什么要有这一步：TotK 的 RomFS 是一棵深目录树（304,207 个文件、15.93 GiB）。逐个解到盘上再
逐个推给手机既慢（这台机器上解 30 万个小文件要几十小时）又不现实（adb 没有推目录的本事）。
而 `dm/tools/switch_nca.py romfs-export` 已经把整段 RomFS 解密后导出成**一个**文件，
所以这里直接从映像里按路径读出每个文件，写进数据包 zip —— 一次顺序读、一个包，手机端用现成的
导入流程解开即可。

用法：
  totk_package.py --romfs-image <romfs.img> --ivfc <romfs.img.ivfc>
                  --shaders <着色器包目录> --game <模块目录> --output <包.zip>

包内结构与 D2R 侧一致（见 docs/ANDROID_PACKAGE.zh-CN.md）：
  manifest.json / game/<模块与布局表> / romfs/<RomFS 里的相对路径> / shaders/<键>.spv 与 .meta
"""
import argparse
import datetime
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MANIFEST_NAME = "manifest.json"
GAME_MODULES = ("libdmguest_main.so", "libdmguest_sdk.so", "libdmguest_subsdk0.so")
GAME_LAYOUTS = tuple("%s.%s.tsv" % (name, kind) for name in ("main", "sdk", "subsdk0") for kind in ("fixups", "gates"))


class Romfs:
    """解密后的 RomFS 映像：按路径取文件。 | The decrypted RomFS image: fetch files by path."""

    def __init__(self, image: Path, ivfc: Path):
        self.image = image.open("rb")
        fs = ivfc.open("rb").read(0x200)
        levels = []
        count = struct.unpack_from("<I", fs, 0x08 + 0x0C)[0]
        for index in range(min(count, 6)):
            logical, hash_size, block, _ = struct.unpack_from("<QQII", fs, 0x08 + 0x10 + index * 0x18)
            levels.append(logical)
        self.base = levels[-1]
        self.image.seek(self.base)
        fields = struct.unpack_from("<10Q", self.image.read(0x50), 0)
        names = ["header_size", "dir_hash_table_offset", "dir_hash_table_size", "dir_meta_table_offset",
                 "dir_meta_table_size", "file_hash_table_offset", "file_hash_table_size",
                 "file_meta_table_offset", "file_meta_table_size", "data_offset"]
        head = dict(zip(names, fields))
        self.dirs = self.read(self.base + head["dir_meta_table_offset"], head["dir_meta_table_size"])
        self.files = self.read(self.base + head["file_meta_table_offset"], head["file_meta_table_size"])
        self.data_offset = self.base + head["data_offset"]

    def read(self, offset, size):
        self.image.seek(offset)
        return self.image.read(size)

    def entries(self):
        """返回 [(路径, 映像内偏移, 大小)]。 | [(path, offset in the image, size)]."""
        def directory(offset):
            parent, sibling, child, file, _hash, name_size = struct.unpack_from("<6I", self.dirs, offset)
            name = self.dirs[offset + 24:offset + 24 + name_size].split(b"\0")[0].decode("utf-8", "replace")
            return parent, sibling, child, file, name

        def file_entry(offset):
            parent, sibling, data_offset, size, _hash, name_size = struct.unpack_from("<IIQQII", self.files, offset)
            name = self.files[offset + 32:offset + 32 + name_size].split(b"\0")[0].decode("utf-8", "replace")
            return data_offset, size, name

        out = []
        # 每个目录项带**完整前缀**入栈：只带自己的名字会把不同层级里同名的目录混在一起，
        # 包里就会出现重名路径与放错目录的文件。
        # Every directory is pushed with its full prefix: carrying only its own name mixes up directories with the
        # same name at different levels, which yields duplicate and misplaced paths in the package.
        stack = [(0, "")]
        while stack:
            offset, prefix = stack.pop()
            _parent, _sibling, child, file, _hash, name_size = struct.unpack_from("<6I", self.dirs, offset)
            entry = file
            while entry != 0xFFFFFFFF:
                data_offset, size, file_name = file_entry(entry)
                out.append((prefix + file_name, self.data_offset + data_offset, size))
                entry = struct.unpack_from("<I", self.files, entry + 4)[0]
            child_entry = child
            while child_entry != 0xFFFFFFFF:
                _cp, _cs, _cc, _cf, _ch, child_name_size = struct.unpack_from("<6I", self.dirs, child_entry)
                child_name = self.dirs[child_entry + 24:child_entry + 24 + child_name_size].split(b"\0")[0].decode("utf-8", "replace")
                stack.append((child_entry, prefix + (child_name + "/" if child_name else "")))
                child_entry = struct.unpack_from("<I", self.dirs, child_entry + 4)[0]
        return out

    def read_file(self, offset, size):
        self.image.seek(offset)
        return self.image.read(size)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--romfs-image", type=Path, required=True, help="解密后的 RomFS 映像 | the decrypted RomFS image")
    parser.add_argument("--ivfc", type=Path, required=True, help="映像旁边的 IVFC 头 | the IVFC header beside the image")
    parser.add_argument("--shaders", type=Path, required=True, help="着色器包目录 | the shader package directory")
    parser.add_argument("--game", type=Path, required=True, help="模块目录 | the module directory")
    parser.add_argument("--output", type=Path, required=True, help="数据包输出路径 | the package output path")
    args = parser.parse_args()

    romfs = Romfs(args.romfs_image, args.ivfc)
    entries = romfs.entries()
    print("映像里的文件 %d 个" % len(entries), flush=True)
    for name in GAME_MODULES + GAME_LAYOUTS:
        if not (args.game / name).is_file():
            raise SystemExit("game directory is missing %s" % name)
    profile = args.shaders / "host-subgroup-size.txt"
    if not profile.is_file():
        raise SystemExit("shaders directory has no host-subgroup-size.txt")
    subgroup = int(profile.read_text(encoding="utf-8").strip())
    shaders = sorted(p for p in args.shaders.iterdir() if p.is_file())
    if len(shaders) < 2:
        raise SystemExit("shaders directory has no modules")

    total_romfs = sum(size for _path, _offset, size in entries)
    total_shaders = sum(p.stat().st_size for p in shaders)
    total_game = sum((args.game / name).stat().st_size for name in GAME_MODULES + GAME_LAYOUTS)
    manifest = {
        "format": 1,
        "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "TotK data (RomFS image + shaders + rewritten modules)",
        "subgroup_size": subgroup,
        "counts": {"game": len(GAME_MODULES) + len(GAME_LAYOUTS), "romfs": len(entries), "shaders": len(shaders)},
        "bytes": {"game": total_game, "romfs": total_romfs, "shaders": total_shaders},
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    written = 0
    total = total_romfs + total_shaders + total_game + len(manifest_bytes)
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        info = zipfile.ZipInfo(MANIFEST_NAME, date_time=FIXED_TIMESTAMP)
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = 0o644 << 16
        archive.writestr(info, manifest_bytes)
        written += len(manifest_bytes)
        for name in GAME_MODULES + GAME_LAYOUTS:
            info = zipfile.ZipInfo("game/" + name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            with (args.game / name).open("rb") as source, archive.open(info, "w") as target:
                shutil_copy(source, target)
            written += (args.game / name).stat().st_size
        for path, offset, size in entries:
            info = zipfile.ZipInfo("romfs/" + path, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            with archive.open(info, "w") as target:
                remaining = size
                position = offset
                while remaining:
                    chunk = romfs.read_file(position, min(1 << 22, remaining))
                    if not chunk:
                        break
                    target.write(chunk)
                    position += len(chunk)
                    remaining -= len(chunk)
            written += size
            if written % (1 << 30) < size:
                print("  打包 %.2f / %.2f GiB" % (written / 2**30, total / 2**30), flush=True)
        for path in shaders:
            info = zipfile.ZipInfo("shaders/" + path.name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            with path.open("rb") as source, archive.open(info, "w") as target:
                shutil_copy(source, target)
            written += path.stat().st_size
    temporary.replace(args.output)
    print("完成：%s（%.2f GiB，RomFS %d 个文件）"
          % (args.output, args.output.stat().st_size / 2**30, len(entries)))
    return 0


def shutil_copy(source, target):
    while True:
        chunk = source.read(1 << 20)
        if not chunk:
            break
        target.write(chunk)


if __name__ == "__main__":
    raise SystemExit(main())
