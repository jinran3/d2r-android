#!/usr/bin/env python3
"""Synthetic regression for the one-command TotK deploy (push -> import -> boot -> log).

覆盖 NA-052 的验收点：干跑 exit 0 且原样打印 adb 命令、干跑与真跑同一条 main()、
行匹配容忍「▸  」前缀、df 解析、字节校验失败与空间不足两条负路、adb 解析优先级、
手机没接上的报错。全部用合成包与假 Adb，不碰真机。
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY / "dm" / "android" / "tools"))
import deploy_totk as dt


class StubAdb(object):
    """按脚本给的回放假 Adb：shell/run 直接返回预定输出，不 subprocess。"""

    def __init__(self, script=None):
        self.script = script or {}
        self.calls = []

    def run(self, args, timeout=120, check=True):
        self.calls.append(list(args))
        key = " ".join(str(a) for a in args)
        for prefix, value in self.script.items():
            if key.startswith(prefix):
                return dt.Result(0, value)
        return dt.Result(0, "")

    def shell(self, args, timeout=120, check=True):
        return self.run(["shell"] + [str(a) for a in args], timeout=timeout, check=check)


def build_package(path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        manifest = {
            "format": 1,
            "created": "2026-01-01T00:00:00Z",
            "source": "synthetic",
            "subgroup_size": 64,
            "counts": {"game": 3, "romfs": 5, "shaders": 7},
            "bytes": {"game": 3, "romfs": 5, "shaders": 7},
        }
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("game/libdmguest_main.so", b"g")
        archive.writestr("romfs/a.txt", b"r")


def run_main(argv):
    """在进程内跑 main()（与 __main__ 同一条代码路径），抓 stdout。

    DeployError 由调用方转成退出码 —— 与模块底部 __main__ 守卫同一套行为。
    """
    old_argv = sys.argv
    sys.argv = ["deploy_totk.py"] + argv
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            try:
                code = dt.main()
            except dt.DeployError as error:
                code = error.code
                print("✗ %s" % error, file=sys.stderr)
    finally:
        sys.argv = old_argv
    return code, buffer.getvalue()


def test_dry_run_same_path():
    """干跑 exit 0，原样打印 adb 命令，且与真跑是同一个 main()（没有第二个入口）。"""
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "totk-package.zip"
        build_package(package)
        code, out = run_main(["--dry-run", "--package", str(package)])
        assert code == 0, out
        # 原样打印：每条都是能直接复制的 adb 命令行
        assert "[dry-run] " in out and "$ " not in out
        for fragment in (
            "push %s /sdcard/Download/totk-package.zip" % package,
            "shell stat -c %s /sdcard/Download/totk-package.zip",
            "shell am start -n org.d2r.android.port/.LauncherActivity",
            "shell run-as org.d2r.android.port cat files/game.log",
            "shell input tap",
        ):
            assert fragment in out, "缺命令片段：%s\n%s" % (fragment, out)
        # 干跑也必须真的走完字节校验与 counts 比对（fake 返回值参与了判断）
        assert "字节校验通过" in out and "counts 与本地包一致" in out
        assert "共执行 22 条 adb 命令" in out


def test_dry_run_fixed_dest():
    """--dest fixed 推到应用外部目录的固定名，并点「从推送的包导入」那一行。"""
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "totk-package.zip"
        build_package(package)
        code, out = run_main(["--dry-run", "--dest", "fixed", "--package", str(package)])
        assert code == 0, out
        assert "/sdcard/Android/data/org.d2r.android.port/files/totk-package.zip" in out
        assert "shell input tap 1650 650" in out, out  # 「从推送的包导入」行的中心点
        assert "共执行 25 条 adb 命令" in out, out  # 比 download 模式多点一次 dump+cat+tap


def test_row_centre_tolerates_prefix():
    """启动行带「▸  」前缀也要匹配上；别的行不能误匹配。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node text="▸  启动游戏" class="android.widget.TextView" bounds="[100,200][300,400]"/>'
        '<node text="导入数据包：未设置" class="android.widget.TextView" bounds="[0,0][9,9]"/>'
        '<node text="从推送的包导入" class="android.widget.TextView" bounds="[10,20][30,40]"/>'
        "</hierarchy>"
    )
    assert dt.row_centre(xml, dt.START_ROW) == ("200", "300")
    assert dt.row_centre(xml, dt.IMPORT_ROW) == ("20", "30")
    # 英文行（无前缀时全等也成立）
    assert dt.row_centre('<hierarchy><node text="Start game" bounds="[0,0][10,10]"/></hierarchy>',
                         dt.START_ROW) == ("5", "5")
    assert dt.row_centre("<hierarchy></hierarchy>", dt.START_ROW) is None


