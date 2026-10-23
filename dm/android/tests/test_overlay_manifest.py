#!/usr/bin/env python3
"""Synthetic regression for the metadata-only overlay manifest gate."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_package import PackageError, read_overlay_manifest


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sub").mkdir()
        (root / "sub" / "file.bin").write_bytes(b"1234")
        manifest = root / "manifest.tsv"
        write(
            manifest,
            "# totk-overlay-manifest 1\n"
            "counts\tupdated_files=1\tbase_files=0\tadded=1\tremoved=0\tchanged=0\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t4\t123\tsub/file.bin\n",
        )
        good = read_overlay_manifest(manifest, root)
        assert good["rows"] == 1
        assert good["statuses"]["added"] == 1
        assert good["counts"]["updated_files"] == 1
        assert good["checked_against_romfs"] == 1

        # A manifest may carry an optional semantics comment between the header and the counts.
        commented = root / "commented.tsv"
        write(
            commented,
            "# totk-overlay-manifest 1\n"
            "# changed = content replaced by the patch\n"
            "counts\tupdated_files=1\tbase_files=0\tadded=1\tremoved=0\tchanged=0\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t4\t123\tsub/file.bin\n",
        )
        assert read_overlay_manifest(commented, root)["rows"] == 1

        # Only the requested statuses are looked up in the tree.
        subset = read_overlay_manifest(manifest, root, statuses={"changed"})
        assert subset["checked_against_romfs"] == 0

        bad = root / "bad.tsv"
        write(
            bad,
            "# totk-overlay-manifest 1\n"
            "counts\tupdated_files=1\tbase_files=0\tadded=1\tremoved=0\tchanged=0\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t5\t123\tsub/file.bin\n",
        )
        try:
            read_overlay_manifest(bad, root)
        except PackageError:
            pass
        else:
            raise AssertionError("size mismatch was accepted")

        unsafe = root / "unsafe.tsv"
        write(
            unsafe,
            "# totk-overlay-manifest 1\n"
            "counts\tupdated_files=1\tbase_files=0\tadded=1\tremoved=0\tchanged=0\tunchanged=0\n"
            "status\tsize\tvirtual_offset\tpath\n"
            "added\t4\t123\t../escape\n",
        )
        try:
            read_overlay_manifest(unsafe, root)
        except PackageError:
            pass
        else:
            raise AssertionError("unsafe path was accepted")
    print("overlay manifest OK")


if __name__ == "__main__":
    main()
