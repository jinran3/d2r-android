#!/usr/bin/env python3
"""把合成测试指令包装为 NSO，调用同一改写器。| Wrap synthetic instructions as NSO and use the same rewriter."""
from pathlib import Path
import os
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_env import tool   # Windows: 补 .cmd/.bat/.exe 后缀（无扩展名的 clang 是给 bash 用的脚本）

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
toolchain = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
# 不经 host_env.tool() 解析的话，Windows 上拿到的是 NDK 的 shell 脚本本体，
# CreateProcess 执行它会报 WinError 193（不是有效的 Win32 应用程序）。
clang = tool(toolchain / "aarch64-linux-android29-clang")
subprocess.run([str(clang), "-c", str(root / "tests/probe.S"), "-o", str(out / "probe.o")], check=True)
subprocess.run([str(tool(toolchain / "llvm-objcopy")), "-O", "binary", "--only-section=.text", str(out / "probe.o"), str(out / "probe.code")], check=True)
code = (struct.pack("<II", 0x14000002, 0x4000) + (out / "probe.code").read_bytes()).ljust(0x1000, b"\0")
ro = bytearray(0x100)
ro[:4] = b"MOD0"
struct.pack_into("<i", ro, 16, 0x20)
struct.pack_into("<BBBBIIII", ro, 0x20, 1, 3, 3, 3, 0, 1, 0, 0)
header = bytearray(0x100)
header[:4] = b"NSO0"
for index, fields in enumerate([(0x100, 0, len(code)), (0x1100, 0x4000, 0x100), (0x1200, 0x8000, 0x100)]):
    struct.pack_into("<III", header, 0x10 + index * 0x10, *fields)
struct.pack_into("<I", header, 0x3c, 0x1000)
struct.pack_into("<III", header, 0x60, len(code), 0x100, 0x100)
(out / "probe.nso").write_bytes(header + code + ro + bytes(0x100))
subprocess.run([sys.executable, str(root.parent / "tools/patch_nso.py"), str(out / "probe.nso"), str(out), "probe"],
               env=dict(os.environ, DM_TARGET="android", DM_RULESET="native"), check=True)
subprocess.run([sys.executable, str(root / "tools/guest_elf.py"), str(out), str(out), "probe"], check=True)
