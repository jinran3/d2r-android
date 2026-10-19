---
protocol: 1
updated_at: 2026-10-19T18:43:27+08:00
phase: M0
state: ACTIVE
branch: totk/scaffold
observed_head: 1d915aba0df285bb8e0cb2d7175e184659b0cd52
origin_ref: origin/totk/scaffold
origin_head_at_checkpoint: 1d915aba0df285bb8e0cb2d7175e184659b0cd52
code_worktree: CLEAN
next_action_id: NA-002
---

# TotK 移植交接文档（HANDOFF）

> 本文件是上下文压缩、模型切换、会话重启后的**唯一权威续跑入口**。
> 聊天记录、压缩摘要、终端滚动历史都不是事实来源。Git 是代码事实，本文是工作意图事实。

## 阅读顺序

1. 仓库根目录 `AGENTS.md`：Agent 硬性入口。
2. 本文 `## 当前快照` 与 `## 下一步唯一动作`。
3. [完整会话日志](HANDOFF_LOG.zh-CN.md)。
4. [TotK 移植进度](TOTK_PORT_PROGRESS.zh-CN.md)。
5. [TotK 移植脚手架计划](TOTK_PORT_SCAFFOLD.zh-CN.md)。

## 权威来源与冲突处理

1. **Git 实际状态**是代码、分支、HEAD、工作区和远端同步的唯一事实来源。
2. **HANDOFF 当前快照**是工作意图、下一步和阻塞原因的唯一事实来源。
3. 进度文档和计划只提供里程碑与路线，不能覆盖当前快照。
4. 聊天记录、压缩摘要、模型记忆只能作为线索，不能作为验证证据。
5. 当 HANDOFF 与 Git 冲突时，先修正 HANDOFF，再写业务代码；修正记录写入日志。
6. 所有“已完成”“已验证”“可运行”必须附命令、退出码或产物路径；没有证据就写 `NOT RUN` 或 `UNVERIFIED`。

## 状态机

| 状态 | 含义 | 允许修改代码 |
| --- | --- | --- |
| `ACTIVE` | 正常开发 | 是 |
| `CHECKPOINTING` | 正在写交接快照 | 否 |
| `READY_FOR_HANDOFF` | 已完成交接，可切换会话 | 否 |
| `BLOCKED_USER` | 等待用户提供材料或决策 | 否 |
| `BLOCKED_EXTERNAL` | 网络、工具、权限等外部阻塞 | 否 |
| `RECOVERING` | 新会话正在核对状态 | 否 |
| `DONE` | 当前阶段完成 | 否 |

进入 `CHECKPOINTING`、`READY_FOR_HANDOFF`、`RECOVERING` 后，禁止新功能开发。
进入 `BLOCKED_*` 必须写清阻塞条件和解除条件。
每次状态变化都要追加到 `HANDOFF_LOG`。

## 强制触发条件

出现任意一条，必须进入交接冻结流程：

- 完成一个原子任务、修复一个真实 bug、完成一次提交或推送；
- 准备切换分支、工作树、Agent 或会话；
- 开始或结束超过 5 分钟的构建、下载、解包、测试或真机操作；
- 遇到失败测试、缺失文件、设备断开、权限问题或无法在 1–2 个动作内解决的阻塞；
- 准备执行删除、移动、覆盖、重置、强制推送等高风险操作；
- 用户说“交接”“暂停”“记录进度”“下次继续”“压缩上下文”；
- 上下文使用率达到 60%、75%、85% 阈值；
- 收到压缩、摘要、最大上下文或 compaction 提示；
- 上下文使用率未知，但已连续工作约 20 分钟或约 15 次工具调用仍无任务边界；
- 新会话核对后发现 HANDOFF 与 Git 不一致。

**不能只等压缩通知。** 压缩可能在 Agent 获得下一次工具调用机会之前发生，因此每个原子任务结束时都必须写快照。

## 上下文预算门

| 使用率 | 允许做什么 | 禁止做什么 |
| --- | --- | --- |
| 0%–50% | 正常开发；每个原子任务后更新快照 | 无 |
| 50%–65% | 收敛范围，只做小任务 | 新开宽泛调研 |
| 65%–80% | 冻结范围，每步后更新 HANDOFF | 新模块、大重构、大删除 |
| 80%–90% | 只做交接、验证、提交 | 任何新功能 |
| ≥90% 或压缩通知 | 只写紧急快照并停止 | 任何代码编辑 |

无法读取使用率时，用以下代理，满足任意一项就写快照：

- 每 15 次工具调用；
- 每 20 分钟；
- 每个原子任务结束；
- 每次长命令前后。

