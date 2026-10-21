#!/usr/bin/env python3
"""Synthetic regression for the TotK package merge (overlay in, updated package out)."""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY / "dm" / "tools"))
sys.path.insert(0, str(REPOSITORY / "dm" / "android" / "tools"))
from build_package import PackageError
from totk_merge_package import merge


def build_base(path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        manifest = {
            "format": 1,
            "created": "2026-01-01T00:00:00Z",
            "source": "base",
            "subgroup_size": 64,
            "counts": {"game": 1, "romfs": 3, "shaders": 1},
            "bytes": {"game": 1, "romfs": 3, "shaders": 1},
        }
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("game/libdmguest_main.so", b"g")
        archive.writestr("romfs/keep.txt", b"k")
        archive.writestr("romfs/replace.txt", b"old")
        archive.writestr("romfs/remove.txt", b"r")
        archive.writestr("shaders/a.spv", b"s")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = root / "base.zip"
        build_base(base)
        overlay = root / "overlay"
        overlay.mkdir(parents=True)
        (overlay / "new.txt").write_bytes(b"NEW")
        (overlay / "replace.txt").write_bytes(b"NEW2")
        manifest = root / "manifest.tsv"
        manifest.write_text(
            "# totk-overlay-manifest 1\n"
            "counts\tupdated_files=2\tbase_files=3\tadded=1\tremoved=1\tchanged=1\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t3\t10\tnew.txt\n"
            "changed\t4\t20\treplace.txt\n"
            "removed\t1\t\tremove.txt\n",
            encoding="utf-8",
        )
        output = root / "out.zip"
        result = merge(base, manifest, overlay, output)
        assert result["replaced"] == 2, result
        assert result["dropped"] == 1, result
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            assert "romfs/keep.txt" in names
            assert "romfs/remove.txt" not in names
            assert archive.read("romfs/replace.txt") == b"NEW2"
            assert archive.read("romfs/new.txt") == b"NEW"
            assert archive.read("game/libdmguest_main.so") == b"g"
            assert archive.read("shaders/a.spv") == b"s"
            manifest_out = json.loads(archive.read("manifest.json"))
            assert manifest_out["counts"]["romfs"] == 3, manifest_out
            assert manifest_out["counts"]["game"] == 1
            assert manifest_out["counts"]["shaders"] == 1
        try:
            merge(base, manifest, overlay, base)
        except PackageError:
            pass
        else:
            raise AssertionError("merging onto the base package was accepted")
        prefixed = root / "prefixed.tsv"
        prefixed.write_text(
            "# totk-overlay-manifest 1\n"
            "counts\tupdated_files=1\tbase_files=3\tadded=1\tremoved=0\tchanged=0\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t3\t10\tromfs/new.txt\n",
            encoding="utf-8",
        )
        try:
            merge(base, prefixed, overlay, root / "out2.zip")
        except PackageError:
            pass
        else:
            raise AssertionError("a romfs/-prefixed manifest path was accepted")
    print("merge package OK")


if __name__ == "__main__":
    main()
