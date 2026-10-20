#!/usr/bin/env python3
"""TotK 着色器的翻译作业流水线：索引 → 事实 → 作业 → SPIR-V → 统计。

输入是 `dm/gfx/tools/totk_shaders.py` 产出的索引（`shader_index.tsv`）与机器码目录
（`code/<键>.bin`）。作业格式与 D2R 侧 `dm/gfx/tools/dmsh_build.py` 完全一致，
翻译器是同一个 `dm/gfx/tools/dmsh_xlate`（Ryujinx.Graphics.Shader）。

三处 TotK 专属的约定（都在作业里显式声明，翻译器据此作答）：

* **机器码要带 SPH**：图形着色器的机器码区前 0x30 字节是 SPH（描述符头）。
  少了它，翻译器读不到描述符，9,807 个键里有 3 个会抛 `IndexOutOfRangeException`
  （实测：去掉 SPH → 3 失败；带上 SPH → 3 个全过）。D2R 侧同一约定（`code[0x30:]`）。
* **深度 -1..1**：TotK 用 `nvnDeviceSetDepthMode(-1..1)`（D2R 是 0..1）。
* **宿主能力**：TotK 的着色器用到 fp64 与深度裁剪控制，Vulkan / Metal 都不支持，
  翻译器据此降级。

事实（贴图维度类型 / 图像格式 / 属性与输出的分量类型）目前**没有来源**：D2R 的
`dm/gfx/nvn/shader_facts.tsv` 是从 PC 版 DXBC 反射冻结的，TotK 没有 PC 版。
本工具按计划 §4.4 的**方案 A** 作答：能给的给（计算着色器的线程组与共享内存来自
控制头 0x748），其余按缺省，并把缺省覆盖的键数写进报告。若以后从游戏数据或运行期
观测（`nvnTextureBuilderSetDims` / `SetFormat`）拿到事实，用 `--facts` 传进来即可，
键名与 D2R 的表一致。

用法：
  totk_xlate.py --index <shader_index.tsv> --code <机器码目录> --work <工作目录>
                [--facts <事实表.tsv>] [--write-facts <事实表输出路径>]
                [--xlate <dmsh_xlate.dll|exe>] [--dotnet <dotnet.exe>]
                [--shards 6] [--jobs-only] [--no-run]

产物（<工作目录>）：`jobs<N>.json`、`out<N>/<键>.spv`、`xlate_report.tsv`。
**产物与事实表都在仓库外**：着色器与由它生成的东西不进仓库。

TotK shader translation pipeline: index → facts → jobs → SPIR-V → report.
The job format is the same as the D2R side (dm/gfx/tools/dmsh_build.py) and the
translator is the same (dm/gfx/tools/dmsh_xlate). Three TotK-specific conventions are
declared per job: the machine code keeps the 0x30-byte SPH (without it 3 of the 9,807
keys throw IndexOutOfRangeException; with it all three pass), the depth range is -1..1,
and the host declares no fp64 / no depth clip control.
The facts (texture dimension types, image formats, attribute and output component types)
have no source yet: D2R's dm/gfx/nvn/shader_facts.tsv was frozen from the PC build's
DXBC reflection and TotK has no PC build. This tool answers per plan §4.4 option A:
give what the archives do carry (compute thread group and shared memory from control
header 0x748) and default the rest, counting the defaulted keys in the report. Facts
recovered later (from game data or run-time observation) can be fed in with --facts.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

JOB_DEFAULTS = {
    "tex": {}, "img": {}, "attr": {}, "fout": {},
    "debug": True, "reduced": True,
    "depth_minus_one_to_one": True,      # TotK 的深度是 -1..1（D2R 是 0..1） | TotK's depth is -1..1
    "host_no_fp64": True,                # 宿主不支持 fp64 | the host has no fp64
    "host_no_depth_clip": True,          # 宿主不支持深度裁剪控制 | the host has no depth clip control
    # 这三项只有 Android 口径的翻译器认（dm/android/tools/build_shaders.py 的模板）：桌面那个翻译器
    # 忽略它们，所以拿它译出来的 SPIR-V 会按 32 宽子组、所有绑定挤在第 0 组 —— 一加 12 的子组是 64，
    # 顶点与片元的绑定号还会互相撞车。TotK 必须用 Android 口径的翻译器。
    # Only the Android-shaped translator honours these three (the template in
    # dm/android/tools/build_shaders.py); the desktop one ignores them, so its SPIR-V assumes a 32-wide
    # subgroup and puts every binding in set 0 - and the OnePlus 12 has a 64-wide subgroup while the
    # vertex and fragment binding numbers collide in one set.
    "host_subgroup_size": 64,            # 一加 12 实测的子组尺寸 | the subgroup size measured on the phone
    "set": 0,                            # 每阶段独立描述符集（下面按阶段填）| a descriptor set per stage (filled per stage below)
    "c2_tex_base": 0x20,                 # c[2] 合并贴图句柄表的基址 | the base of the combined texture handle table
    "c2_tex_end": 0x120,                 # 合并贴图句柄表的上界 | the end of the combined texture handle table
}

# 每阶段独立描述符集，避免顶点与片元的绑定号互相碰撞（与 D2R 的 Android 管线同一约定）。
# A descriptor set per stage, so the vertex and fragment binding numbers do not collide (the same
# convention as the D2R Android pipeline).
STAGE_SET = {"vs": 0, "ps": 1, "gs": 2, "hs": 3, "ds": 4, "cs": 0}


def read_index(path: Path) -> list:
    """读 totk_shaders.py 的索引 TSV → 记录列表 | read the index TSV → list of records"""
    rows = []
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            if not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            r = dict(zip(header, c))
            r["local"] = None if r.get("local", "-") in ("-", "") else [int(v) for v in r["local"].split("x")]
            r["shared"] = int(r.get("shared", 0) or 0)
            rows.append(r)
    return rows


def read_facts(path: Path) -> dict:
    """读事实表（键 <TAB> JSON，与 D2R 的 nvn/shader_facts.tsv 同格式） | read a fact table (key <TAB> JSON, same format as the D2R table)"""
    facts = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t", 1)
            if len(c) == 2:
                facts[c[0]] = json.loads(c[1])
    return facts


def facts_row(facts: dict) -> str:
    """事实表的一行（紧凑 JSON，键按字典序） | one fact-table row (compact JSON, keys sorted)"""
    return json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_job(rec: dict, code_dir: Path, facts: dict) -> dict:
    """一条记录 → 一个作业 | one record → one job"""
    job = {"key": rec["key"], "stage": rec["stage"], "code": str(code_dir / (rec["key"] + ".bin"))}
    extra = facts.get(rec["key"], {})
    job.update(JOB_DEFAULTS)
    job["set"] = STAGE_SET.get(rec["stage"], 0)
    for field in ("tex", "img", "attr", "fout"):
        if extra.get(field):
            job[field] = extra[field]
    if rec["stage"] == "cs":
        job["local"] = rec["local"] or [1, 1, 1]
        job["shared"] = rec["shared"]
    if rec.get("c1"):
        job["c1"] = rec["c1"]
    return job


def write_facts(records: list, path: Path) -> int:
    """写事实表（只写有事实的键；其余按缺省作答）→ 行数 | write the fact table (only keys that carry facts) → row count"""
    rows = []
    for rec in records:
        if rec["stage"] != "cs":
            continue
        facts = {"tex": {}, "img": {}, "attr": {}, "fout": {},
                 "local": rec["local"] or [1, 1, 1], "shared": rec["shared"]}
        rows.append(rec["key"] + "\t" + facts_row(facts))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# TotK 翻译查询的作答表（totk_xlate.py --write-facts 生成；不在仓库里）：键 <TAB> 事实 JSON\n"
                    + "".join(r + "\n" for r in sorted(rows)), encoding="utf-8")
    return len(rows)


def run_shard(args, shard: int, jobs_path: Path, out_dir: Path) -> tuple:
    """跑一个分片 → (分片号, 成功键列表, 失败键→错误) | run one shard → (shard, ok keys, failures)"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = []
    if args.xlate.suffix.lower() == ".dll":
        cmd = [args.dotnet, str(args.xlate), str(jobs_path), str(out_dir)]
    else:
        cmd = [str(args.xlate), str(jobs_path), str(out_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = sorted(p.stem for p in out_dir.glob("*.spv"))
    failed = {}
    for line in (proc.stdout or "").splitlines():
        m = re.match(r"【红】([0-9a-f]{16})：(.*)", line.strip())
        if m:
            failed[m.group(1)] = m.group(2).strip()
    return shard, ok, failed, proc.returncode, (proc.stdout or "")[-400:], (proc.stderr or "")[-400:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", type=Path, required=True, help="totk_shaders.py 产出的 shader_index.tsv | the index TSV")
    ap.add_argument("--code", type=Path, required=True, help="机器码目录（code/<键>.bin，含 SPH） | the machine-code dir (with the SPH)")
    ap.add_argument("--work", type=Path, required=True, help="工作目录（作业、产物、报告） | the work dir")
    ap.add_argument("--facts", type=Path, help="事实表（键 <TAB> JSON） | the fact table")
    ap.add_argument("--write-facts", type=Path, help="把本次的事实表写到这里 | write the fact table here")
    ap.add_argument("--xlate", type=Path, default=Path(os.environ.get("DM_XLATE", "dmsh_xlate.dll")), help="翻译器 dll / 可执行文件 | the translator")
    ap.add_argument("--dotnet", type=Path, default=Path(os.environ.get("DOTNET", "dotnet")), help="dotnet 可执行文件 | the dotnet executable")
    ap.add_argument("--shards", type=int, default=6, help="并行分片数 | number of parallel shards")
    ap.add_argument("--jobs-only", action="store_true", help="只写作业，不跑翻译 | write the jobs only")
    ap.add_argument("--no-run", action="store_true", help="不跑翻译（等价于 --jobs-only） | do not run the translator")
    args = ap.parse_args()

    records = read_index(args.index)
    facts = read_facts(args.facts) if args.facts else {}
    args.work.mkdir(parents=True, exist_ok=True)
    if args.write_facts:
        n = write_facts(records, args.write_facts)
        print("事实表：%s（%d 键有事实，其余按缺省作答）" % (args.write_facts, n))

    jobs = [build_job(rec, args.code, facts) for rec in records]
    shards = max(1, args.shards)
    buckets = [jobs[i::shards] for i in range(shards)]
    paths = []
    for i, bucket in enumerate(buckets):
        p = args.work / ("jobs%d.json" % i)
        p.write_text(json.dumps(bucket, ensure_ascii=False), encoding="utf-8")
        paths.append(p)
    print("作业：%d 条，分 %d 片，写在 %s" % (len(jobs), shards, args.work))
    if args.jobs_only or args.no_run:
        return 0

    ok_all, failed, problems = [], {}, []
    with ThreadPoolExecutor(max_workers=shards) as pool:
        futures = [pool.submit(run_shard, args, i, paths[i], args.work / ("out%d" % i)) for i in range(shards)]
        for fut in futures:
            shard, ok, bad, code, tail, err = fut.result()
            ok_all.extend(ok)
            failed.update(bad)
            if code != 0:
                problems.append("分片 %d 退出码 %d：%s %s" % (shard, code, tail.strip(), err.strip()))
            print("分片 %d：成功 %d，失败 %d" % (shard, len(ok), len(bad)))
    ok_all = sorted(set(ok_all))
    report = args.work / "xlate_report.tsv"
    with report.open("w", encoding="utf-8") as f:
        f.write("key\tstage\tresult\tdetail\n")
        for rec in records:
            key = rec["key"]
            if key in failed:
                f.write("%s\t%s\tFAIL\t%s\n" % (key, rec["stage"], failed[key]))
            else:
                f.write("%s\t%s\tOK\t\n" % (key, rec["stage"]))
    defaulted = len(records) - len([k for k in facts if k in {r["key"] for r in records}])
    print("翻译：%d 个键，成功 %d，失败 %d；按缺省作答的键 %d" % (len(records), len(ok_all), len(failed), defaulted))
    if failed:
        print("失败键（最多 20 个）：%s" % ", ".join(sorted(failed)[:20]))
    for p in problems:
        print("【红】" + p)
    print("报告：%s" % report)
    return 1 if (failed or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