## 交接冻结流程

### 1. 停止扩展

- 不新增功能、不开新实验、不改无关文件。
- 正在运行的命令记录 PID、会话或日志路径。
- 不为了“顺手”再改一个文件。

### 2. 采集 Git 状态

```powershell
cd D:\Switch\d2r-android
git status --short --untracked-files=all
git branch --show-current
git rev-parse HEAD
git rev-parse origin/totk/scaffold
git log -8 --oneline --decorate
git diff --stat
git diff --check
```

同时记录已提交、未提交、未跟踪、被忽略但重要的产物。

### 3. 更新当前快照

按 `## 当前快照` 的字段原地更新，不追加第二份快照。

### 4. 更新下一步唯一动作

按 `## 下一步唯一动作` 的契约更新。只允许一个 READY 动作。

### 5. 追加日志

在 `HANDOFF_LOG.zh-CN.md` 顶部追加一条，不覆盖旧记录。

### 6. 自检

运行：

```powershell
D:\Switch\.tools\venv\Scripts\python.exe tools\agent_handoff_check.py --verify
```

校验失败时不得声明“可以交接”。

### 7. 提交与推送

- 交接控制面单独提交，不与业务代码混在一起。
- 推荐提交信息：`docs: checkpoint agent handoff`。
- 推送后核对本地 HEAD 与 `origin/totk/scaffold`。
- 无法提交或推送时必须写 `COMMIT: NOT DONE` / `PUSH: NOT DONE`，并列出恢复命令。

### 8. 写恢复入口

`## 下一步唯一动作` 必须包含一条可直接复制的命令或明确编辑目标。

## 当前快照

- 快照时间：2026-10-19 18:43（Asia/Shanghai）
- 当前阶段：M0 准备 / 脚手架
- 当前分支：`totk/scaffold`
- 观测 HEAD：`1d915aba0df285bb8e0cb2d7175e184659b0cd52`（快照基线；允许是当前 HEAD 的祖先）
- origin 对应分支：`origin/totk/scaffold`，检查点为 `1d915aba0df285bb8e0cb2d7175e184659b0cd52`（与观测 HEAD 相同）
- 代码工作区：`CLEAN`（排除交接控制面）
- 未提交代码文件：无
- 未跟踪代码文件：无
- 被忽略但重要的产物：`dm/android/build/D2R-Android-port.apk`
- 本次会话目标：执行 NA-001（审查并单独提交两处 TotK 适配代码），然后更新交接控制面。
- 已完成（带证据）：见下方「已完成清单」。
- 未完成：D2R 专属资产裁剪（批 1 = 宿主侧 TACT/CASC，见 NA-002）；TotK 文件准备；M0 实测；着色器事实表来源。
- 最近一次成功命令：`git push`，exit 0（`c405782..1d915ab`）；`tools/agent_handoff_check.py --verify`，exit 0。
- 最近一次失败命令及原因：本轮无仓库命令失败；规则域与校验器负向测试的 exit 1 是预期断言失败。
- 已验证产物路径：本轮未产出新构建产物（NOT RUN）；`D:\Switch\d2r-android\dm\android\build\D2R-Android-port.apk` 为上一会话产物。
- 当前阻塞：缺少用户合法导出的 TotK 文件、`prod.keys`、`hactool`；`adb devices` 无设备。
- 需要用户提供的材料：自己的 TotK 本体 + 更新、`prod.keys`、可用 `hactool`、一加 12（开启 USB 调试）。
- 回滚点：`1d915aba0df285bb8e0cb2d7175e184659b0cd52` / `totk/scaffold`。
- 禁止事项：不得提交游戏内容、密钥、存档或构建产物；不得删除未提交代码；不得把 D2R 数据当作 TotK 数据。

### 已完成清单

- 新增 `AGENTS.md` 硬性入口。
- 新增 `tools/agent_handoff_check.py` 与 `tools/test_agent_handoff_check.py`。
- 新增 `docs/HANDOFF_LOG.zh-CN.md`。
- 交接协议已纳入 `dm/android/tools/ci_checks.py`。
- 交接控制面已提交并推送（`c405782`）；以 `origin/totk/scaffold` 为准。
- `build.py --game-run --version handoff-check`：exit 0，生成 APK（上一会话证据）。
- 规则域负向测试：`touch-run-v4` exit 1（构建号不符），`totk-run-v1` exit 0（`cuts 0 obs 0`）。
- 两处 TotK 适配代码审查后单独提交：`1d915ab`，提交只含 `dm/android/tools/extract_packages.py` 与 `dm/tools/patch_nso.py`；`git push` exit 0；`git status --short` 为空。
- `agent_handoff_check.py --verify`：exit 0；负向测试确认 HEAD 不一致、密钥样式、未闭合 BEGIN 均被拒绝。

