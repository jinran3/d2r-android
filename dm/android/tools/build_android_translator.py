#!/usr/bin/env python3
"""单独构建 Android 口径的着色器翻译器（dmsh_android.dll）。

D2R 的 Android 管线不用 `dm/gfx/tools/dmsh_xlate` 那个翻译器，而是从同一份源再注入四处：
每阶段独立描述符集、按作业给的 host 子组尺寸、只声明 Android 真启用的能力（无 fp64、无片元着色器互锁），
再加 c[2] 句柄表区间（按作业给，D2R 缺省不变）。TotK 也必须用这个口径：
桌面那个翻译器默认按 32 宽子组编译，而一加 12 的子组是 64。

用法：build_android_translator.py --out <输出目录> [--dotnet <dotnet 可执行文件>]
产物：<输出目录>/dmsh_android.dll 与 translation-api.json（能力与源码指纹）。
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_shaders


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="输出目录 | the output directory")
    parser.add_argument("--dotnet", type=Path, default=None, help="dotnet 可执行文件 | the dotnet executable")
    args = parser.parse_args()
    dotnet = args.dotnet or Path(os.environ.get("DM_DOTNET", "")) or None
    if dotnet is None:
        for candidate in (Path.home() / "dm-work/tools/dotnet/dotnet", Path("D:/Switch/totk-work/tools/dotnet/dotnet.exe")):
            if candidate.is_file():
                dotnet = candidate
                break
    if dotnet is None:
        raise SystemExit("找不到 dotnet：给 --dotnet 或设 DM_DOTNET")
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "work"
    work.mkdir(parents=True, exist_ok=True)
    tool = build_shaders.translator(dotnet, work)
    print("Android 翻译器：%s" % tool)
    print("能力：%s" % (work / "translator-bin" / "translation-api.json").read_text(encoding="utf-8").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
