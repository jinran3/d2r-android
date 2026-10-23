#!/usr/bin/env python3
"""把 BKTR overlay 合进 TotK 宿主数据包：替换被更新的文件、去掉被删掉的文件。

为什么自己写：宿主包的条目是 30 多万个文件、全部 STORED；重新压缩一遍既慢又会改变字节。
这里逐条**原样复制**未被替换的条目，只把 overlay 里的文件换进去，并对结果做自检。

只读基座包、只写新文件：输出路径不能和基座包相同，也必须在仓库外。

用法:
  python dm/tools/totk_merge_package.py --base-package <基座包.zip> \
      --overlay-manifest <清单.tsv> --overlay-dir <导出的正文目录> --output <新包.zip> [--json]
"""
import argparse
import datetime
import json
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = Path(__file__).resolve().parents[2]
# 清单解析器只有一个实现：Android 侧的包工具。 | The manifest has one parser: the Android package tool.
sys.path.insert(0, str(REPOSITORY / "dm" / "android" / "tools"))
from build_package import PackageError, read_overlay_manifest  # noqa: E402

FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CHUNK = 1 << 22
ROMFS_PREFIX = "romfs/"


def copy_entry(source, target, info):
    """原样复制一个 STORED 条目（不重新压缩）。 | Copy a STORED entry verbatim."""
    fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    fresh.compress_type = zipfile.ZIP_STORED
    fresh.external_attr = info.external_attr
    fresh.create_system = info.create_system
    with source.open(info.filename) as reader, target.open(fresh, "w") as writer:
        while True:
            block = reader.read(CHUNK)
            if not block:
                break
            writer.write(block)


def write_file(target, path, name):
    """把一个外部文件写成包内条目。 | Write an external file into the archive."""
    info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    with path.open("rb") as reader, target.open(info, "w") as writer:
        while True:
            block = reader.read(CHUNK)
            if not block:
                break
            writer.write(block)


def merge(base_package, manifest_path, overlay_dir, output, quiet=False):
    if output.resolve() == base_package.resolve():
        raise PackageError("output must not be the base package")
    repository = REPOSITORY.resolve()
    if str(output.resolve()).lower().startswith(str(repository).lower() + os.sep.lower()):
        raise PackageError(f"output must stay outside the repository: {output}")
    if output.exists():
        raise PackageError(f"output already exists: {output}")

    rows = []
    summary = read_overlay_manifest(manifest_path, None, None, rows)
    overlay = {}
    removed = set()
    for status, size, relative in rows:
        # 清单里的路径是相对 RomFS 根的（"Mals/..."），包里才是 "romfs/Mals/..."。
        # 前缀写错时必须报错，而不是"一个都没命中"那样静默通过。
        # Manifest paths are relative to the RomFS root; package entries carry the "romfs/" prefix.
        if relative.startswith(ROMFS_PREFIX):
            raise PackageError(f"manifest path must not carry the romfs/ prefix: {relative}")
        if status in ("added", "changed"):
            overlay[relative] = size
        elif status == "removed":
            removed.add(relative)
    if not quiet:
        print("overlay：替换 %d 个、删除 %d 个（清单 %d 行）" % (len(overlay), len(removed), summary["rows"]),
              file=sys.stderr, flush=True)

    temporary = output.with_suffix(output.suffix + ".part")
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = {"game": 0, "romfs": 0, "shaders": 0}
    byte_counts = {"game": 0, "romfs": 0, "shaders": 0}
    replaced = 0
    dropped = 0
    with zipfile.ZipFile(base_package) as source:
        base_manifest = json.loads(source.read("manifest.json"))
        base_names = set(source.namelist())
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED, allowZip64=True) as target:
            for info in source.infolist():
                name = info.filename
                if name == "manifest.json":
                    continue
                if name.startswith(ROMFS_PREFIX):
                    relative = name[len(ROMFS_PREFIX):]
                    if relative in removed:
                        dropped += 1
                        continue
                    if relative in overlay:
                        path = overlay_dir.joinpath(*PurePosixPath(relative).parts)
                        if not path.is_file():
                            raise PackageError(f"overlay file is missing: {relative}")
                        if path.stat().st_size != overlay[relative]:
                            raise PackageError(f"overlay size mismatch: {relative}")
                        write_file(target, path, name)
                        byte_counts["romfs"] += overlay[relative]
                        counts["romfs"] += 1
                        replaced += 1
                        continue
                copy_entry(source, target, info)
                group = name.split("/", 1)[0] if "/" in name else ""
                if group in counts:
                    counts[group] += 1
                    byte_counts[group] += info.file_size
            # 新增文件：清单里有、基座包里没有的路径。
            for relative, size in overlay.items():
                name = ROMFS_PREFIX + relative
                if name in base_names:
                    continue
                path = overlay_dir.joinpath(*PurePosixPath(relative).parts)
                if not path.is_file():
                    raise PackageError(f"overlay file is missing: {relative}")
                if path.stat().st_size != size:
                    raise PackageError(f"overlay size mismatch: {relative}")
                write_file(target, path, name)
                counts["romfs"] += 1
                byte_counts["romfs"] += size
                replaced += 1
            manifest = dict(base_manifest)
            manifest["created"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            manifest["source"] = "TotK v1.4.2 base package + BKTR patch overlay"
            manifest["counts"] = dict(counts)
            manifest["bytes"] = dict(byte_counts)
            info = zipfile.ZipInfo("manifest.json", date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            target.writestr(info, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    temporary.replace(output)

    # 自检：重新读一遍中央目录，确认条目数、removed 缺席、overlay 大小。
    with zipfile.ZipFile(output) as check:
        names = check.namelist()
        infos = {info.filename: info for info in check.infolist()}
        groups = {}
        for name in names:
            group = name.split("/", 1)[0] if "/" in name else name
            groups[group] = groups.get(group, 0) + 1
        still_there = [relative for relative in removed if ROMFS_PREFIX + relative in infos]
        if still_there:
            raise PackageError(f"{len(still_there)} removed paths are still in the package")
        for relative, size in overlay.items():
            info = infos.get(ROMFS_PREFIX + relative)
            if info is None:
                raise PackageError(f"overlay path missing from the package: {relative}")
            if info.file_size != size:
                raise PackageError(f"overlay size mismatch in the package: {relative}")
    return {
        "output": str(output),
        "bytes": output.stat().st_size,
        "entries": len(names),
        "groups": groups,
        "replaced": replaced,
        "dropped": dropped,
        "manifest_counts": counts,
        "manifest_bytes": byte_counts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-package", type=Path, required=True)
    parser.add_argument("--overlay-manifest", type=Path, required=True)
    parser.add_argument("--overlay-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = merge(args.base_package, args.overlay_manifest, args.overlay_dir, args.output)
    except PackageError as error:
        sys.exit(f"package error: {error}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("完成：%s（%d 个条目，%.2f GiB）" % (result["output"], result["entries"], result["bytes"] / 1073741824))
        print("  替换 %d 个、删除 %d 个；counts=%s" % (result["replaced"], result["dropped"], result["manifest_counts"]))


if __name__ == "__main__":
    main()
