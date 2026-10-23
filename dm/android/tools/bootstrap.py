#!/usr/bin/env python3
"""在仓库外安装 Android 构建工具。 | Install Android build tools outside the repository."""
import concurrent.futures
import hashlib
import json
import os
import subprocess
import stat
from pathlib import Path
import tarfile
import threading
import urllib.request
import zipfile

ROOT = Path(os.environ.get("DM_ANDROID_TOOLS", str(Path.home() / "dm-work/tools/android")))
IS_WINDOWS = os.name == "nt"
# 平台专有工具包：Google 为每个 OS 发不同归档，文件名与校验和各不相同（platform 跨平台共用一个）。
# 注意 Windows 的 platform-tools 后缀是 -win 而不是 -windows，写错会 404。
# Per-OS tool archives: Google ships a different archive per OS, with different names and checksums
# (platform itself is OS-independent). platform-tools uses the suffix "-win", not "-windows".
PACKAGES = {
    "ndk": ("android-ndk-r28c-windows.zip", "086bba43ff2f5eb0e387b15c8278bb4e0d89ba1d") if IS_WINDOWS
           else ("android-ndk-r28c-linux.zip", "a7b54a5de87fecd125a17d54f73c446199e72a64"),
    "platform": ("platform-35_r02.zip", "0bb560a90a7a2cbd0dd8348224d518b638fe7949"),
    "build-tools": ("build-tools_r35_windows.zip", "af059bb67cf7786f45ee0db85e2d24985df1b4b6") if IS_WINDOWS
                   else ("build-tools_r35_linux.zip", "2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc"),
    "platform-tools": ("platform-tools_r37.0.1-win.zip", "e03e78b1d80b396f1c3358e31251cb31740e1110") if IS_WINDOWS
                      else ("platform-tools_r37.0.1-linux.zip", "477254aa5f903c15cf51001717bdf347fb6b53e0"),
}
SIZES = {
    "ndk": 748118221 if IS_WINDOWS else 722261334,
    "platform": 64273788,
    "build-tools": 59878107 if IS_WINDOWS else 61958799,
    "platform-tools": 8044989 if IS_WINDOWS else 9054187,
}


_PWRITE_LOCK = threading.Lock()


def _pwrite(fd, data, offset):
    """把 data 写到 fd 的 offset 处（pwrite 语义：不移动文件偏移）。
    POSIX 用 os.pwrite，它对文件偏移是原子的。
    Windows 没有 pwrite 系统调用，os.pwrite 这个属性根本不存在，只能 lseek+write。
    但这两个系统调用不是原子的一对：GIL 只序列化单个调用，线程 A lseek 之后、write 之前
    可以被线程 B 的 lseek 抢占，A 就会把数据写到 B 的偏移上，文件因此写坏并变长。
    所以 Windows 分支必须持锁把 lseek+write 包成原子操作。分段下载写的偏移互不重叠，
    因此这里加锁只牺牲并行度，不改变结果。
    Write data at fd+offset without moving the file position (pwrite semantics).
    POSIX uses os.pwrite, which is atomic with respect to the file position.
    Windows has no pwrite syscall and the attribute does not exist at all, leaving lseek+write.
    Those two calls are not an atomic pair: the GIL serializes individual calls, so thread A can be
    preempted between its lseek and its write and then write at thread B's offset, corrupting and
    over-lengthening the file. The Windows branch therefore holds a lock across lseek+write.
    Ranged downloads write non-overlapping offsets, so the lock costs parallelism but not correctness."""
    if hasattr(os, "pwrite"):
        return os.pwrite(fd, data, offset)
    with _PWRITE_LOCK:
        os.lseek(fd, offset, os.SEEK_SET)
        return os.write(fd, data)