def test_launcher_row_scrolls():
    """行在屏幕外时要滚一屏再找（真机 3168×1440 横屏，导入行在「游戏」行以下就被截断）。

    uiautomator dump 只含可见节点 —— 首跑就是因此没找到「从推送的包导入」。
    """
    top_only = ('<hierarchy><node text="" bounds="[0,0][1000,500]"/>'
                '<node text="▸  启动游戏" bounds="[0,0][100,50]"/></hierarchy>')
    bottom_only = ('<hierarchy><node text="" bounds="[0,0][1000,500]"/>'
                   '<node text="从推送的包导入" bounds="[100,200][300,300]"/></hierarchy>')

    class Seq(StubAdb):
        def __init__(self, dumps):
            super().__init__()
            self.dumps = list(dumps)

        def run(self, args, timeout=120, check=True):
            self.calls.append(list(args))
            if list(args[:2]) == ["shell", "cat"] and any("totk-window.xml" in str(a) for a in args):
                return dt.Result(0, self.dumps.pop(0) if self.dumps else "")
            return dt.Result(0, "")

    # 导入行在下方：先 dump 找不到 → 往下滚 → 找到并点击
    adb = Seq([top_only, bottom_only])
    assert dt.launcher_row(adb, dt.IMPORT_ROW, "导入") is True
    swipes = [c for c in adb.calls if list(c[:3]) == ["shell", "input", "swipe"]]
    assert len(swipes) == 1, adb.calls
    assert int(swipes[0][4]) > int(swipes[0][6]), swipes  # down: 从下往上滑（y1 > y2）
    # 启动行在上方：往反方向滚
    adb = Seq([bottom_only, top_only])
    assert dt.launcher_row(adb, dt.START_ROW, "启动", direction="up") is True
    swipes = [c for c in adb.calls if list(c[:3]) == ["shell", "input", "swipe"]]
    assert len(swipes) == 1 and int(swipes[0][4]) < int(swipes[0][6]), swipes  # up: y1 < y2
    # 屏幕尺寸从 dump 根节点取
    assert dt.screen_size(top_only) == (1000, 500)
    assert dt.screen_size("") == (0, 0)


def test_parse_free_kib():
    """按真机 df 的形态取 Available；表头与解析不出的行不能污染结果。"""
    real = ("Filesystem     1K-blocks    Used Available Use% Mounted on\n"
            "/dev/fuse       125829120  2097152  123731968   2% /storage/emulated\n")
    assert dt.parse_free_kib(real) == 123731968
    assert dt.parse_free_kib("Filesystem 1K-blocks Used Available Use% Mounted on\n") == 0
    assert dt.parse_free_kib("") == 0
    assert dt.parse_free_kib("tmpfs 0 0 - - /tmp\n") == 0


