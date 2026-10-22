#!/usr/bin/env python3
"""TotK 数据包的一键部署：推包 → 导入 → 开机 → 读日志。

一条命令跑完原来要人手做的四段，每一段都打印真正执行的 adb 命令：
  1) 解析 adb（--adb > DM_ANDROID_TOOLS/platform-tools > 仓内/工作区约定路径 > PATH）；
  2) 推之前查外部存储与 /data 的剩余空间（<35 GiB 拦住，<40 GiB 警告）；
  3) 推包并核对手机上的字节数与本地一致；
  4) 把启动界面的状态写成 totk（否则界面按旧值选 D2R 的句柄表）；
  5) 打开启动界面、触发导入、等 manifest.json 出现、核对导入后的 counts；
  6) 点「启动游戏」、等 files/game.log 出现、把它拉回本机。

干跑（--dry-run）与真跑走的是**同一个 main()**：只有 adb 传输层把「执行」换成「打印」，
设备侧的返回值由 Adb.fake() 给出占位值，后续每一步的解析与判断照常执行。
干跑不会碰手机、不会写本机日志文件。

用法：
  # 先干跑（手机不在也能跑，exit 0 并原样打印 adb 命令）
  python dm/android/tools/deploy_totk.py --dry-run --package <数据包.zip>
  # 真跑（推到 /sdcard/Download/，导入要自己在启动界面选包）
  python dm/android/tools/deploy_totk.py --package <数据包.zip>
  # 真跑（推到应用外部目录的固定名，启动界面用「从推送的包导入」一键导入）
  python dm/android/tools/deploy_totk.py --package <数据包.zip> --dest fixed

退出码：0 = 走完；2 = 没有 adb / 没有设备；3 = 空间不够或空间查不出来；4 = 推送或字节校验失败；
       5 = 导入问题（超时或清单对不上）；6 = 没等到日志。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    # Windows 控制台默认 GBK；只改本进程输出编码，Linux/CI 上无行为变化。
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACKAGE = "org.d2r.android.port"
FIXED_NAME = "totk-package.zip"          # 启动界面固定路径导入找的就是这个名字
DOWNLOAD_DIR = "/sdcard/Download"        # SAF 能稳定读到的公共目录
APP_EXTERNAL = "/sdcard/Android/data/%s/files" % PACKAGE
LAUNCHER_ACTIVITY = PACKAGE + "/.LauncherActivity"
STATE_FILE = "files/launcher-state.conf"     # 启动界面自己的状态（game= / driver=）
SETTINGS_FILE = "files/temp/launch-settings.conf"   # native 严格解析的那份
DEVICE_TMP = "/data/local/tmp/totk-deploy.conf"
DEVICE_MANIFEST = "files/d2r-package/manifest.json"
GAME_LOG = "files/game.log"
MIN_FREE_GIB = 35.0                    # 包 16.60 GiB + 解出 16.47 GiB ≈ 33.1 GiB
WARN_FREE_GIB = 40.0
IMPORT_ROW = ("从推送的包导入", "Import the pushed package")
START_ROW = ("启动游戏", "Start game")
DRY_SERIAL = "DRYRUN01"
# 干跑时给 uiautomator dump 的占位窗口：两行控件的 bounds 是真跑要解析的那种格式。
# 启动行的文字带「▸  」前缀（LauncherActivity.java:364 的 "▸  " + text(...)），这里照真机写，
# 让干跑与真跑走同一套后缀匹配（见 row_centre）。
DRY_WINDOW_DUMP = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hierarchy rotation="0">'
    '<node text="" class="android.widget.FrameLayout" bounds="[0,0][2160,1800]">'
    '<node text="从推送的包导入" class="android.widget.TextView" clickable="true" bounds="[1200,600][2100,700]"/>'
    '<node text="▸  启动游戏" class="android.widget.TextView" clickable="true" bounds="[1200,900][2100,1000]"/>'
    '</node></hierarchy>'
)


class DeployError(Exception):
    """带退出码的失败：main() 只在这里打印一行，不打回溯。"""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class Result(object):
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout or ""


def adb_executable_name():
    return "adb.exe" if os.name == "nt" else "adb"


def adb_candidates(explicit=None, repo=None):
    """按优先级列候选 adb：显式参数 > DM_ANDROID_TOOLS > 仓内/工作区约定路径 > PATH。"""
    name = adb_executable_name()
    candidates = []
    if explicit:
        candidates.append((Path(explicit), "--adb"))
    tools = os.environ.get("DM_ANDROID_TOOLS")
    if tools:
        candidates.append((Path(tools) / "platform-tools" / name, "DM_ANDROID_TOOLS"))
    # 仓内约定路径：仓库根下的 .tools/ 与工作区根下的 .tools/（D:\Switch\.tools\android\platform-tools）。
    root = repo or Path(__file__).resolve().parents[3]
    for base in (root / ".tools" / "android", root.parent / ".tools" / "android"):
        candidates.append((base / "platform-tools" / name, "仓内约定路径"))
    which = shutil.which("adb") or shutil.which("adb.exe")
    if which:
        candidates.append((Path(which), "PATH"))
    return candidates


def resolve_adb(explicit=None, repo=None, dry_run=False):
    """返回 (可执行文件, 来源说明)。干跑找不到 adb 时退回 PATH 写法，不拦住干跑。"""
    candidates = adb_candidates(explicit, repo)
    for path, source in candidates:
        if path.is_file():
            return path, source
    if dry_run:
        print("[dry-run] 没找到 adb（真跑会在这里停下）；按 PATH 写法继续打印命令")
        return Path("adb"), "PATH（干跑占位）"
    raise DeployError("找不到 adb，已试过：" + "；".join("%s（%s）" % (p, s) for p, s in candidates), 2)


def shell_join(parts):
    """把命令行按人能直接复制的形式打出来（空格/引号一律加双引号）。"""
    def quote(part):
        part = str(part)
        return '"%s"' % part if re.search(r'[\s"]', part) else part
    return " ".join(quote(part) for part in parts)


class Adb(object):
    """adb 传输层：真跑执行，干跑只打印；两种模式用同一套调用。"""

    def __init__(self, executable, device=None, dry_run=False, package_size=0):
        self.executable = Path(executable)
        self.device = device
        self.dry_run = dry_run
        self.package_size = package_size
        self.commands = 0

    def command(self, args):
        parts = [str(self.executable)]
        if self.device:
            parts += ["-s", str(self.device)]
        return parts + [str(a) for a in args]

    def run(self, args, timeout=120, check=True):
        parts = self.command(args)
        text = shell_join(parts)
        self.commands += 1
        print(("[dry-run] " if self.dry_run else "$ ") + text, flush=True)
        if self.dry_run:
            return Result(0, self.fake(parts))
        try:
            proc = subprocess.run(parts, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DeployError("跑不起来：%s（%s）" % (text, error), 2)
        if check and proc.returncode != 0:
            raise DeployError("命令失败（exit %d）：%s\n%s" % (proc.returncode, text, (proc.stdout or "").strip()), 2)
        return Result(proc.returncode, proc.stdout)

    def shell(self, args, timeout=120, check=True):
        return self.run(["shell"] + [str(a) for a in args], timeout=timeout, check=check)

    def fake(self, parts):
        """干跑给设备侧的占位返回值：让后续解析/判断照常走一遍。"""
        body = parts[1:]
        if self.device and body[:1] == ["-s"]:
            body = body[2:]
        if not body:
            return ""
        if body[0] == "devices":
            return "List of devices attached\n%s\tdevice\n" % DRY_SERIAL
        if body[0] == "get-state":
            return "device\n"
        if body[:1] == ["shell"]:
            return self.fake_shell(body[1:])
        return ""

    def fake_shell(self, args):
        words = [str(a) for a in args]
        joined = " ".join(words)
        if words[:1] == ["df"]:
            return ("Filesystem 1K-blocks Used Available Use%% Mounted on\n"
                    "/dev/fuse 125829120 2097152 123731968 2%% %s\n" % (words[-1]))
        if words[:1] == ["stat"] and "%s" in words:
            return "%d\n" % self.package_size
        if words[:1] == ["wc"] and "-c" in words:
            return "%d %s\n" % (self.package_size, words[-1])
        if "uiautomator" in joined:
            return "UI hierchary dumped to: /sdcard/totk-window.xml\n"
        if words[:1] == ["cat"] and "totk-window.xml" in joined:
            return DRY_WINDOW_DUMP
        if "launcher-state.conf" in joined and words[:2] == ["run-as", PACKAGE]:
            return "# 仅供界面显示 | display only\npackage_summary=干跑占位\ndriver=system\ngame=d2r\n"
        if words[:1] == ["run-as"] and DEVICE_MANIFEST in joined and "cat" in words:
            return json.dumps(self.dry_manifest, ensure_ascii=False) + "\n" if self.dry_manifest else "{}\n"
        if words[:1] == ["run-as"] and DEVICE_MANIFEST in joined and "ls" in words:
            return DEVICE_MANIFEST + "\n"
        if words[:1] == ["run-as"] and GAME_LOG in joined:
            return "[dry-run] 占位日志：真跑这里就是 files/game.log 的内容\n"
        return ""

    dry_manifest = {}
    # 干跑的设备清单 = 本机包里的清单，这样 counts 比对这条代码路径也是真的在比。
    def set_dry_manifest(self, manifest):
        self.dry_manifest = manifest or {}


def parse_free_kib(text):
    """从 `df -k <路径>` 的输出里取 Available（KiB）。找不到返回 0。"""
    best = 0
    for line in (text or "").splitlines():
        fields = line.split()
        percent = [i for i, token in enumerate(fields) if re.fullmatch(r"\d+%", token)]
        if not percent or percent[0] < 1:
            continue
        index = percent[0]
        for candidate in (index - 1,):
            if candidate >= 0 and fields[candidate].isdigit():
                best = max(best, int(fields[candidate]))
    return best


def gib(kib):
    return kib / 1024.0 / 1024.0


DEVICE_STATES = ("device", "offline", "unauthorized", "recovery", "sideload", "bootloader")


def select_device(adb, explicit=None):
    """挑设备：--device 指定时直接用；否则 adb devices 里唯一那台。

    只认 `序列号<TAB>状态` 的行：adb 守护进程启动时会把
    `* daemon not running; starting now at tcp:5037` 这类横幅写到 stderr，
    而传输层把 stderr 并进 stdout —— 不滤掉就会被当成设备（真机首跑踩过）。
    """
    if explicit:
        adb.device = explicit
        # get-state 是 adb 的宿主机命令，不能走 `adb shell`（设备上没有它，真机首跑 exit 127）
        adb.run(["get-state"], check=True)
        return explicit
    listing = adb.run(["devices"]).stdout
    devices = []
    for line in listing.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of") or line.startswith("*"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip() in DEVICE_STATES:
            devices.append((parts[0].strip(), parts[1].strip()))
    if not devices:
        raise DeployError("adb devices 为空 —— 手机没接上（这是唯一的外部阻塞）", 2)
    if len(devices) > 1:
        raise DeployError("接了 %d 台设备（%s），用 --device 指定一台"
                          % (len(devices), ", ".join("%s(%s)" % (serial, state) for serial, state in devices)), 2)
    serial, state = devices[0]
    if state == "unauthorized":
        raise DeployError("%s 未授权 USB 调试：解锁手机，在「允许 USB 调试吗」弹窗点允许" % serial, 2)
    adb.device = serial
    adb.run(["get-state"], check=True)
    return serial


def check_space(adb, minimum_gib):
    """推之前查外部存储与 /data：导入时外部 ~33.1 GiB，内部再加 81.6 MB 的模块。"""
    free = {}
    for label, path in (("外部存储 /sdcard", "/sdcard"), ("/data", "/data")):
        result = adb.shell(["df", "-k", path], check=False)
        kib = parse_free_kib(result.stdout)
        if kib <= 0:
            # 解析不出数字与"真的满了"是两回事：前者该去查 shell/df，后者才该去清空间。
            raise DeployError("%s 的 df -k 没解析出剩余空间（exit %d，输出：%s）—— 先确认真机 shell 正常，"
                              "不要当成空间满" % (label, result.returncode,
                                                 (result.stdout or "").strip()[:200]), 3)
        free[label] = gib(kib)
        print("  %s 可用 %.1f GiB" % (label, free[label]))
        if free[label] < minimum_gib:
            raise DeployError("%s 只剩 %.1f GiB，少于最低 %.1f GiB —— 先清空间（导入要 ~33.1 GiB）"
                              % (label, free[label], minimum_gib), 3)
        if free[label] < WARN_FREE_GIB:
            print("  ! %s 低于建议的 %.1f GiB，导入会很挤" % (label, WARN_FREE_GIB))
    return free


def local_manifest(package, path_override=None):
    """读本地包的 manifest.json（覆盖式路径优先）；读不出来只警告，不当失败。"""
    if path_override:
        try:
            return json.loads(Path(path_override).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print("  ! 读 %s 失败：%s" % (path_override, error))
            return None
    try:
        started = time.time()
        with zipfile.ZipFile(str(package)) as archive:
            with archive.open("manifest.json") as stream:
                manifest = json.loads(stream.read().decode("utf-8"))
        print("  包内清单读出来了（%.1f 秒）：%s" % (time.time() - started, describe(manifest)))
        return manifest
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print("  ! 读包内 manifest.json 失败（不拦住，但导入后没法核对 counts）：%s" % error)
        return None


def describe(manifest):
    if not manifest:
        return "(无)"
    counts = manifest.get("counts", {})
    return "format=%s romfs=%s shaders=%s subgroup_size=%s" % (
        manifest.get("format"), counts.get("romfs"), counts.get("shaders"), manifest.get("subgroup_size"))


def push_package(adb, package, remote):
    size = package.stat().st_size
    print("  推 %s（%.2f GiB）→ %s" % (package.name, size / 2 ** 30, remote))
    adb.run(["push", str(package), remote], timeout=24 * 3600)
    return size


def verify_remote_size(adb, package, remote, expected):
    """推完核对手机上的字节数：`stat -c %s` 不行就退 `wc -c`。"""
    output = adb.shell(["stat", "-c", "%s", remote], check=False).stdout.strip()
    if not output.isdigit():
        output = adb.shell(["wc", "-c", remote], check=False).stdout.split()
        output = output[0] if output and output[0].isdigit() else ""
    if not output:
        raise DeployError("读不到手机上的字节数：%s" % remote, 4)
    actual = int(output)
    if actual != expected:
        raise DeployError("字节数不一致：本机 %d，手机 %d（%s）—— 重新推" % (expected, actual, remote), 4)
    print("  字节校验通过：本机与手机都是 %d 字节" % actual)
    return actual


def rewrite_key_value(text, updates):
    """保留未知行（界面自己写的其它键、注释）地改写 key=value。"""
    kept = []
    seen = set()
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            kept.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            kept.append("%s=%s" % (key, updates[key]))
            seen.add(key)
        else:
            kept.append(line)
    for key, value in updates.items():
        if key not in seen:
            kept.append("%s=%s" % (key, value))
    return "\n".join(kept) + "\n"


def push_internal_text(adb, text, remote_inside):
    """把一段文本写进应用内部目录：先推到 /data/local/tmp，再 run-as cp（应用目录对 adb 不开放）。"""
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".conf", delete=False)
    try:
        handle.write(text)
        handle.close()
        adb.run(["push", handle.name, DEVICE_TMP])
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
    adb.shell(["run-as", PACKAGE, "cp", DEVICE_TMP, remote_inside])
    adb.shell(["rm", "-f", DEVICE_TMP])


def force_profile(adb, profile, driver):
    """把启动界面的状态写成目标档位：界面点「启动游戏」时会用它重写 game_profile。

    这一步是防「跑成 D2R 句柄表」的最后一道闸：游戏档位记在界面自己的 launcher-state.conf 里，
    native 那份 launch-settings.conf 只会在点「启动游戏」时被界面重写，提前写也会被覆盖。
    """
    current = adb.shell(["run-as", PACKAGE, "cat", STATE_FILE], check=False).stdout
    updates = {"game": profile}
    if driver:
        updates["driver"] = driver
    push_internal_text(adb, rewrite_key_value(current, updates), STATE_FILE)
    # native 侧也写一份，万一先从别的入口启动，档位仍然是对的。
    settings = adb.shell(["run-as", PACKAGE, "cat", SETTINGS_FILE], check=False).stdout
    push_internal_text(adb, rewrite_key_value(settings, {"game_profile": profile}), SETTINGS_FILE)
    print("  游戏档位已锁到 %s%s" % (profile, ("，驱动 %s" % driver) if driver else ""))


def launcher_row(adb, texts, label, attempts=5):
    """在启动界面里按文字找到一行并点它；找不到返回 False（调用方降级成人工提示）。"""
    for attempt in range(attempts):
        adb.shell(["uiautomator", "dump", "/sdcard/totk-window.xml"], check=False)
        xml = adb.shell(["cat", "/sdcard/totk-window.xml"], check=False).stdout
        point = row_centre(xml, texts)
        if point:
            adb.shell(["input", "tap", point[0], point[1]])
            return True
        if attempt + 1 < attempts:
            print("  等启动界面画出来（第 %d 次没找到「%s」）..." % (attempt + 1, label))
            time.sleep(3)
    return False


def row_centre(xml, texts):
    """从 uiautomator dump 里取匹配文字那行 bounds 的中心点。

    按后缀匹配而不是全等：启动行在界面上带「▸  」前缀（LauncherActivity.java:364），
    全等会在真机上静默失配、把自动化降级成人工点。已核对启动界面其余行
    （导入数据包 / 游戏 / 分辨率 / 驱动 / 存档导入导出 / 待导入提示）的后缀都不与目标撞车。
    """
    if not xml or "<hierarchy" not in xml:
        return None
    for node in re.finditer(r"<node\b[^>]*>", xml):
        tag = node.group(0)
        text = re.search(r'\btext="([^"]*)"', tag)
        bounds = re.search(r'\bbounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if not text or not bounds:
            continue
        shown = text.group(1).strip()
        if not any(shown.endswith(want) for want in texts):
            continue
        left, top, right, bottom = (int(bounds.group(i)) for i in range(1, 5))
        return (str((left + right) // 2), str((top + bottom) // 2))
    return None


def wait_for(adb, probe, what, timeout, interval=10, extra=None):
    """轮询一条 adb 探测，直到成功或超时；干跑第一次就成功（fake 已经给足返回值）。"""
    started = time.time()
    while True:
        result = probe()
        if result:
            print("  %s（等了 %.0f 秒）" % (what, time.time() - started))
            return result
        if time.time() - started > timeout:
            raise DeployError("%s 等了 %d 秒还没出现" % (what, timeout), extra)
        print("  ... 还在等 %s（%.0f 秒）" % (what, time.time() - started), flush=True)
        time.sleep(interval)


def import_manifest(adb):
    result = adb.shell(["run-as", PACKAGE, "ls", DEVICE_MANIFEST], check=False)
    return DEVICE_MANIFEST if result.returncode == 0 and result.stdout.strip() else None


def game_log_text(adb):
    result = adb.shell(["run-as", PACKAGE, "cat", GAME_LOG], check=False)
    return result.stdout if result.returncode == 0 and result.stdout.strip() else None


def check_imported_manifest(adb, expected):
    """导入完成后拿手机上的清单与本地包对一遍：抓的就是「推成基座包了」这类低级错误。"""
    raw = adb.shell(["run-as", PACKAGE, "cat", DEVICE_MANIFEST], check=False).stdout
    try:
        start = raw.index("{")
        actual = json.loads(raw[start:])
    except (ValueError, KeyError) as error:
        print("  ! 手机上的清单读不出 JSON：%s" % error)
        return None
    print("  手机上的清单：%s" % describe(actual))
    if not expected:
        return actual
    for key in ("format", "subgroup_size"):
        if expected.get(key) != actual.get(key):
            raise DeployError("清单 %s 不一致：本机 %s，手机 %s —— 包推错了？"
                              % (key, expected.get(key), actual.get(key)), 5)
    for key in ("game", "romfs", "shaders"):
        want = expected.get("counts", {}).get(key)
        got = actual.get("counts", {}).get(key)
        if want != got:
            raise DeployError("清单 counts.%s 不一致：本机 %s，手机 %s —— 推错包了？"
                              % (key, want, got), 5)
    print("  counts 与本地包一致 ✓")
    return actual


def save_log(text, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print("  日志已落盘：%s（%d 行）" % (destination, len(text.splitlines())))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", type=Path, required=True, help="数据包 zip | the data package")
    parser.add_argument("--profile", default="totk", help="游戏档位（totk / d2r）| the game profile")
    parser.add_argument("--driver", default="turnip", choices=("turnip", "system"),
                        help="界面里的驱动档位 | the driver row in the launcher")
    parser.add_argument("--device", help="adb 设备序列号 | the adb device serial")
    parser.add_argument("--adb", help="显式指定 adb 可执行文件 | explicit adb path")
    parser.add_argument("--dest", choices=("download", "fixed"), default="download",
                        help="推到 /sdcard/Download/（默认，SAF 读得到）或应用外部目录的固定名 | where to push")
    parser.add_argument("--external", help="覆盖推送目录 | override the remote directory")
    parser.add_argument("--no-push", action="store_true", help="不推包，直接用手机上已有的 zip | keep the pushed zip")
    parser.add_argument("--no-import", action="store_true", help="推完就停，导入自己点 | stop after the push")
    parser.add_argument("--no-boot", action="store_true", help="导入完就停，开机自己点 | stop after the import")
    parser.add_argument("--log-out", type=Path, help="把 files/game.log 落到本机这个路径 | where to save game.log")
    parser.add_argument("--manifest", type=Path, help="用这份 manifest.json 对 counts（跳过读 zip）| use this manifest")
    parser.add_argument("--min-free-gib", type=float, default=MIN_FREE_GIB,
                        help="推之前要求的最低剩余空间（GiB）| minimum free space")
    parser.add_argument("--import-timeout", type=int, default=180 * 60, help="导入超时（秒）| import timeout")
    parser.add_argument("--boot-timeout", type=int, default=300, help="等 game.log 的超时（秒）| boot timeout")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印要执行的 adb 命令，不碰手机 | print the adb commands and touch nothing")
    args = parser.parse_args()

    if not args.package.is_file():
        raise DeployError("数据包不存在：%s" % args.package, 2)
    package_size = args.package.stat().st_size
    manifest = local_manifest(args.package, args.manifest)

    print("== TotK 一键部署%s ==" % ("（干跑：只打印，不碰手机）" if args.dry_run else ""))
    executable, source = resolve_adb(args.adb, dry_run=args.dry_run)
    print("adb：%s（来自 %s）" % (executable, source))

    adb = Adb(executable, dry_run=args.dry_run, package_size=package_size)
    adb.set_dry_manifest(manifest or {})
    serial = select_device(adb, args.device)
    print("设备：%s" % serial)

    if args.external:
        remote = args.external.rstrip("/") + "/" + args.package.name
        import_mode = "saf"
    elif args.dest == "fixed":
        remote = "%s/%s" % (APP_EXTERNAL, FIXED_NAME)
        import_mode = "fixed"
    else:
        remote = "%s/%s" % (DOWNLOAD_DIR, args.package.name)
        import_mode = "saf"

    print("-- 1/6 推之前的空间闸门 --")
    check_space(adb, args.min_free_gib)

    if args.no_push:
        print("-- 1/6 跳过推送（--no-push）：假定手机上已有 %s --" % remote)
    else:
        print("-- 1/6 推包 --")
        push_package(adb, args.package, remote)
        verify_remote_size(adb, args.package, remote, package_size)

    print("-- 2/6 档位锁定 --")
    force_profile(adb, args.profile, args.driver)

    print("-- 3/6 打开启动界面 --")
    adb.shell(["am", "start", "-n", LAUNCHER_ACTIVITY])

    if args.no_import:
        print("-- 4/6 跳过导入（--no-import）：在启动界面点「导入数据包」选 %s --" % remote)
        return 0

    print("-- 4/6 导入 --")
    if import_mode == "fixed":
        print("  目标是应用外部目录的固定名，走界面的「从推送的包导入」")
        if not launcher_row(adb, IMPORT_ROW, IMPORT_ROW[0]):
            print("  ! 没能在界面上找到「%s」，请自己点这一行；脚本继续等 manifest.json" % IMPORT_ROW[0])
    else:
        print("  包在 %s —— SAF 选择器请自己选这个文件（脚本等 manifest.json）" % remote)
    wait_for(adb, lambda: import_manifest(adb), "导入完成（files/d2r-package/manifest.json）",
             args.import_timeout, extra=5)
    check_imported_manifest(adb, manifest)

    if args.no_boot:
        print("-- 5/6 跳过开机（--no-boot）：在启动界面点「启动游戏」--")
        return 0

    print("-- 5/6 开机 --")
    if not launcher_row(adb, START_ROW, START_ROW[0]):
        print("  ! 没能在界面上找到「%s」，请自己点这一行；脚本继续等 files/game.log" % START_ROW[0])
    text = wait_for(adb, lambda: game_log_text(adb), "游戏日志 files/game.log",
                    args.boot_timeout, interval=5, extra=6)

    print("-- 6/6 读日志 --")
    for line in [line for line in text.splitlines() if line.strip()][-12:]:
        print("  | " + line)
    if "DM_GAME_PROFILE=%s" % args.profile in text:
        print("  游戏档位在日志里确认为 %s ✓" % args.profile)
    else:
        print("  ! 日志里没找到 DM_GAME_PROFILE=%s —— 对照「首次开机预演清单」第 6 条怀疑项" % args.profile)
    if args.log_out and not args.dry_run:
        save_log(text, args.log_out)
    elif args.log_out:
        print("  [dry-run] 不落盘：%s" % args.log_out)
    print("== 完成：共执行 %d 条 adb 命令 ==" % adb.commands)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeployError as error:
        print("✗ %s" % error, file=sys.stderr)
        raise SystemExit(error.code)
