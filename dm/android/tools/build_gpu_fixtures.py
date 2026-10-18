#!/usr/bin/env python3
"""从当前源码构建可放进APK nativeLibraryDir的真实GPU诊断ELF，不运行设备。
Build real GPU diagnostic ELFs for APK nativeLibraryDir from current sources, without running a device.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import os
import shlex
import subprocess
import sys
from host_env import HOST_TAG, file_lock, tool

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get("DM_ANDROID_TOOLS", str(Path.home() / "dm-work/tools/android")))
BIN = TOOLS / "ndk/toolchains/llvm/prebuilt" / HOST_TAG / "bin"
CLANG = tool(BIN / "aarch64-linux-android29-clang")


def build(output):
    output.mkdir(parents=True,exist_ok=True)
    with file_lock(output / ".build.lock"):
        subprocess.run([sys.executable,str(ROOT / "tools/build_gpu_driver.py")],check=True)
        subprocess.run([sys.executable,str(ROOT / "tools/prepare_gpu_test.py"),
                        str(ROOT / "build/gpu-test-shaders"),str(tool(TOOLS / "ndk/shader-tools" / HOST_TAG / "glslc"))],check=True)
        native=ROOT / "native"
        targets={
            "libdmgpudriverprobe.so": [ROOT / "tests/gpu_driver_properties.c",native / "gpu_driver.c"],
            "libdmgputestprobe.so": [ROOT / "tests/vulkan_test.c",native / "legacy_digest.c",native / "pending_ranges.c",native / "gpu_driver.c",
                                    ROOT.parent / "gfx/nvn/nvn_tex.c",ROOT.parent / "gfx/tex/nvn_deswizzle.c"],
        }
        records=[]
        for name,sources in targets.items():
            directory=output / name.removesuffix(".so")
            directory.mkdir(exist_ok=True)
            compile_commands=[]

            def compile_file(source):
                obj=directory / (source.stem+".o")
                deps,stamp=obj.with_suffix(".d"),obj.with_suffix(".cmd")
                command=[str(CLANG),"-c","-O3","-fPIE","-fno-strict-aliasing","-fno-omit-frame-pointer","-g",
                         "-Wall","-Wextra","-MMD","-MF",str(deps),
                         "-I",str(ROOT.parent / "host"),"-I",str(native),"-I",str(native / "compat"),
                         "-I",str(ROOT.parent / "gfx/nvn/include"),"-I",str(ROOT / "build/gpu-driver/include"),
                         str(source),"-o",str(obj)]
                recorded=json.dumps(command)
                if obj.exists() and deps.exists() and stamp.exists() and stamp.read_text(encoding="utf-8")==recorded:
                    paths=shlex.split(deps.read_text(encoding="utf-8").split(":",1)[1].replace("\\\n"," "))
                    if all(Path(p).exists() and Path(p).stat().st_mtime<=obj.stat().st_mtime for p in paths):
                        return obj,command
                result=subprocess.run(command,capture_output=True,text=True, encoding="utf-8", errors="replace")
                (directory / (source.stem+".log")).write_text(result.stdout+result.stderr, encoding="utf-8")
                if result.returncode:
                    raise RuntimeError("GPU fixture compile failed: "+str(source)+"\n"+result.stderr)
                stamp.write_text(recorded, encoding="utf-8")
                return obj,command

            with ThreadPoolExecutor(max_workers=4) as pool:
                compiled=list(pool.map(compile_file,sources))
            objects=[obj for obj,_ in compiled]
            compile_commands=[cmd for _,cmd in compiled]
            binary=output / name
            command=[str(CLANG),"-pie","-Wl,-z,defs","-Wl,-z,max-page-size=16384",
                     *map(str,objects),"-landroid","-llog","-ldl","-lm","-o",str(binary)]
            stamp=binary.with_suffix(".cmd")
            recorded=json.dumps(command)
            if not (binary.exists() and stamp.exists() and stamp.read_text(encoding="utf-8")==recorded
                    and all(p.stat().st_mtime<=binary.stat().st_mtime for p in objects)):
                result=subprocess.run(command,capture_output=True,text=True, encoding="utf-8", errors="replace")
                (output / (name+"-link.log")).write_text(result.stdout+result.stderr, encoding="utf-8")
                if result.returncode:
                    raise RuntimeError("GPU fixture link failed: "+name+"\n"+result.stderr)
                stamp.write_text(recorded, encoding="utf-8")
            records.append({"binary":str(binary),"source_files":[str(p) for p in sources],
                            "compile_commands":compile_commands,"link_command":command,
                            "pie":True,"max_page_size":16384,"device_executed":False})
        (output / "build.json").write_text(json.dumps(records,indent=2)+"\n", encoding="utf-8")
        print("GPU diagnostic PIE ELFs:",", ".join(targets),flush=True)
        return [output / name for name in targets]


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT / "build/gpu-fixtures")
    build(parser.parse_args().output)