def test_verify_remote_size_mismatch():
    """手机上的字节数不一致 → DeployError(4)，消息里两个数都写出来。"""
    adb = StubAdb({"shell stat -c %s": "123\n"})
    try:
        dt.verify_remote_size(adb, Path("x.zip"), "/sdcard/Download/x.zip", 456)
    except dt.DeployError as error:
        assert error.code == 4 and "123" in str(error) and "456" in str(error), error
    else:
        raise AssertionError("字节数不一致被放过了")
    # stat 不支持时退 wc -c
    adb = StubAdb({"shell wc -c": "456 /sdcard/Download/x.zip\n"})
    assert dt.verify_remote_size(adb, Path("x.zip"), "/sdcard/Download/x.zip", 456) == 456


def test_check_space_gate():
    """低于 35 GiB 拦住（code 3）；df 解析不出与"真的满了"是两种报错。"""
    small = ("Filesystem 1K-blocks Used Available Use% Mounted on\n"
             "/dev/fuse 104857600 99000000 5857600 94% /data\n")
    adb = StubAdb({"shell df": small})
    try:
        dt.check_space(adb, 35.0)
    except dt.DeployError as error:
        assert error.code == 3 and "先清空间" in str(error), error
    else:
        raise AssertionError("空间不足被放过了")
    broken = StubAdb({"shell df": "df: /sdcard: Permission denied\n"})
    try:
        dt.check_space(broken, 35.0)
    except dt.DeployError as error:
        assert error.code == 3 and "不要当成空间满" in str(error), error
    else:
        raise AssertionError("df 失败被当成了空间满")


def test_select_device_requires_phone():
    """真跑（非干跑）时 adb devices 为空 → code 2，消息点名外部阻塞。"""
    adb = StubAdb({"devices": "List of devices attached\n\n"})
    try:
        dt.select_device(adb)
    except dt.DeployError as error:
        assert error.code == 2 and "手机没接上" in str(error), error
    else:
        raise AssertionError("没有设备也放过了")
    # adb 守护进程启动横幅（stderr 被并进 stdout）不能当成设备 —— 真机首跑踩过
    banner = StubAdb({"devices": "List of devices attached\n"
                                 "* daemon not running; starting now at tcp:5037\n"
                                 "* daemon started successfully\n"
                                 "3b864e51\tdevice\n"})
    assert dt.select_device(banner) == "3b864e51"
    # get-state 是宿主机命令：必须是 adb get-state，不能是 adb shell get-state（真机首跑 exit 127）
    assert ["get-state"] in banner.calls, banner.calls
    assert ["shell", "get-state"] not in banner.calls, banner.calls
    # 未授权要给人话，而不是「接了 1 台设备」
    denied = StubAdb({"devices": "List of devices attached\nZX\tunauthorized\n"})
    try:
        dt.select_device(denied)
    except dt.DeployError as error:
        assert error.code == 2 and "未授权" in str(error), error
    else:
        raise AssertionError("未授权被放过了")
    # 多台设备要 --device 指定
    adb = StubAdb({"devices": "List of devices attached\nA\tdevice\nB\tdevice\n"})
    try:
        dt.select_device(adb)
    except dt.DeployError as error:
        assert error.code == 2 and "--device" in str(error), error
    else:
        raise AssertionError("多设备歧义被放过了")