### 代码工作区（排除交接控制面）

```text
```

## 下一步唯一动作

- ID：NA-002
- 状态：READY
- 工作目录：`D:\Switch\d2r-android`
- 前置条件：`totk/scaffold` 的 HEAD 与 `origin/totk/scaffold` 同为 `1d915aba0df285bb8e0cb2d7175e184659b0cd52`；代码工作区干净；`HANDOFF_LOG` 无未闭合 `[BEGIN]`。
- 动作：裁剪批 1 —— 拆除 TACT/CASC（暴雪存储）宿主侧解码及其构建接线。只做「必须同时改」的集合：删除 `dm/host/hle_tact.c` 并修正它在两套构建系统、prof 枚举、改写器登记与白名单中的引用（批 2 的 `dm/tools/casc_overlay.py`、`dm/tools/tact_bootlist.py`、`dm/data/**`、`dm/verify/**`、README/文档不在本步范围）。
- 命令或编辑目标：先 `git grep -n -e hle_tact -e PROF_TACT -e libdeflate -e SVC_HOST_TACT` 全量复核调用点；再 `git rm dm/host/hle_tact.c`；同一提交内修正 `dm/host/hle.h`、`dm/host/dm.h`、`dm/host/diag.c`、`dm/host/hle_svc.c`、`dm/host/hle_fs.c`、`dm/host/Makefile`、`dm/android/tools/host_link.py`、`dm/tools/patch_nso.py`、`dm/host/tests/mode_scan.py`、`dm/i18n/literal_whitelist.tsv`；然后按「标准验证命令」跑 `dm\android\tools\ci_checks.py`（带 `DM_ANDROID_TOOLS=D:\Switch\.tools\android`）、`dm\android\tools\build.py --game-run --version trim-b1`、`tools\agent_handoff_check.py --verify`；最后 `git add -A`、`git commit -m "totk: drop host-side TACT/CASC decode"`、`git push`。
- 成功判据：`ci_checks.py` 8 通过 / 0 失败；`build.py --game-run` exit 0 且产出 APK；`git grep` 复核后 `hle_tact` 与 `PROF_TACT` 在仓库内已无活引用；提交只含本批文件；`git rev-parse HEAD` 与 `git rev-parse origin/totk/scaffold` 相同。
- 失败判据：任一验证命令非零退出，或 `ci_checks.py` 出现失败项；APK 未产出；提交混入批 2 文件或交接控制面文件。
- 回滚点：`1d915aba0df285bb8e0cb2d7175e184659b0cd52` / `totk/scaffold`（单次提交，必要时 `git revert`）。
- 需要写入的证据：`git grep` 原始输出；`ci_checks.py` 计分行与退出码；`build.py --game-run` 退出码与 APK 路径、大小；`git status --short`；commit hash；`git rev-parse HEAD` 与 `git rev-parse origin/totk/scaffold`。

## 长操作两阶段日志

对超过 5 分钟或高风险的构建、下载、解包、真机测试，必须先在日志写 `[BEGIN]`，完成后写 `[END]`。

```text
[BEGIN] operation-name
命令：
工作目录：
预期结果：
日志路径：
回滚点：
```

```text
[END] operation-name
退出码：
产物：
结果：SUCCESS / FAILED / INTERRUPTED
备注：
```

新会话看到只有 `[BEGIN]` 没有 `[END]` 时，状态标记为 `IN_PROGRESS_UNKNOWN`，必须先检查进程、日志和产物，不能直接重跑。

## 新会话恢复流程

1. 读 `AGENTS.md`。
2. 读本文 frontmatter、`## 当前快照`、`## 下一步唯一动作`。
3. 运行 `python tools/agent_handoff_check.py --resume`。
4. 运行 `python tools/agent_handoff_check.py --verify`。
5. 检查 `HANDOFF_LOG` 是否有未闭合 `[BEGIN]`。
6. 对比分支、HEAD、代码工作区文件清单和远端同步状态。
7. 不一致时先修正 HANDOFF，不直接写业务代码。
8. 复述下一步唯一动作和成功判据。
9. 只执行该动作。
10. 完成后立即更新快照和日志。

恢复时禁止：

- 相信压缩摘要里的“已完成”；
- 跳过 Git 状态核对；
- 同时开始多个不相关任务；
- 删除或覆盖上一位 Agent 的未提交改动；
- 把未提交改动写成已提交；
- 未检查未闭合长操作就重跑。

