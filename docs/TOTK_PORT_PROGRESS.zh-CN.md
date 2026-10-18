# TotK 移植进度

更新日期：2026-10-18。此文件随工作更新，是中断后继续移植的入口。

路线图与分阶段验收门见 [TotK 移植脚手架计划](TOTK_PORT_SCAFFOLD.zh-CN.md)（下称「计划」）。

- 目标设备：一加 12（Snapdragon 8 Gen 3 / **Adreno 750** / Android）
- 起点：fork 自 `sydeEvans/d2r-android`（HEAD `5d8e322`），上游是 `jhaizhou-ops/d2r-mobile`
- 分支：`totk/scaffold`（`main` 保持 D2R 可构建，不混入 TotK 工作）

## 当前状态（继续开发先看这里）

**2026-10-18：分支建立 + 检查基线跑绿。**

1. `totk/scaffold` 分支已建，推到 `origin`（`6d0b04e`）。
2. 第一个提交不是裁剪，而是**让检查本身在本机可信**。改动前 `ci_checks.py` 是 5 通过 / 3 失败，逐条查证后三个失败全是环境假象：
   - 字面量扫描 443+112 条红 → 根因是 Windows `relpath` 给反斜杠，白名单存正斜杠，整表匹配不上。按 `os.sep` 归一后降到 1 条。
   - `ci_checks.py` 自己先崩 → GBK 控制台打不出它的通过/失败符号，`UnicodeEncodeError`。改为本进程强制 UTF-8。
   - 启动设置两测试编译失败 → `alarm`/`setenv`/`mkdtemp` 是 POSIX 专有，Windows/MinGW 没有。按 `os.name != "posix"` 如实标跳过，**Linux/CI 照常真跑**。
   - 剩余 1 条（`drop_light.py:65` 的 f-string）是 **Python 3.9 vs 3.12 的分词差异**：白名单按 3.12 的 PEP 701 行为生成且双向严格，3.9 上结构上不可能跑绿。按 `sys.version_info < (3,12)` 如实跳过，未改扫描语义以免破坏上游闸门。
   - **验证：5 项通过，0 项失败，exit 0**；5 项跳过全部带理由，没有把「跑不了」记成「通过」。
3. 计划文档已纳入版本管理：`docs/TOTK_PORT_SCAFFOLD.zh-CN.md`。

**尚未开始**：§8 第 2 步（拿到游戏文件后填计划 §3 的表：模块数 / 符号数 / NVN 函数数 / 着色器键数 / 构建号）与第 3 步（着色器事实表来源，计划 §4.4，M2 的 go/no-go 检查点）。裁剪提交（删 D2R 专属资产）待基线确认后进行。

## 本机环境与已知限制

- **WSL2 当前不可用**：`Wsl/Service/MountDisk/HCS/ERROR_PATH_NOT_FOUND`，虚拟磁盘缺失。上游构建脚本面向 Linux x86_64，所以完整构建/真机构建在本机暂时跑不了。
- **Python 3.9.2 为默认解释器**（`py -0` 里的 3.14 注册项指向不存在的 `C:\Python314`）。上游 CI 固定 3.12。
- **未安装项目 JDK**：`ci_checks.py` 的存档包 / 数据包导入两项自动跳过。
- 未安装 Android NDK（`bootstrap.py` 未跑），未接真机。

这些在 `ci_checks.py` 输出里都以「跳过」显式列出，不用猜。

## 下一步

按计划 §8 顺序：

1. ~~`totk/scaffold` 分支 + 可验证基线~~ —— 完成。
2. **裁剪提交**：删计划 §2 清单里的 D2R 专属资产（`dm_*.c`、D2R 派生表、i18n 表、TACT 相关），重跑 `ci_checks.py` 确认仍绿。注意 `host/Makefile` 的 `SRC` 是显式列举、`host_link.py` 用 `glob("*.c")`——两处行为不同，删文件时必须同时核对。
3. **准备工具链**：决定用 WSL（需修复虚拟磁盘）还是另装 Linux 环境；跑 `bootstrap.py`。
4. **拿到自己的 TotK 本体+更新与 `prod.keys` 后**，填计划 §3 的表、读出 NSO 构建号（计划里 `extract_packages.py` 硬编码了 D2R 的 Title ID，必须改）。
5. **解决计划 §4.4 的着色器事实表来源** —— M2 的 go/no-go 检查点，唯一可能推翻整条路线的点。

## 必须遵守的边界（每轮复述）

- 不提交任何游戏内容：程序、美术、着色器、存档，以及由它们生成的图 / 表 / 代码。仓库的 `.gitignore` 已挡 `*.nsp/nsz/xci/nca/keys` 与 `/ExeFS/` `/romfs/` `/save/`，游戏文件另放仓库外。
- 密钥不回显：日志与错误信息里不出现 `prod.keys` 内容（`extract_packages.py` 已按此设计）。
- 许可边界：Ryujinx 着色器翻译与 Eden 胶水是 GPL-3.0，本仓库是 MIT，**可参考思路不可拷代码**。
- 结论要带证据：性能与正确性结论必须写明机型、场景、热机状态；没跑的直接写「没跑」。