def test_adb_resolution_priority():
    """优先级：--adb > DM_ANDROID_TOOLS > 仓内约定 > PATH；干跑找不到也不拦。"""
    with tempfile.TemporaryDirectory() as tmp:
        explicit = Path(tmp) / "my-adb"
        explicit.write_text("", encoding="utf-8")
        found, source = dt.resolve_adb(explicit=str(explicit))
        assert found == explicit and source == "--adb", (found, source)
        tools = Path(tmp) / "tools" / "platform-tools"
        tools.mkdir(parents=True)
        from_tools = tools / ("adb.exe" if os.name == "nt" else "adb")
        from_tools.write_text("", encoding="utf-8")
        old = os.environ.get("DM_ANDROID_TOOLS")
        os.environ["DM_ANDROID_TOOLS"] = str(Path(tmp) / "tools")
        try:
            found, source = dt.resolve_adb()
            assert found == from_tools and source == "DM_ANDROID_TOOLS", (found, source)
        finally:
            if old is None:
                os.environ.pop("DM_ANDROID_TOOLS", None)
            else:
                os.environ["DM_ANDROID_TOOLS"] = old
    # 全都找不到时干跑给占位、真跑才报错（屏蔽 PATH 查找与 DM_ANDROID_TOOLS，排除本机环境影响）
    old_which = dt.shutil.which
    old_tools = os.environ.pop("DM_ANDROID_TOOLS", None)
    dt.shutil.which = lambda name: None
    try:
        found, source = dt.resolve_adb(repo=Path(tmp), dry_run=True)
        assert source.startswith("PATH"), (found, source)
        try:
            dt.resolve_adb(repo=Path(tmp))
        except dt.DeployError as error:
            assert error.code == 2 and "找不到 adb" in str(error), error
        else:
            raise AssertionError("真跑找不到 adb 被放过了")
    finally:
        dt.shutil.which = old_which
        if old_tools is not None:
            os.environ["DM_ANDROID_TOOLS"] = old_tools


def test_manifest_marker_is_external():
    """完成标记必须在**外部**包目录：真机首跑确认内部只有 game/，manifest 跟着 romfs/shaders 落外部。"""
    assert dt.DEVICE_MANIFEST.startswith("/sdcard/Android/data/"), dt.DEVICE_MANIFEST
    assert "run-as" not in dt.DEVICE_MANIFEST
    adb = StubAdb({"shell ls": dt.DEVICE_MANIFEST + "\n"})
    assert dt.import_manifest(adb) == dt.DEVICE_MANIFEST
    assert adb.calls[0] == ["shell", "ls", dt.DEVICE_MANIFEST], adb.calls
    manifest = {"format": 1, "subgroup_size": 64,
                "counts": {"game": 9, "romfs": 304243, "shaders": 24535}}
    adb = StubAdb({"shell cat": json.dumps(manifest)})
    assert dt.check_imported_manifest(adb, manifest) == manifest
    assert adb.calls[0] == ["shell", "cat", dt.DEVICE_MANIFEST], adb.calls
    wrong = dict(manifest, subgroup_size=32)
    try:
        dt.check_imported_manifest(StubAdb({"shell cat": json.dumps(wrong)}), manifest)
    except dt.DeployError as error:
        assert error.code == 5, error
    else:
        raise AssertionError("subgroup 不一致被放过了")


def test_rewrite_key_value_keeps_unknown():
    """改档位时保留界面自己写的其它键与注释，只动目标键。"""
    text = "# comment\npackage_summary=旧包\ndriver=system\ngame=d2r\nframe_counter=1\n"
    out = dt.rewrite_key_value(text, {"game": "totk", "driver": "turnip"})
    lines = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    assert lines == {"package_summary": "旧包", "driver": "turnip", "game": "totk",
                     "frame_counter": "1"}, lines
    assert "# comment" in out
    # 空文件（键不存在）也能补写
    assert dt.rewrite_key_value("", {"game_profile": "totk"}).strip() == "game_profile=totk"


def test_missing_package():
    """包不存在 → code 2，且一条 adb 命令都不打印（设备流程前就拦住）。"""
    code, out = run_main(["--dry-run", "--package", "Z:\\no\\such\\package.zip"])
    assert code == 2, (code, out)
    assert "[dry-run]" not in out, out


def main():
    test_dry_run_same_path()
    test_dry_run_fixed_dest()
    test_row_centre_tolerates_prefix()
    test_launcher_row_scrolls()
    test_parse_free_kib()
    test_verify_remote_size_mismatch()
    test_manifest_marker_is_external()
    test_check_space_gate()
    test_select_device_requires_phone()
    test_adb_resolution_priority()
    test_rewrite_key_value_keeps_unknown()
    test_missing_package()
    print("deploy totk OK")


if __name__ == "__main__":
    main()