## 项目事实

| 项目 | 当前值 |
| --- | --- |
| 主仓库 | `D:\Switch\d2r-android` |
| 参考仓库 | `D:\Switch\d2r-mobile` |
| origin | `https://github.com/jinran3/d2r-android.git` |
| upstream | `https://github.com/sydeEvans/d2r-android.git` |
| 打开中的 PR | PR #1，`totk/scaffold` → `main` |
| PR 地址 | https://github.com/jinran3/d2r-android/pull/1 |
| 目标设备 | 一加 12，Snapdragon 8 Gen 3 / Adreno 750 |
| 当前阶段 | 脚手架与 M0 准备，TotK 尚不可运行 |

已提交的 TotK 脚手架提交：

- `6d0b04e`：Windows 检查工具诚实性修复。
- `954d402`：纳入 TotK 计划与进度入口。
- `622c473`：纯 Windows Android 工具链端到端可用。
- `a919fdb`：更新进度入口，记录纯 Windows 构建已打通。
- `c405782`：交接控制面定稿（快照、日志、校验器）。
- `1d915ab`：TotK 适配 —— `extract_packages.py` 标题号参数化、`patch_nso.py` 新增 `totk-run-v1` 规则域。

## 本机环境

- 必须使用 `D:\Switch\.tools\venv\Scripts\python.exe`（Python 3.12.14）。
- Android 工具链：`D:\Switch\.tools\android`。
- 构建命令必须设置 `DM_ANDROID_TOOLS=D:\Switch\.tools\android`。
- `adb`：`D:\Switch\.tools\android\platform-tools\adb.exe`，当前无设备。
- `gh` 命令必须显式带 `--repo jinran3/d2r-android`。
- fork 的 GitHub Actions 未注册，本机构建是唯一验证手段。

## 标准验证命令

```powershell
$vpy = 'D:\Switch\.tools\venv\Scripts\python.exe'
$env:DM_ANDROID_TOOLS = 'D:\Switch\.tools\android'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

& $vpy dm\android\tools\ci_checks.py
& $vpy dm\android\tools\build.py --game-run --version handoff-check
& $vpy tools\agent_handoff_check.py --verify
```

## 后续队列

1. ~~提交交接控制面~~ —— 完成（`c405782`）。
2. ~~提交两处 TotK 适配代码~~ —— 完成（`1d915ab`）。
3. 小步裁剪 D2R 专属资产，每批后跑 `ci_checks` 与完整 `build.py --game-run`：批 1 = 宿主侧 TACT/CASC（NA-002）；批 2 = Python 工具 / 验证脚本 / 文档 / 数据表；批 3 = 36 个 `dm_*.c` 与派生表（最危险，必须同时核对 `dm/host/Makefile` 的显式 `SRC` 与 `dm/android/tools/host_link.py` 的 glob）。
4. 准备 TotK 本体、更新、`prod.keys`、`hactool`，完成 M0 实测表。
5. 解决着色器事实表来源，给出 M2 前 go/no-go 结论。
6. 按 M1–M6 验收门推进。

## 已知风险

| 风险 | 影响 | 状态 |
| --- | --- | --- |
| 着色器事实表无来源 | 可能推翻原生移植路线 | 未解决 |
| TotK 系统服务面远大于 D2R | HLE 工作量可能失控 | 未实测 |
| Adreno 750 驱动兼容性 | 现有 Turnip 面向 Adreno 830 | 未验证 |
| RomFS 超过 4GB | zip、zipalign、apksigner 边界问题 | 未设计 |
| 真机未连接 | 启动、导入、性能均未验证 | 阻塞 |
| `ci_checks` 不覆盖宿主链接 | 可能假绿 | 用完整 build 兜底 |
| 裁剪 D2R 资产波及两套构建系统 | 删文件会断宿主链接或改写器登记 | 已探明，见 NA-002；以完整 build 兜底 |

## 必须遵守的边界

- 只能使用用户自己拥有的 TotK 副本，从自己的主机导出。
- 不提交游戏程序、美术、着色器、存档或由其生成的表和图。
- 不回显 `prod.keys` 内容。
- Ryujinx 着色器翻译与 Eden 胶水是 GPL-3.0；本仓库是 MIT，只能参考思路，不能拷代码。
- 性能与正确性结论必须写明机型、场景、热机状态；没跑就写 `NOT RUN`。
- 构建号、CUTS/OBS、NVN 表、着色器事实表、驱动配置必须按 TotK 重新验证。