#!/usr/bin/env python3
"""Android 工具链的宿主平台差异。 | Host-platform differences for the Android toolchain.

上游只在 Linux x86_64 上跑过，所以工具链路径与可执行文件名都写死了。这两件事在
Windows 上不一样，集中在这里，别在各个脚本里各判一次：

1. NDK 的预编译目录按 OS 命名：Linux 是 linux-x86_64，Windows 是 windows-x86_64。
2. 工具在 Windows 上带扩展名，而且扩展名不统一：
   - aapt2 / zipalign / adb / java / glslc / llvm-*      -> .exe
   - clang（目标三元组包装）/ clang++                      -> .cmd
   - d8 / apksigner                                        -> .bat（只有批处理，没有 .exe）
   CreateProcess 只会自动补 .exe，补不出 .cmd / .bat，
   所以像 `build-tools/d8` 这样不带扩展名的写法在 Windows 上必定 FileNotFoundError。

Upstream only ever ran on Linux x86_64, so toolchain paths and executable names were hardcoded.
Two things differ on Windows; they live here so each script does not re-implement the check:

1. The NDK prebuilt directory is named per host OS: linux-x86_64 vs windows-x86_64.
2. Tools carry extensions on Windows, and they are not uniform:
   - aapt2 / zipalign / adb / java / glslc / llvm-*      -> .exe
   - clang (target-triplet wrapper) / clang++              -> .cmd
   - d8 / apksigner                                        -> .bat (batch only; there is no .exe)
   CreateProcess only appends .exe, so an extensionless path such as `build-tools/d8`
   can never resolve and always raises FileNotFoundError on Windows.
"""
import os
import time
from contextlib import contextmanager
from pathlib import Path

HOST_TAG = "windows-x86_64" if os.name == "nt" else "linux-x86_64"

# 顺序要紧：先 .exe 再 .cmd 再 .bat。d8 只有 .bat，clang 只有 .cmd，其余是 .exe。
# Order matters: .exe, then .cmd, then .bat. d8 has only .bat, clang only .cmd, the rest .exe.
_SUFFIXES = (".exe", ".cmd", ".bat")


def tool(path):
    """把不带扩展名的工具路径解析成 Windows 上真实可执行的文件。
    非 Windows 原样返回；Windows 上依次尝试 .exe/.cmd/.bat，一个都不存在时返回原路径，
    让调用方的 "Missing tool" 检查仍能报出那个熟悉的名字。
    Resolve an extensionless tool path to a real executable on Windows.
    Returns the path unchanged off Windows. On Windows it tries .exe/.cmd/.bat in order; when
    none exists it returns the original path so the caller's "Missing tool" check still reports
    the familiar name."""
    if os.name != "nt":
        return path
    path = Path(path)
    if path.suffix:                      # 已经带扩展名 | already carries one
        return path
    for suffix in _SUFFIXES:
        candidate = path.with_name(path.name + suffix)
        if candidate.exists():
            return candidate
    return path


@contextmanager
def file_lock(path):
    """跨平台的进程内独占文件锁，语义对齐上游的 fcntl.flock(path, LOCK_EX)：
    阻塞等待、持有期间互斥、退出（异常也一样）自动释放。

    POSIX 用 fcntl.flock。Windows 没有 fcntl，等价物是 msvcrt.locking，但有两个坑：
      - 只能锁「当前文件偏移起的 N 字节」，所以先 lseek 到 0、锁 1 字节；
      - LK_LOCK 只重试约 10 秒就抛 OSError，而这里的构建可能等更久，
        所以用 LK_NBLCK 自己循环重试，不受那个上限约束。
    与 fcntl 的差异仅在「同进程内重复获取同一把锁」的表现（flock 在同 fd 上是幂等的，
    这里会自锁）；本项目每个构建路径只取一次锁，不依赖该行为。

    A cross-process exclusive file lock matching the upstream fcntl.flock(LOCK_EX):
    blocking, mutually exclusive, released on exit (including exceptions).
    POSIX uses fcntl.flock. Windows has no fcntl; msvcrt.locking is the equivalent but
    can only lock N bytes from the current file offset (hence lseek to 0 and lock 1 byte),
    and LK_LOCK gives up after ~10 seconds while a build may legitimately wait longer, so
    this retries with LK_NBLCK itself instead. The only behavioural difference from flock
    is repeated acquisition within one process (flock is idempotent on the same fd; this
    would self-deadlock); each build path here takes the lock exactly once."""
    path = Path(path)
    if os.name == "nt":
        import msvcrt
        with open(path, "a+b") as fh:
            os.lseek(fh.fileno(), 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield fh
            finally:
                os.lseek(fh.fileno(), 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
    else:
        import fcntl
        with open(path, "a+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield fh
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
