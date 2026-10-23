#!/usr/bin/env python3
"""totk-app 的构建入口（R0：纯 Java 骨架，不链任何 native 代码）。

一条命令出可安装 APK：aapt2 链接清单 → javac → d8 → 把 classes.dex 塞进 APK → zipalign → apksigner。
工具全部来自 $DM_ANDROID_TOOLS（本机固定的 Android SDK 副本），签名用其中的 debug.keystore。

Build entry point of totk-app (R0: pure Java skeleton, no native code linked).
One command produces an installable APK: aapt2 links the manifest, javac compiles, d8 dexes, the dex is stored into the
APK, then zipalign and apksigner run. All tools come from $DM_ANDROID_TOOLS, and the debug.keystore there signs it.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # totk-app/
ANDROID = ROOT / "android"
BUILD = ROOT / "build"
TOOLS = Path(os.environ.get("DM_ANDROID_TOOLS", r"D:\Switch\.tools\android"))
BT = TOOLS / "build-tools"
JDK = TOOLS / "jdk" / "bin"
ANDROID_JAR = TOOLS / "platform" / "android.jar"
KEYSTORE = TOOLS / "debug.keystore"

VERSION = os.environ.get("TOTK_APP_VERSION", "R0")
MIN_SDK, TARGET_SDK = "29", "34"


def run(cmd, what):
    print(f"-- {what}\n   {' '.join(str(c) for c in cmd)}", flush=True)
    # 工具的报错在中文 Windows 上是 GBK：不解码成 text，失败时按 utf-8 replace 打印，避免解码异常盖住真正的错误
    # Tool messages are GBK on a Chinese Windows: keep the raw bytes and decode with replacement only when printing,
    # so a decode error can never mask the real failure
    r = subprocess.run([str(c) for c in cmd], capture_output=True)
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    if r.returncode != 0:
        sys.stdout.write(out)
        sys.stderr.write(err)
        raise SystemExit(f"FAIL {what}: exit {r.returncode}")
    if err.strip():
        print("   " + err.strip().replace("\n", "\n   "), flush=True)
    return r


def main():
    for p in (BT, JDK, ANDROID_JAR, KEYSTORE):
        if not p.exists():
            raise SystemExit(f"缺少工具：{p}（检查 DM_ANDROID_TOOLS）")
    BUILD.mkdir(parents=True, exist_ok=True)
    for d in ("classes", "dex"):
        shutil.rmtree(BUILD / d, ignore_errors=True)
        (BUILD / d).mkdir()

    linked = BUILD / "linked.apk"
    run([BT / "aapt2.exe", "link", "-o", linked, "-I", ANDROID_JAR,
         "--manifest", ANDROID / "AndroidManifest.xml",
         "--min-sdk-version", MIN_SDK, "--target-sdk-version", TARGET_SDK], "aapt2 link")

    sources = sorted(str(p) for p in (ANDROID / "src").rglob("*.java"))
    if not sources:
        raise SystemExit("android/src 下没有 .java")
    run([JDK / "javac.exe", "-nowarn", "-encoding", "UTF-8", "-source", "11", "-target", "11",
         "-classpath", ANDROID_JAR, "-d", BUILD / "classes", *sources], f"javac（{len(sources)} 个源文件）")

    classes = sorted(str(p) for p in (BUILD / "classes").rglob("*.class"))
    run([BT / "d8.bat", "--lib", ANDROID_JAR, "--min-api", MIN_SDK,
         "--output", BUILD / "dex", *classes], f"d8（{len(classes)} 个 class）")

    dex = BUILD / "dex" / "classes.dex"
    if not dex.exists():
        raise SystemExit("d8 没有产出 classes.dex")

    # native 层（R1 起）：NDK clang 直接编一个 .so。不开 CMake —— 现在只有一个库，命令更透明。
    # Native layer (from R1 on): NDK clang builds one .so directly. No CMake yet -- there is a single library and an
    # explicit command line is easier to audit.
    toolchain = TOOLS / "ndk" / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64"
    clang = toolchain / "bin" / "clang.exe"
    native_src = sorted(str(p) for p in [(ANDROID / "jni" / "totk_jni.c")] + sorted((ROOT / "core").rglob("*.c")))
    so_dir = BUILD / "lib" / "arm64-v8a"
    so_dir.mkdir(parents=True, exist_ok=True)
    so = so_dir / "libtotkcore.so"
    if not clang.exists():
        raise SystemExit(f"缺少 NDK clang：{clang}")
    run([clang, "--target=aarch64-linux-android" + MIN_SDK, "-fPIC", "-shared", "-O2", "-Wall",
         "--sysroot", toolchain / "sysroot", "-o", so, *native_src, "-llog"],
        f"clang（{len(native_src)} 个源文件 → libtotkcore.so）")

    with zipfile.ZipFile(linked, "a") as z:
        z.write(dex, "classes.dex")                                     # dex 压缩即可 | the dex may be compressed
        z.write(so, "lib/arm64-v8a/libtotkcore.so", zipfile.ZIP_STORED)  # .so 必须不压缩，zipalign -p 才能直接映射 | the .so must be stored so zipalign -p can map it in place

    aligned = BUILD / "aligned.apk"
    run([BT / "zipalign.exe", "-f", "-p", "4", linked, aligned], "zipalign")

    out = BUILD / f"totk-app-{VERSION}.apk"
    if out.exists():
        out.unlink()
    run([BT / "apksigner.bat", "sign", "--ks", KEYSTORE, "--ks-pass", "pass:android",
         "--key-pass", "pass:android", "--ks-key-alias", "androiddebugkey",
         "--min-sdk-version", MIN_SDK, "--out", out, aligned], "apksigner sign")
    run([BT / "apksigner.bat", "verify", "--min-sdk-version", MIN_SDK, out], "apksigner verify")

    size = out.stat().st_size
    print(f"APK: {out}（{size} 字节）", flush=True)
    return out


if __name__ == "__main__":
    main()