def download(url, path, sha1=None, total=0):
    if path.exists() and (not sha1 or hashlib.file_digest(path.open("rb"), "sha1").hexdigest() == sha1):
        return path
    temp = path.with_suffix(path.suffix + ".part")
    print("Download:", path.name, flush=True)
    # 大工具包分段下载，已下载的连续前缀可续传。
    # Download large tool archives in ranges and resume an existing contiguous prefix.
    if total:
        prefix = temp.stat().st_size if temp.exists() else 0
        # O_BINARY 必不可少：Windows 的 os.open 默认按文本模式打开，底层 CRT 会把 0x0A 翻成 0x0D0A，
        # 工具链是二进制包，这样写下去会静默变长变坏（实测 200000 字节 -> 200452，多了 452 个 CR，
        # 正好等于 LF 数）。O_BINARY 在 POSIX 上不存在，用 getattr 兜底，Linux/CI 行为不变。
        # O_BINARY is mandatory: on Windows os.open defaults to text mode and the CRT rewrites 0x0A as
        # 0x0D0A, silently corrupting these binary archives (measured 200000 -> 200452 bytes; the 452
        # extra CRs exactly match the LF count). It does not exist on POSIX, hence getattr, so Linux/CI
        # is unchanged.
        fd = os.open(temp, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        ranges = [(start, min(start + 8 * 1024 * 1024, total))
                  for start in range(prefix, total, 8 * 1024 * 1024)]
        def part(span):
            start, end = span
            piece = path.with_name(path.name + f".{start}.chunk")
            if not piece.exists() or piece.stat().st_size != end - start:
                subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                                "--retry", "5", "--retry-all-errors", "--connect-timeout", "20",
                                "--max-time", "180", "--range", f"{start}-{end - 1}",
                                "--output", str(piece), url], check=True)
            if piece.stat().st_size != end - start:
                raise RuntimeError("Server returned wrong range: " + piece.name)
            _pwrite(fd, piece.read_bytes(), start)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
                list(pool.map(part, ranges))
        except BaseException:
            # 分段文件可能有洞；失败时仅保留此前确定完整的连续前缀。
            # A failed ranged download may have holes; keep only the previous complete prefix.
            os.ftruncate(fd, prefix)
            raise
        finally:
            os.close(fd)
    else:
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                        "--retry", "5", "--retry-all-errors", "--output", str(temp), url], check=True)
    if sha1 and hashlib.file_digest(temp.open("rb"), "sha1").hexdigest() != sha1:
        raise RuntimeError("Tool archive checksum mismatch: " + path.name)
    temp.replace(path)
    for piece in path.parent.glob(path.name + ".*.chunk"):
        piece.unlink()
    return path


def install_package(item):
    name, (archive, sha1) = item
    target = ROOT / name
    if target.exists():
        path = ROOT / "downloads" / archive
        if path.exists():
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if stat.S_ISLNK(info.external_attr >> 16):
                        link = target.joinpath(*Path(info.filename).parts[1:])
                        if not link.is_symlink():
                            if link.exists(): link.unlink()
                            link.symlink_to(z.read(info).decode())
        return
    path = download("https://dl.google.com/android/repository/" + archive, ROOT / "downloads" / archive, sha1, SIZES[name])
    staging = ROOT / (name + ".unpack")
    staging.mkdir(exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(staging)
        for info in z.infolist():
            mode = (info.external_attr >> 16) & 0o777
            if stat.S_ISLNK(info.external_attr >> 16):
                link = staging / info.filename
                link.unlink()
                link.symlink_to(z.read(info).decode())
                continue
            if mode and not info.is_dir():
                (staging / info.filename).chmod(mode)
    children = list(staging.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise RuntimeError("Unexpected archive layout: " + archive)
    children[0].rename(target)
    staging.rmdir()
    print("Ready:", target, flush=True)


def install_java():
    if (ROOT / "jdk/bin/java").exists():
        return
    url = "https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=" + ("windows" if IS_WINDOWS else "linux")
    response = subprocess.check_output(["curl", "--fail", "--silent", "--show-error", "--location",
                                        "--retry", "3", "--max-time", "60", url])
    package = json.loads(response)[0]["binary"]["package"]
    path = download(package["link"], ROOT / "downloads" / package["name"], total=package["size"])
    if hashlib.file_digest(path.open("rb"), "sha256").hexdigest() != package["checksum"]:
        raise RuntimeError("JDK archive checksum mismatch")
    staging = ROOT / "jdk.unpack"
    staging.mkdir(exist_ok=True)
    # 归档格式跟平台走：Adoptium 的 Windows 发 .zip，Linux 发 .tar.gz。按扩展名判断，而不是
    # 再看一遍 IS_WINDOWS —— 将来换镜像源时，格式变化不会让解包静默失败。
    # Archive format follows the platform: Adoptium ships .zip for Windows, .tar.gz for Linux.
    # Keyed on the extension so a mirror change cannot silently break extraction.
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            z.extractall(staging)
    else:
        with tarfile.open(path) as t:
            t.extractall(staging, filter="data")
    children = list(staging.iterdir())
    children[0].rename(ROOT / "jdk")
    staging.rmdir()
    print("Ready: JDK", flush=True)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "downloads").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(install_package, item) for item in PACKAGES.items()]
        futures.append(pool.submit(install_java))
        for future in concurrent.futures.as_completed(futures):
            future.result()
    print("Android toolchain:", ROOT)
