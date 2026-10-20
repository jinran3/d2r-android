---
protocol: 1
updated_at: 2026-10-20T11:30:00+08:00
phase: M0
state: ACTIVE
branch: totk/scaffold
observed_head: a25ccc3
origin_ref: origin/totk/scaffold
origin_head_at_checkpoint: a25ccc3
code_worktree: CLEAN
next_action_id: NA-032
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

- 快照时间：2026-10-20 10:10（Asia/Shanghai）
- 当前阶段：M0 勘察完成；M1（模块装载）就绪；§4.4 着色器事实表来源已有解
- 当前分支：`totk/scaffold`
- 观测 HEAD：见 frontmatter `observed_head`（NA-032 业务提交：着色器归档解码工具）
- origin 对应分支：`origin/totk/scaffold`，检查点见 frontmatter
- 代码工作区：`CLEAN`（排除交接控制面）
- 未提交代码文件：无
- 未跟踪代码文件：无
- 被忽略但重要的产物：`dm/android/build/D2R-Android-port.apk`（`trim-b26`，17,725,903 字节）
- 本次会话目标：NA-031（模块来源接规则域 + HLE 缺口普查）与 NA-032（§4.4 着色器事实表来源）。
- 已完成（带证据）：见下方「已完成清单」。
- 未完成：着色器事实表里**贴图维度 / 图像格式 / 属性分量类型**那几项还没定位（控制头里的描述符表），以及让翻译链吃下 TotK 着色器（NA-032 剩下的部分；计算着色器的线程组与共享内存**已直接可得**）；**改写器的 x18 适配**（TotK 的 main 有「分支跳进独占窗口中间」和 `blr x18` 调用两种 D2R 没有的形态，当前 TotK 规则域先不做 x18 改写，Android 侧靠宿主保全 x18；正式做法见 NA-032 之后那一步）；更新包 RomFS 的 BKTR 补丁应用（最终数据集还差这层）；真机装载与进 `nnMain`（一加 12 未接）；批 6 剩余的 D2R 清理（D2R 的 CUTS/OBS 表、`casc_overlay.py`、iOS 资产管线）。
- 最近一次成功命令：`build.py --game-run --version trim-b26` exit 0（APK 17,725,903 字节）；`ci_checks.py` 10 项通过 / 0 项失败；`agent_handoff_check.py --verify` exit 0；`test_rewriter.py` exit 0；`make_package.py --ruleset totk-run-v1 --exefs ... --modules-only` exit 0；`switch_shaders.py` exit 0（30 个着色器文件 + 清单）。
- 最近一次失败命令及原因：① `make_package.py` 第一次跑 TotK 报 `FileNotFoundError: ...\produce\game` —— 自备 ExeFS 那条路少了 `produce.mkdir`，已修；② `test_rewriter.py` 首次报 `FileNotFoundError` —— 本机没设 `DM_ANDROID_TOOLS`（脚本按 `~/dm-work/tools/android` 找工具链），设上即 exit 0；③ `switch_nca.py romfs-extract` 多线程共用一个文件句柄导致读串台（已改为每线程一个句柄，并加了读满校验）。
- 已验证产物路径：`D:\Switch\d2r-android\dm\android\build\D2R-Android-port.apk`（`trim-b26`）；TotK 侧仓库外产物：`D:\Switch\totk-work\`（upd-exefs、pack-totk\produce\game、guest-so、shaders-out、base\RomFS 解包中）
- 当前阻塞：一加 12 真机仍未接（`adb devices` 无设备）；FSHA 容器的内层条目格式还没解析（事实表还差最后一步）。
- 需要用户提供的材料：一加 12（开启 USB 调试）——游戏文件与 `prod.keys` 已由用户于 2026-10-20 提供。
- 回滚点：见 frontmatter `observed_head` / `totk/scaffold`。
- 禁止事项：不得提交游戏内容、密钥、存档或构建产物；不得删除未提交代码；不得把 D2R 数据当作 TotK 数据；**外部项目的代码不要直接搬进来**（`OJZen/totk-mobile` 是 Apache-2.0，本仓库是 MIT；只读思路与格式事实，代码自己写；Ryujinx 是 MIT，可用但要保留声明）。

### 已完成清单

- 新增 `AGENTS.md` 硬性入口。
- 新增 `tools/agent_handoff_check.py` 与 `tools/test_agent_handoff_check.py`。
- 新增 `docs/HANDOFF_LOG.zh-CN.md`。
- 交接协议已纳入 `dm/android/tools/ci_checks.py`。
- 交接控制面已提交并推送（`c405782`、`8965544`）；以 `origin/totk/scaffold` 为准。
- `build.py --game-run --version handoff-check`：exit 0，生成 APK（较早会话证据）。
- 规则域负向测试：`touch-run-v4` exit 1（构建号不符），`totk-run-v1` exit 0（`cuts 0 obs 0`）。
- 两处 TotK 适配代码审查后单独提交：`1d915ab`，提交只含 `dm/android/tools/extract_packages.py` 与 `dm/tools/patch_nso.py`。
- NA-002 裁剪批 1（`b54f782`）：删除 `dm/host/hle_tact.c`，把宿主调用分派器（0x85–0x8e）拆到新文件 `dm/host/hle_hostcall.c`；摘掉 `PROF_TACT`、`SVC_HOST_TACT_ZLIB`、0x80 剪口登记、`libdeflate` 构建接线与两处白名单行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b1` exit 0，APK 19,364,303 字节。
- NA-003 裁剪批 2（`1a2f535`）：删 `dm/tools/tact_bootlist.py`、`dm/verify/bootchk.sh`、`dm/verify/bootlist_static.py`，并清掉 `patch_nso.py` 的清单出包块、`accept.sh` 的 ⓪ 验收项与 `ITEMS` 表、`test_accept.py` 的替身桩、四个 README 行、`dm/ios/run.sh`、`shell_build.sh`、`d2rm_pack.py` 的搬运点。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b2` exit 0，APK 19,364,303 字节；`git grep -e bootlist -- dm tools` 0 命中。
- NA-004 裁剪批 3（`62139f0`）：删 `dm/host/hle_granny.c`（332 行）与宿主调用 0x83/0x84 的登记表、枚举、分派器 case、生命周期调用、生命周期单测桩与标记序号、字面量白名单行、改写器里的 0x83/0x84 剪口条目、两个 README 行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b3` exit 0，APK 19,315,151 字节；`git grep -i granny -- dm` 只剩 4 行举例注释。
- NA-005 裁剪批 4（`bf7b33f`）：删 vendored `dm/third_party/libdeflate`（43 个跟踪文件、14,851 行，含 MIT `COPYING`），并清掉 `dm/third_party/README*.md` 与 `docs/DEPENDENCIES*.md` 的 libdeflate 行。TACT/CASC 依赖至此清零。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b4` exit 0，APK 19,315,151 字节（与 trim-b3 同大小——该库自 NA-002 起已不参与构建）；`git grep -i libdeflate` 除控制面历史外 0 命中。
- NA-006 裁剪批 5（`abb0040`）：删 `dm/host/hle_movie.c`（308 行，过场/背景视频「按真实时长空播」，宿主实现按 D2R main 3.3.94012 原映像偏移写死游戏侧协议）、`dm/host/tests/t_movie.c`、`dm/host/tests/movie_cut.py`，并清掉 `dm/host/tests/Makefile` 五处、`literal_whitelist.tsv`、`dm/README*.md`、`dm/host/README*.md` 的引用。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b5` exit 0，APK 19,282,383 字节（比 trim-b4 小 32,768 字节）；`git grep -e hle_movie -e movie_cut -e t_movie -- dm` 0 命中。**本机 NOT RUN**：`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）在本机跑不了，被删的 `t_movie`／`movie_cut.py` 未经本机执行验证。
- NA-007 裁剪批 7a（`4392313`）：删 `dm/host/dm_turnsmooth.c`（转向回跳平滑，独占观测门 19 `OBS_ERR_SMOOTH` 与 20 `OBS_MODEL_YAW`）、`dm/host/dm_shoprefresh.c`（商人「刷新货架」）、`dm/ios/tools/turn_trace.py`；观测门两侧同步收口（`dm/host/dm.h` 的枚举去 19/20、`OBS_MAX` 21→19；`dm/tools/patch_nso.py` 的 OBS 表去两条；`dm/host/hle.c` 的门号越界检查要求两侧同时收）；另清 `diag.c` 四处（含把错挂在删除行上的「首领连战」注释移回 `dm_bossrush_c2s` 那行）、`Makefile` 的 `SRC`、`touch_layout.py` 两处注释、`uireg/affected.tsv`、`dm/host/README*.md`。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b6` exit 0，APK 19,265,999 字节（比 trim-b5 小 16,384 字节）；规则域测试 `totk-run-v1` exit 0 / `cuts 0 obs 0`、`touch-run-v4` exit 1；`git grep -e dm_turnsmooth -e dm_shoprefresh -e OBS_ERR_SMOOTH -e OBS_MODEL_YAW -- dm` 0 命中。
- NA-008 裁剪批 7b（`6b261f7`）：删 `dm/host/dm_lootfilter.c`（掉落过滤）、`dm/host/dm_autobuff.c`（增益技能自动补），并清掉隐藏调用点 —— `dm_lootfilter_hidden`（`dm_potpick.c`、`dm_pouch.c`）、`dm_autobuff_srv_tick`（`diag.c`）、`dm_autobuff_pump`／`dm_autobuff_test_drop`（`dm_potpick.c`）、`dm_lootfilter_pump`／`dm_lootfilter_test_dump`（`dm_potpick.c`）；连 `hle_fs.c` 的 `g_dm_mount_seed_hook` 钩子机制整条摘掉（唯一登记者是掉落过滤的构造函数；`DM_TOUCH_DEFAULTS` 开关在别处仍在用，不会被孤立）。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b7` exit 0，APK 19,200,463 字节（比 trim-b6 小 65,536 字节）；`git grep -e dm_lootfilter -e dm_autobuff -e g_dm_mount_seed_hook -- dm` 0 命中（**用前缀查**，词边界会漏掉 `dm_lootfilter_hidden` 这类符号）。
- NA-009 裁剪批 7c（`b4d3557`）：删 `dm/host/dm_beltauto.c`（打开背包时自动把药水补进腰带；只有 `dm_beltauto_step`／`dm_beltauto_on_uimsg` 两个导出符号，无观测门、无构造器），并清掉 `diag.c`／`dm_world.c` 各一处调用、`dm_potpick.c` 两行提到它的实测记录注释、`Makefile` 的 `SRC`、白名单行、`uireg` 行、两个 `dm/host/README*.md` 表行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b8` exit 0，APK 19,167,695 字节（比 trim-b7 小 32,768 字节）；`git grep -e dm_beltauto -- dm` 0 命中。自定义键 `pot_pick` 保持不变（仍由 `dm_potpick.c` 在用；`dm_custom.c` 的 `k_keys` 是位置数组，删键要整体重编号，另随 `dm_potpick` 那批做）。
- NA-010 裁剪批 7d（`89a38ec`）：删 `dm/host/dm_potpick.c`（药水自动拾取），并把织在 `dm/host/diag.c` 里的六处一起拆掉（两处日志语义里的 `dm_potpick_auto` 三元、静态 `potpick_gate` 函数与其调用、`pk_auto` 变量与计算）；另清 `dm_world.c` 调用行、`dm_custom.h` 键注释、`Makefile` 的 `SRC`、两个 README 表行、`uireg` 行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b9` exit 0，APK 19,151,311 字节（比 trim-b8 小 16,384 字节）；`git grep -e dm_potpick -- dm` 0 命中。自定义键 `pot_pick` 仍留在 `dm_custom.c` 的 `k_keys` 位置数组里（与 7b 后已死的 `loot_filter`／`auto_buff` 同一处理），但 `dm_custom.h` 的键注释只列活键，已删掉该条目。
- NA-011 裁剪批 7e（`ead836a`）：删 `dm/host/dm_townwp.c`（进局落在城镇小站旁，宿主调用 0x8a/0x8b），并把四处宿主调用收口（`hle.h` 登记行中英各两条 + 枚举两项、`hle_hostcall.c` 的 case、`patch_nso.py` 的两个剪口条目与注释）；另清 `diag.c` 调用行、`Makefile` 的 `SRC`、两个 README 表行、`uireg/affected.tsv` 的行。**环境变量名不含模块名**：按模块名 grep 抓不到 `DM_TOWNWP_OFF`，宽口径复核（`git grep -n -i -e townwp`）又抓到三处并清掉（`uireg.py` 的说明块与 `OLD_SPAWN` 免跑表、专门验该特性的 "wp" 回归局、两个 shotgate 页面里只剩这一项的 `env` 块；两个 JSON 改后用 `json.load` 验过合法，`uireg.py` 用 `ast.parse` 验过语法）。`dm/verify/touchcases/no_move_taps/script.txt` 里的坐标位移是 D2R 产品的旧测量，本机无法验证，只改注释写明现状。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b10` exit 0，APK 19,134,927 字节（比 trim-b9 小 16,384 字节）。
- NA-012 裁剪批 7f（`c9aadb8`）：删 `dm/host/dm_dropfilter.c`（掉落光柱 = 宿主调用 0x87、落地音 = 0x88）与 `dm/host/dm_drophaptic.c`（高价值掉落震动）—— 这族是 29 个剩余模块里唯一不牵连 iOS 应用源码、中英表与单测的。宿主调用四处收口（`dm/host/hle.h` 的 0x87/0x88 登记行中英各两条 + 枚举两项与尾注、`hle_hostcall.c` 的两个 case、`patch_nso.py` 的两个剪口条目与六行注释）；iOS 端 `dm/ios/Sources/front_ios.m` 第 408–411 行那四行震动块**必须**同批删（它每帧调 `dm_drop_haptic_take`，留着会链接不上；iOS 构建 macOS 专用，本机 NOT RUN，只做逐行检查）。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b11` exit 0，APK 19,118,543 字节（比 trim-b10 小 16,384 字节）；宽口径复核（`-i -e dm_dropfilter -e dm_drophaptic -e dm_drop_haptic -e DM_DROP_LIGHT -e DM_DROPF_LOG`）除 `docs/HANDOFF*` 外 0 命中。
- NA-013 裁剪批 7g（`a4522ed`）：删 `dm/host/dm_textbox.c`、`dm_textbox_core.c` 与 `dm_textbox_core.h`（普通文字框的注释颜色码改写）。**观测门 14 两侧同收**：`dm/host/dm.h` 的枚举去掉 `OBS_TEXTBOX = 14`、`OBS_MAX` 19 → 18，`dm/tools/patch_nso.py` 的 OBS 表里 14 = `0xadc434` 那条一并去掉（只改一侧会撞 `gate_obs_set` 的越界 die）。另清 `diag.c` 的安装调用、`dm_runeword.c` 的对照表改写（`loc_tb` 改原样透传 —— 清单里的名字本来就不在表里，行为不变）、生成器 `annot_strings.py` 不再出那张对照表（`gen_romfs_overlay.py` 的写表调用一并去掉，两个脚本用 `ast.parse` 验过语法）、单测 `t_textbox.c` 与 `dm/host/tests/Makefile` 里它的规则与 run 列表引用。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b12` exit 0，APK 19,085,775 字节（比 trim-b11 小 32,768 字节）；宽口径复核（`-i -e dm_textbox -e OBS_TEXTBOX -e DM_TEXTBOX`）除 `docs/HANDOFF*` 外 0 命中。
- NA-014 裁剪批 7h（`a66b703`）：删 `dm/host/dm_elysium.c` 与 `dm_elysium.h`（「极乐世界」模式：D2R 特有的按角色开关，局内暗金掉率 ×5、套装 ×3）。连带清掉 `diag.c`／`dm_actions.c` 的两处调用与 include、`dm_cursor.c` 的建角页勾选框（触屏与手柄两条路径的读取、Y 键翻勾、「返回」判定里排除那一行的条件）、`dm_cursor.h` 的 `dm_fe_bliss` 声明、`touch_layout.py` 的 `_BLISS` 布局块（函数随之改名 `pad_charopt`）、`dm/i18n/ui_text.tsv` 的三行并**重出** `dm/host/dm_i18n_tab.h`（`dm_i18n.py --check` exit 0，397 条）、`uireg.py` 的「e」局两行勾选框断言与整个 v / v2 两局、`uireg/affected.tsv` 五行的 `v` 标记、两个单测替身桩、README 与白名单行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b13` exit 0，APK 19,003,855 字节（比 trim-b12 小 81,920 字节）；宽口径复核（含中文「极乐世界」）除 `docs/HANDOFF*`／`docs/UPSTREAM_README*`／`docs/TOTK_PORT_SCAFFOLD*` 外 0 命中。**中间失败两次**（都是我的编辑失误：把含 `pl`/`pd` 声明的行整行替换成了注释、摘 Y 键翻勾时少留一个右括号），按编译器定位修回后第三次构建通过，过程与教训已写进日志。
- NA-015 裁剪批 7i（`c0e4fc9`）：删 `dm/host/dm_namegen.c`（起名页留空时按音节拼随机名）与单测 `t_namegen.c`；连带清掉 `dm_actions.h` 的 `dm_name_gen` 声明、`front_ios.m` 起名页那段自动填名（**这是 D2R iOS 产品的一个增强功能下线，原版自带的「随机名字」键仍是玩家入口**）、`dm_cursor.c` 里随之失效的 `g_fe_name_no_accept` 机制、`dm/host/tests/Makefile` 的 `t_namegen` 目标与 `run:` 列表、`dm/host/Makefile` 的 `SRC`、两个 README 表行、`uireg/affected.tsv` 一行。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b14` exit 0，APK 18,987,471 字节（比 trim-b13 小 16,384 字节）；宽口径复核（`-e dm_namegen -e dm_name_gen -e name_gen -e g_fe_name_no_accept`）除 `docs/HANDOFF*` 外 0 命中（文件名与符号名的下划线写法不同，两种形态都查了）。
- NA-016 裁剪批 7j（`7520d35`）：删 `dm/host/dm_bright.c`（「3D 画面加亮」的宿主侧动态曝光：按关卡类型与原版自算的环境亮度算曝光 k = 1–4，每帧喂图形层的 `dm_bright_k()`）；连带清掉 `diag.c` 拍入口的 `dm_bright_server_tick`（顺带删掉测试开关 `DM_TEST_DAYTIME`）、`frontend_activity.c` 的 `dm_bright_load()`、`dm/host/Makefile` 的 `SRC`、两个 README 表行。**图形层刻意不动**：`dm/gfx/nvn/nvn_mtl.m` 的 `bright_lut` 整段保留，宿主强定义摘除后只剩 `__attribute__((weak))` 的缺省 `1.0`，`if (!(k > 1.005f)) return;` 于是不重写调色表 → 画面保持原版亮度。`dm/host/dm_bright_levels.inc` 与 `dm/tools/gen_bright_levels.py` 仍在仓库里但已无人消费，归到后面的「派生表批」一起摘。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b15` exit 0，APK 18,954,703 字节（比 trim-b14 小 32,768 字节）；宽口径复核（`-e dm_bright -e bright_levels -e bright`，文件名与符号两种形态）里 `dm_bright.c` / `dm_bright_load` / `dm_bright_server_tick` / `DM_TEST_DAYTIME` 在代码中 0 命中。**与原计划的偏差**：原 NA-016 写的是「个人仓库 2–5 页」，本批改做 3D 画面加亮，个人仓库那部分并入 NA-017 的仓库族。
- NA-017 裁剪批 7k（`8a23b42`）：整族删掉 `dm/host/dm_vault.c`（编年史仓库服务端）、`dm/host/dm_vault_ui.c`（储藏箱第六页「编年史」的整套 UI）、`dm/host/dm_pages.c`（个人仓库 2–5 页）。连带清掉 `dm_cursor.c` 里三十多处编年史 / 个人仓库引用（落点分类、说明框、拖拽、单击、界面双击存入、`DM_PS_VAULT` 枚举位、`dm_ui_bag_point`、个人仓库页码与左右箭头、切换布局后记页签）、`dm_cursor.h` 的枚举位（其余位取值不变）、`dm_pouch.c` 里「存放」的编年史分支（并把 `dm_item_write` / `dm_item_make` / `dm_memfind` / `dm_item_quest` 搬过来改成 static）、`hle_fs.c` 的提交前钩子（`[4]` 缩成 `[2]`，百宝囊 `[0]`、秘境 `[1]`）、`diag.c` / `dm_actions.c` 的调用、iOS 布局 `wide_stash.py` 的第六页与 `TouchVault` / `TouchPgPage` 控件、中英表 29 行（重出 `dm_i18n_tab.h`，397 → 368 条）、白名单与 `uireg/affected.tsv`、四个 README、单测替身与 `mode_scan.py` / `native_write_scan.py` 的登记。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b16` exit 0，APK 18,708,943 字节（比 trim-b15 小 245,760 字节）；宽口径复核（`-e dm_vault -e dmVault -e dm_pages -e dm_page -e DM_PS_VAULT -e TouchV_ -e PgPage`）在 `dm/host` / `dm/ios` / `dm/i18n` / `dm/android` 的代码里 0 命中（只剩 `dm_pouch.c` 开头那两行「从 dm_pages.c / dm_vault.c 搬过来」的来历说明）；**中间失败一次**（`dm_cursor.c:1425` 的 `!vb` 漏改），已写进日志。
- NA-018 裁剪批 7l（`b7ee3e8`）：整族删掉「百宝囊」——`dm/host/dm_pouch.c`（符文 / 宝石自动拾取进囊、囊里清单、背包「存放」按钮、囊的侧文件）、`dm/ios/tools/pouch_layout.py`（物品栏底部那块百宝囊框与「存放」按钮的布局）、`dm/ios/tools/gen_pouch_art.py`（框贴图生成）。连带清掉 `dm_world.c` / `diag.c` / `dm_cursor.c` 的调用、`hle_fs.c` 的提交前钩子再收一格（`[2]` → `[1]`，秘境进度 `[0]`）、`dm.h` 的 `dm_blob`、自定义开关 `gem_pick` / `store_btn`（`dm_custom.c` 的 `k_keys` / `k_def` / 读盘日志与 `touch_layout.py` 的 `_CUSTOM_KEYS` **两侧行序逐项核对一致**）、中英表 11 行（重出 `dm_i18n_tab.h`，368 → 357 条）、`gen_romfs_overlay.py` / `gen_assets.py` / `run.sh` / `check_hud_gen.sh` / `scan_literals.py` 的管线登记、四个 README。**UI 回归台**：删掉测自动存入的 sa 局，改掉 s 局那几步的判据，并**补上 NA-017 漏掉的一处**——测个人仓库多页与编年史仓库的 `pg1` / `pg2` / `vt1` / `vf1` / `vf2` 五局还在断言已经不会出现的日志，一并删掉，`affected.tsv` 里指向这六局的 13 行局名清掉，`uireg_pick.py` 的核心局清单去掉 `pg2` / `vt1`。**行为变化**：珍宝匣那一页还在，但「仓库页里新落下的符文 / 宝石自动转进高级仓库」与「符文拖进共享页时收包处改道」这两条写在 `dm_pouch.c` 里，随本批没了。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b17` exit 0，APK 18,594,255 字节（比 trim-b16 小 114,688 字节）；宽口径复核（`-e dm_pouch -e dmPouch -e TouchPouch -e TouchStore -e pouch -e gem_pick -e store_btn`）在 `dm/host` / `dm/ios` / `dm/i18n` / `dm/android` 的代码里 0 命中。
- NA-019 裁剪批 7m（`c3fb671`）：整族删掉「iCloud 存档同步」——`dm/host/dm_cloudsync.c`（同步核心）、`dm/ios/Sources/cloud_ios.m`（iOS 侧 ubiquity 容器与 `dm_cloud_boot` / `flush` / `foreground`）、`dm/ios/tools/cloud_guard.sh`（本机测试的云端总闸）、`dm/host/tests/t_cloudsync.c`（同步核心单测）。宿主侧连带清掉三处「只有 iCloud 那一侧设它」的钩子（`hle_fs.c` 的 `g_dm_save_commit_hook`、`dm_uiscreen.c` 的 `g_dm_ingame_hook` 与 `g_dm_charsel_hook`、`diag.c` 的冲突提示调用）、自定义开关 `icloud`（两侧行序逐项核对一致，11 项对 11 项）、中英表两行（重出 `dm_i18n_tab.h`，357 → 355 条）、`project.yml` 的三行 iCloud 权限（**App 组那一行留着** —— 它服务的是苹果托管资源包）、`project_free.py` 的免费账号权限清单（六行 → 三行，正则与计数一起改）、`main.m` / `front_ios.m` 的调用、三个本机 shell 脚本里的总闸（`smoke_mac.sh` / `touch_e2e_mac.sh` / `uireg/run_mac.sh`）、以及 UI 回归台的 `rf3` 局。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b18` exit 0，APK 18,545,103 字节（比 trim-b17 小 49,152 字节）；宽口径复核（`-e dm_cloud -e cloud_ios -e cloud_guard -e icloud -e iCloud -e dmCloud`）在 `dm/` 的代码与文案里 0 命中。**iOS 侧本机编不了**：工程描述、权限、两个 `.m` 与三个 shell 脚本都未经 Xcode 构建 / `bash -n` 验证，已在日志里写明。
- NA-020 裁剪批 7n（`1c11605`）：整族删掉「大秘境 / 佣兵」——`dm/host/dm_rift.c`（1139 行）、`dm_rift.h`、`dm_rift_ui.c`、`dm/ios/Sources/dm_rift_hud.m`、`dm/host/dm_doorspot.h` 与 `tests/t_doorspot.c`、`tests/t_rift_clock.c`、`dm/ios/tools/merc_slots.py`、`dm/ios/tools/gen_merc_art.py`。**四道分支门（0x89 / 0x8c / 0x8d / 0x8e）与三道观测门（15 / 16 / 17）两侧同收**：`hle.h` 的登记与枚举、`hle_hostcall.c` 的分派、`dm.h` 的枚举、`diag.c` 的 `event_msg_obs`、以及 `dm/tools/patch_nso.py` 里那 110 行门块与三行 `obs.append`。顺手修了 NA-013 留下的一个越界：`OBS_MAX` 当时被压成 18，而 18 号门（`OBS_NOTICE_INPUT`）一直在用 —— 宿主 `gate_register` 判 `id >= OBS_MAX` 就 die，带 18 号门的产物一装载就报「观测门编号越界 18」；本批把 `OBS_MAX` 修回 19。「打通秘境解锁技能硬点上限（20 → 40）」整套机制随秘境一起去掉（解锁条件就是 `dm_rift_cleared_any()`），积分牌的「秘境」页（act = 5）也去掉（页签与页数由六项变五项）。`dm_game_notice` 不用搬 —— 原以为 `dm_actions.c` 那个用户要跟着搬，实际那个用户属于技能硬点上限、随机制一起去掉了，剩下的只有首领连战与刷怪积分牌两个用户。中英表删 105 行（重出 `dm_i18n_tab.h`，355 → 250 条），`dm_i18n.py` 的秘境英文长度闸一并摘掉；iOS 侧摘掉编年史页签那一族的秘境内容、积分牌的秘境页与第六个页签、大秘境面板、秘境 HUD 那一画、「佣兵面板底图」那一步；白名单 7 行、`affected.tsv` 3 行、四个 README、单测与 `mode_scan.py` 的登记表同步。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b19` exit 0，APK 18,151,887 字节（比 trim-b18 小 393,216 字节）；宽口径复核（`-e dm_rift -e dmRift -e dmMerc -e gen_merc -e TouchRF -e dmKbRift -e dmSkillCap`）在 `dm/` 下 0 命中。**iOS 侧本机编不了**：布局与资源管线的改动未经 Xcode 构建验证，已在日志写明。
- NA-021 裁剪批 7o（`7db35be`）：整族删掉「首领连战 + 刷怪积分牌」——`dm/host/dm_bossrush.c`（440 行）、`dm_bossrush.h`、`dm/host/dm_kills.c`（325 行）。连带清掉 `diag.c` 的每拍 / 收包 / UI 消息与那行 include、`dm_actions.c` 的积分牌面板泵、**只给这一族用的两样旁路机制**（`hle_time.c` 的强制恐怖地带 `g_dm_tz_time` / `tz_site()`、`hle_hid.c` 的「显示物品」键按下次数 `g_dm_l_presses`）、**只服务这两族的两个函数**（`dm_game_notice` 原版系统提示、`dm_door_label` 门名牌 —— 摘完后没有别的用户，连声明一起没了）、iOS 侧积分牌那一族（`KB_*` / `_kb_*`，注意 `_kb_keys()` 是**从 `dm_kills.c` 正则读名单**的，源文件删了它会直接报错）与编年史页签条的第四项「首领」（**页签条因此回到原版三个**：`tabCount` 3、宽 266、`@Unique` / `@Sets` / `@Runewords`）、中英表 30 行（重出 `dm_i18n_tab.h`，250 → 220 条）、回归台的两局（`kba` / `kbb`）、白名单与 `affected.tsv` 各两行、`native_write_scan.py` 的可见位守卫名单、`mode_scan.py` 的登记表、Makefile 的 `SRC` 两项、两个 README。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b20` exit 0，APK 17,988,047 字节（比 trim-b19 小 163,840 字节）；宽口径复核（`-e dm_bossrush -e dm_kills -e dmBr -e dmKb -e TouchKB -e dm_door_label -e dm_game_notice`）在 `dm/` 下 0 命中。这一批的 `[BEGIN]` 是事后补记的（日志里写明了）。
- NA-022 裁剪批 7p（`52f5953`）：整族删掉「免费回城」——`dm/host/dm_freetp.c`（进局给玩家挂原版回城技能 411、无视回城书直接开门）、触屏回城钮（`dm_touch_controls.c` / `.h` 的 `DM_TC_PORTAL` 枚举项与 `DM_TC_COUNT` 12 → 11、四个 `portal_*` 状态、四个 `dm_tc_*_portal*` 函数、布局 / 按键映射 / 取消手指 / resize / 按下抬起那几处）、iOS 侧（`DmTouchOverlay.m` 的钮与两张按枚举序排的数组、`front_ios.m` 的请求与「修饰键发布」状态、`dm_gamepad.m` 的 ZR 空键接管、`app_mac.m` 的 `dm_front_navigation`），以及回城钮那套**两阶段收据协议**（`input_pair_check.py` 的 `validate_portal` 与组合配对、`test_input_pair_check.py` 的 35 条用例、`test_touch_receipt.py` 的 `portal_sequence` 源）与其单测（`t_portal_sequence.c` / `test_portal_receipt.py` 删掉）。顺带恢复：手柄「重新绑定技能」框回到原版六列（第六列 ZR 原是为回城快捷键留的）。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b21` exit 0，APK 17,955,279 字节（比 trim-b20 小 32,768 字节）；**iOS 触控层的五个 C 单测本机用 MinGW `cc -std=c11 -Wall -Wextra -Werror` 编过并跑过**（`t_touch_controls` 通过、`t_skill_aim` 76/76、`t_binding_freshness` 8/8、`t_joy_travel` 48 项、`t_native_binding` 编译通过但运行要夹具）；`test_input_pair_check.py` 32/32 通过。**这一批自造了三处编译级破坏**（删注释时把 `*/` 一起删、删 `dm_tc_resize` 时把函数体删空、删单测用例时把后面的 `dm_tc_resize` 一起删），是上面那套 `-Werror` 编译检查抓出来的 —— **Android 构建不带 `-Werror`，只当警告放过**，教训已写进日志。
- NA-023 裁剪批 7q（`cc279c2`）：**派生表批** —— 三张「从游戏文件生成、内容不编进程序」的表里，编年史仓库表与关卡亮度表的宿主消费方已分别随 7k / 7j 摘掉 → 只剩经验表（`dm/host/dm_hud_exp.h`，底栏经验条用，`diag.c` 还在 `#include`）。本批把那两张表的替身（`dm_vault_tab.h` / `dm_bright_levels.inc`）、生成器（`gen_vault_table.py` / `gen_bright_levels.py`）、`shell_stubs.py` 里的替身清单与解析、`derived.tsv` 里 `VTPART`/`VTROW`/`VTSET`/`BRT` 四类行、以及 `make_package.py` / `build_package.py` / `Makefile` / `run.sh` / `gen_assets.py` / `d2rm_pack.py` / `check_hud_gen.sh` 的登记一起摘掉，派生表管线收缩成「经验表 + 技能图标索引」两张。顺手修了两处：`check_hud_gen.sh` 的「不许提交」清单里还留着**故意提交**的经验表替身（留着就每次都报红）；`shell_stubs.py` 判「这是不是替身」看的是 `k_exp[100]` 字符串在不在（替身里恰好有 `static uint32_t k_exp[100];` → 判不出来、脚本崩在 AttributeError），改成看真正的初始化式 `k_exp[100] = {`。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b22` exit 0，APK 17,955,279 字节（与上一版同大小 —— 派生表是替身、内容不进包）；**本机不用游戏文件就验了管线**：造一份「真实表」样式的 `dm_hud_exp.h` 跑 `shell_stubs.py data` → exit 0、`derived.tsv：经验 100、技能索引 0`、写出 10 行 `EXP`；`shell_stubs.py stubs` 写出的经验表替身与仓库里那一份逐字相同。**分两次提交**（协议：控制面单独提）：`cc279c2` = 业务代码，`ci_checks.py` + HANDOFF + LOG 走第二个提交。
- NA-024 裁剪批 7r（`c3fb671`）：整族删掉「符文之语助手」——`dm/host/dm_runeword.c`（91 KB：把原版符文之语做成可翻页 / 可看细节 / 可一键镶嵌的清单面板，宿主自绘）与其布局（`touch_layout.py` 的 `TouchRw*` 那一族控件、`_RW` / `_inv_rw` / `pad_inv_rw` / `_rw_children_check`）、iOS 侧（`front_ios.m` 触点脚本的「await rw」指令）、宿主各处的调用与登记（`dm_cursor.c` 的清单命中与长按分支、`dm_actions.c` 的每拍泵、`diag.c` 的 UI 消息、`hle_hid.c` 的手柄过滤、`dm_mode_items.h`）、中英表四行（**220 → 216 条**）、单测替身桩与 `mode_scan.py`、回归台四局（`rw1` / `rw2` / `rwp` / `rwd`）与 `affected.tsv` / `usage*.md` / `uireg_pick.py`、白名单五行。**`dm_swapskill`（技能组切换）没动** —— 那是覆盖层上的独立开关；**「k 局」保留** —— 它测的是原版自己的镶嵌。证据：`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b23` exit 0，APK 17,775,055 字节（比 trim-b22 小 180,224 字节）；宽口径复核（`-e dm_runeword -e TouchRw -e dmRw -e "await rw"`）在 `dm/` 下 0 命中；`touch_layout.py` 本机 `py_compile` 通过。
- NA-025 裁剪批 7s（`1b9b1e4`）：删除 `dm/host/dm_custom.c` / `.h`，摘掉宿主调用、iOS 自定义页布局与 15 行 `dmCustom*` 文案，语言开关按方案 (b) 一并移除（`hle_fs.c` 的 `settings_lang_apply` 删除，`dm_sys_lang()` 生产恒为简中，`DM_LANG` 仅作测试模拟）；基础覆盖层改为常驻物品注释，Android `nvn_vulkan.c` 的帧率接口固定 60。证据：`build.py --game-run --version trim-b24` exit 0、APK 17,725,903 字节；`dm_i18n.py --check` exit 0（201 条）；`scan_literals.py` exit 0（295 条）；`mode_scan.py` exit 0；宽口径 grep 在 `dm/host` / `dm/ios` / `dm/i18n` 代码与文案 0 命中；业务提交 `1b9b1e4` 已推送，HEAD 与 origin 相同。
- NA-027 TotK 文件准备 + M0 勘察（`becd40b`）：用户提供了 TotK v1.4.2 合并 XCI（17,677,626,368 字节，Title ID `0100F2C0115B6000`）与 `prod.keys`；本机原先没有 `hactool`，已从上游发布版取得 1.4.0 win-x64 到仓库外 `D:\Switch\.tools\hactool`。**hactool 1.4.0 解不开更新包的 NCA3 BKTR 补丁段**（`Invalid BKTR layout!`），因此新写了 `dm/tools/switch_nca.py`（纯 Python，按 hactool 的 NCA3 头 XTS / 段 CTR / PFS0 / RomFS 算法重写，只依赖 pycryptodome + numpy）与 `dm/tools/nso_stats.py`（NSO 段、MOD0 动态表、符号 / 重定位统计）。实测数据：更新包（v1.4.2）四个模块的构建号 = main `5cb42b1cf25469fb0635fd046453d843`、sdk `5cf080e800530a7f25bd528ec875c27b`、subsdk0 `3308c1d216f788397d1451c8345a16cd`、rtld `82a3cf78789f9d9858c52379d8d2d129`（本体 v1.0.0 的 main 是 `082ce09b06e33a123cb1e2770f5f9147`）；模块 = main 45,769,200 / sdk 6,693,520 / subsdk0 3,501,008 字节 text + rtld 9,536 字节；动态符号合计 33,858（导入 1,356）、重定位合计 36,747；NVN 取址函数 534 个（D2R 是 523），加载函数在 main 的 0xbbfa90，槽走间接指针表；RomFS = 304,207 个文件 / 15.87 GB。证据：`switch_nca.py info/exefs/romfs-list/romfs-extract` exit 0（本体 ExeFS 与 hactool 逐字节一致）、`nso_stats.py` exit 0、`build.py --game-run --version trim-b25` exit 0、APK 17,725,903 字节、`ci_checks.py` 10 / 0。**本批 NOT RUN**：更新包 RomFS 的 BKTR 补丁应用（还没实现）、着色器包解码（缺任天堂 zstd 字典）、真机（一加 12 未接）。
- NA-028 规则域接 TotK（`a70f0ef`）：`dm/tools/patch_nso.py` 的 `DM_RULESET=totk-run-v1` 从「空表占位」改成**按 TotK 真实构建号取表**（TOTK_BUILDS = main `5cb42b1cf25469fb0635fd046453d843` / sdk `5cf080e800530a7f25bd528ec875c27b` / subsdk0 `3308c1d216f788397d1451c8345a16cd` / rtld `82a3cf78789f9d9858c52379d8d2d129`），构建号不符即中止；CUTS / OBS / PARAMS 给 TotK 的 main 登记空表（空表是当前正确状态）。**M1 前提修正**：实测 TotK 的 main 把 x18 当**普通寄存器**用（.text 里 24,204 条指令提到 x18、18,572 条提到 w18，例如 0x3f00 `add x18, x19, #0x260`、0xa761c `stxr w17, w18, [x10]`），D2R 那套「x18 = TLS 指针」的语义前提对 TotK 不成立；但上游的机制本质是**每线程把客体 x18 存进线程槽 K18**，对普通寄存器同样成立，而 Android 宿主本来就保全 x18（`dm/android/native/probe.c` 逐次检查宿主调用前后 x18 不变；Linux AArch64 ABI 不用 x18），所以 **TotK 规则域不做 x18 改写、宿主侧也不用改** —— D2R 的行为一字未动。证据：`DM_RULESET=totk-run-v1` 对四个模块全部 exit 0，产出第一份 TotK 改写映像（main 61,760,960 / sdk 12,984,320 / subsdk0 6,750,208 / rtld 66,136 字节）与门清单：**sdk 58 个不同 svc 号 + 42 个计时器门 + 124 处 TLS 区读 + 2 处 TLS 读 + 3 处 TLS 写，main 814 处 TLS 读，rtld 5 个 svc（与 sdk 重叠）**；`ci_checks.py` 10 / 0；`build.py --game-run --version trim-b26` exit 0。
- NA-029 上游同步（见下面日志条目）：上游 `jhaizhou-ops/d2r-mobile` 的 main 已比本 fork 新（其 `dm/tools/patch_nso.py` 88,578 字节 vs 我们 72,377，283 行差异）。差异分三类：① D2R 玩法剪口（我们裁剪批次已删）② Android 宿主改造（我们独有）③ **可直接用的上游改进**。采纳了第三类里的 **#55 寄存器字段预筛**（扫描时先看四个寄存器字段有没有 18，命中才反汇编；上游口径 7,201,192 → 189,399 个候选、三个模块一趟 78.5s → 20.2s）。验证：① 按上游口径在 TotK 的 main 上独立复核 —— 11,442,300 字 → 322,813 候选（2.82%）→ 42,776 处 x18/w18，**漏 0、多 0**；② 仓库自带 `dm/android/tests/test_rewriter.py`（unicorn 逐条比对原指令与改写后语义，含 ldxr/stxr 独占窗口用例）**exit 0**。未采纳并说明理由：上游的西班牙语界面、社区修复（Mac 悬停提示 / iCloud 启动 / 快速操作 / Xcode 26.2）、loader 空弱引用修复等都是 D2R 产品侧改动，与 TotK 移植无直接关系；其中「Mac 着色器反射 JSON 按目录拷贝」（#60）与 §4.4 相关，列入待查。
- NA-030 TotK 模块进 Android 装载链（见下面日志条目）：用 `DM_RULESET=totk-run-v1 DM_TARGET=android` 重跑改写器（四个模块全部 exit 0），再用 `dm/android/tools/guest_elf.py` 把 main / sdk / subsdk0 打成 `libdmguest_*.so`（61,817,600 / 13,009,664 / 6,767,368 字节，`.target` = `android-context-v1` ✓）；再照 `dm/android/native/game_modules.c` 的 `parse()` 复刻宿主解析，三个模块全部读出：符号 706 / 23,039 / 10,110（合计 33,855）、重定位 2,070 / 19,027 / 15,648（合计 36,745）、导入 680 / 9 / 664（合计 1,353），与 NA-027 的离线统计对得上。**跨模块未解析只剩 9 个符号，且全是 `glslc*`**（NVIDIA 的运行时 GLSL 编译器 API：`glslcInitialize` / `glslcCompile` / `glslcCompilePreSpecialized` / `glslcCompileSpecialized` / `glslcFinalize` / `glslcGetDefaultOptions` / `glslcGetVersion` / `glslcSetAllocator`）——D2R 没有这个需求。宿主的 `resolve_import`（`dm/host/hle.c`）对模块外导入有**未实现桩兜底**，所以这 9 个不会挡住装载，只会在 HLE 审计里记成 STUB（真机跑起来后用 `DM_HLECOUNT` 看有没有被调用过）。**本批 NOT RUN**：真机上的实际装载与进 `nnMain`（一加 12 未接）。
- NA-031 模块来源接规则域 + HLE 缺口普查（`48f5d1f`）：`make_package.py` 新增 `--ruleset` / `--exefs` / `--modules-only`，TotK 侧一条命令出模块（`--ruleset totk-run-v1 --exefs <目录> --modules-only` exit 0，产物 `game/` 里是三个 `libdmguest_*.so` 与 `{name}.fixups/gates.tsv`，正是数据包要的形态），D2R 路径一字未变。**HLE 缺口普查（关键结论）**：TotK 三模块未定义导入 1,266 个，宿主已有的 HLE_FORCE 表（173 条）覆盖 66 个，**真正缺的只有 8 个 `glslc*`**（NVIDIA 运行时 GLSL 编译器 API，D2R 没有这个需求）；宿主的「未实现桩」是良性的（记一次日志、返回 0，不中止），所以符号层不用改宿主。另外把 58 个 svc 号与宿主覆盖面对了一遍：宿主有 case 的 34 个，**没有 case 的 24 个**是 #19 MapSharedMemory、#20 UnmapSharedMemory、#21 CreateTransferMemory、#31 ConnectToNamedPort、#33 SendSyncRequest、#34 SendSyncRequestWithUserBuffer、#35 SendAsyncRequestWithUserBuffer、#50 SetThreadActivity、#51 GetThreadContext3、#54 SynchronizePreemptionState、#64 CreateSession、#65 AcceptSession、#67 ReplyAndReceive、#68 ReplyAndReceiveWithUserBuffer、#75 CreateCodeMemory、#81 MapTransferMemory、#82 UnmapTransferMemory、#112 CreatePort、#114 ConnectToPort 等（名字取自 Ryujinx 的 `[Svc(0x..)]` 枚举）——它们多是 Horizon IPC，而 D2R 宿主是直接接管**服务客户端函数**（HLE_FORCE）而不走 IPC，所以真机上的实际缺口预计远小于 24 个。
- NA-032 §4.4 着色器事实表来源（`944681d`）：**任天堂的 zstd 字典就在游戏自己里** —— `/Pack/ZsDic.pack.zs` 是个 SARC装着 3 份 128 KB 字典（`zs.zsdic` id=1、`bcett.byml.zsdic` id=2、`pack.zsdic` id=3），着色器包的 zstd 帧头写着自己要 id=1；之前「Dictionary mismatch」的死结由此解开。用新写的 `dm/tools/switch_shaders.py` 解出全部着色器归档：`ApplicationPackage.Nin_NX_NVN.release.sarc.zs` → SARC 19 个条目（含 `AglShader.sharcb` 794,624 字节等），12 个 `*.bfsha.zs` → FSHA 容器（`material...` 解出 101,165,712 字节），条目里带 `cTexSrc`、`gl_InstanceID`、`grass_shader` 这类**反射元数据字符串** —— 也就是 D2R 那条「从 PC 版反射冻结事实表」的路对 TotK 不成立，但**从游戏自带的着色器归档取**这条路成立（方案 D 可行），§4.4 的 go/no-go 风险基本解除。
- NA-032 着色器事实表（第一半，`a25ccc3`）：按确认的归档格式自己写了 `dm/gfx/tools/totk_shaders.py`（BNSH / FSHA / BAHS v9 三种容器 → 逐着色器解出控制头、机器码与 C1，算出**着色器键** = `sha256(control+program+c1)[:16]`、阶段、控制头尺寸）。实测：`/Shader` 归档里 49,089 条记录、**9,807 个唯一键**（cs 18 / ps 5,557 / vs 4,232）；**计算着色器的线程组与共享内存直接从控制头 0x748 读出**（如 64x1x1、8x8x1、1x1x1，共享内存 0 / 2048 字节）—— 这类事实**不需要 PC 反射**，TotK 侧直接可得。贴图维度 / 图像格式 / 属性分量类型的位置还没定位（C1 块很小，多半在控制头的描述符表），仍按方案 A / B 走。
- `agent_handoff_check.py --verify`：exit 0；负向测试确认 HEAD 不一致、密钥样式、未闭合 BEGIN 均被拒绝。

### 代码工作区（排除交接控制面）

```text
```

## 下一步唯一动作

- ID：NA-032
- 状态：READY
- 工作目录：`D:\Switch\d2r-android`
- 前置条件：HEAD / origin 均为 NA-032 的业务提交（见 frontmatter）；代码工作区干净；着色器归档已能解出（`D:\Switch\totk-work\shaders-out\`，30 个文件 + `manifest.json`）。
- 动作：把解出的着色器归档解析成**事实表**（贴图维度类型 / 格式、顶点与片元输出的分量类型、计算着色器的线程组大小与共享内存），并让仓库现有的翻译链吃下 TotK 的着色器：① 先摸清 FSHA 容器与 `*.sharcb` / `*.bfsha` 内层 BNSH 二进制的结构（从 `manifest.json` 与二进制头出发，参考外部项目 `OJZen/totk-mobile` 的 `script/index_shaders.py` / `build_shader_ir.py` 的思路，**代码自己写**）；② 产出 TotK 版的事实表（与 `dm/gfx/tools/dmsh_facts.py` 现有表同格式，落在仓库外，接口信息入库要先开 Issue）；③ 用一条小批量（几十个着色器）验证「翻译 → SPIR-V → 能出图」这条路。
- 命令或编辑目标：先 `git grep -n -e shader_facts -e dmsh_facts -- dm/gfx/tools` 看现有事实表的格式与消费方，再写一个解析脚本（放 `dm/tools/` 或 `dm/gfx/tools/`，按仓库规矩命名），用 `D:\Switch\totk-work\shaders-out\` 里的文件跑；随后 `ci_checks.py`、`build.py --game-run --version trim-b28`。
- 成功判据：能从一批 TotK 着色器里读出维度 / 格式 / 线程组等事实并写成与现有事实表同格式的表；对同一批着色器跑翻译链能产出 SPIR-V 且不报「缺事实」；`ci_checks.py` 10 项通过 / 0 项失败；`build.py --game-run --version trim-b28` exit 0 且产出 APK。
- 失败判据：解析不出事实（说明游戏自带归档里没有这些信息 → §4.4 需要改走方案 A/B，**如实记录并改结论**）、翻译链吃不下、任一验证命令非零 —— 此时回滚本批并更新计划 §4.4 的结论。
- 回滚点：见 frontmatter `observed_head` / `totk/scaffold`。
- 需要写入的证据：FSHA / BNSH 的结构证据（偏移与字段）、事实表的条目数与样例、翻译批量的输出与错误、`ci_checks.py` 计分行、构建退出码与 APK 路径大小、`git status --short`、提交号、HANDOFF / LOG 更新与 `--verify` 退出码。**本机 NOT RUN 的部分**：真机上的实际出图（一加 12 未接）、iOS / macOS 侧编译。
- 顺带记下（下一步之后要做）：改写器要按 TotK 适配两处形态 —— ① **多入口独占窗口**（一个 LL/SC 区域可以有多个 load 入口共享一个 store，外部分支还能跳进区域中间；做法是给每个入口各发一段序言，外部跳进来的目标也要有入口），② **`blr x18`**（TotK 用 x18 当函数指针调用，需要专门的站点处理）。参考实现见 `OJZen/totk-mobile` 的 `tools/patch_module.py` + `tools/exclusive.py`（Apache-2.0，**只读思路、代码自己写**）。该项目的 v1.4.3 main 构建号是 `277178b7dba1b6d4949a84778d4abc58`（我们是 v1.4.2 的 `5cb42b1c…`），它的跳转表是**有符号**的、按 v1.4.3 的地址写死，TotK v1.4.2 的对应表要自己定位。

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
- `8965544`：交接控制面 —— NA-001 快照与日志。
- `b54f782`：裁剪批 1 —— 删除 `dm/host/hle_tact.c`，宿主调用分派器拆到 `dm/host/hle_hostcall.c`。
- `1a2f535`：裁剪批 2 —— 删除 bootlist 清单工具与其验收项。
- `62139f0`：裁剪批 3 —— 删除 D2R 专属的 Granny 段解码。
- `bf7b33f`：裁剪批 4 —— 删除 vendored `dm/third_party/libdeflate`。
- `abb0040`：裁剪批 5 —— 删除 D2R 专属的过场 movie 空播剪口。
- `4392313`：裁剪批 7a —— 删除 D2R 的转向回跳平滑与商人「刷新货架」。
- `6b261f7`：裁剪批 7b —— 删除 D2R 的掉落过滤与增益自动补。
- `b4d3557`：裁剪批 7c —— 删除 D2R 的「开背包自动补腰带」。
- `89a38ec`：裁剪批 7d —— 删除 D2R 的药水自动拾取（含 `diag.c` 里的服务端一道）。
- `ead836a`：裁剪批 7e —— 删除 D2R 的进局小站落点。
- `c9aadb8`：裁剪批 7f —— 删除 D2R 的高价值掉落光柱 / 落地音 / 掉落震动。
- `a4522ed`：裁剪批 7g —— 删除 D2R 的文字框注释颜色码改写（含观测门 14）。
- `a66b703`：裁剪批 7h —— 删除 D2R 的「极乐世界」模式。
- `c0e4fc9`：裁剪批 7i —— 删除 D2R 的起名页随机取名。
- `7520d35`：裁剪批 7j —— 删除 D2R 的「3D 画面加亮」。
- `8a23b42`：裁剪批 7k —— 删除 D2R 的编年史仓库与个人仓库多页。
- `b7ee3e8`：裁剪批 7l —— 删除 D2R 的百宝囊。
- `c3fb671`：裁剪批 7m —— 删除 D2R 的 iCloud 存档同步。
- `1c11605`：裁剪批 7n —— 删除 D2R 的大秘境与佣兵。
- `7db35be`：裁剪批 7o —— 删除 D2R 的首领连战与刷怪积分牌。
- `52f5953`：裁剪批 7p —— 删除 D2R 的免费回城。
- `cc279c2`：裁剪批 7q —— 派生表批（只留经验表）。
- `c3fb671`：裁剪批 7r —— 删除 D2R 的符文之语助手。

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

1. ~~提交交接控制面~~ —— 完成（`c405782`、`8965544`）。
2. ~~提交两处 TotK 适配代码~~ —— 完成（`1d915ab`）。
3. 小步裁剪 D2R 专属资产，每批后跑 `ci_checks` 与完整 `build.py --game-run`：批 1 = 宿主侧 TACT/CASC —— 完成（`b54f782`）；批 2 = bootlist 清单工具与验证面 —— 完成（`1a2f535`）；批 3 = Granny 段解码 —— 完成（`62139f0`）；批 4 = vendored `dm/third_party/libdeflate` 与文档行 —— 完成（`bf7b33f`）；批 5 = 过场 movie 空播 —— 完成（`abb0040`）；批 6 = D2R 的 CUTS/OBS 表 + `casc_overlay.py` + iOS 资产管线（与 §4.3/§4.4 合并做，阻塞在用户材料）；批 7 = 36 个 `dm_*.c` 与派生表 / i18n 表 —— 分小批推进，7a = 转向回跳平滑 + 商人「刷新货架」—— 完成（`4392313`）；7b = 掉落过滤 + 增益自动补 —— 完成（`6b261f7`）；7c = 开背包自动补腰带 —— 完成（`b4d3557`）；7d = 药水自动拾取 —— 完成（`89a38ec`）；7e = 进局落在城镇小站旁 —— 完成（`ead836a`）；7f = 高价值掉落光柱 / 落地音 / 掉落震动一族 —— 完成（`c9aadb8`）；7g = 普通文字框的注释颜色码一族 —— 完成（`a4522ed`）；7h = 极乐世界模式 —— 完成（`a66b703`）；7i = 起名页随机取名 —— 完成（`c0e4fc9`）；7j = 3D 画面加亮 —— 完成（`7520d35`）；7k = 仓库族（编年史仓库 + 个人仓库 2–5 页）—— 完成（`8a23b42`）；7l = 百宝囊 —— 完成（`b7ee3e8`）；7m = iCloud 存档同步 —— 完成（`c3fb671`）；7n = 大秘境 / 佣兵族 —— 完成（`1c11605`）；7o = 连战 + 积分牌 —— 完成（`7db35be`）；7p = 免费回城 —— 完成（`52f5953`）；7q = 派生表批 —— 完成（`cc279c2`）；7r = 符文之语助手 —— 完成（`c3fb671`）；7s = iOS 自定义页（NA-025）；批 7 的后续按同一模式：每个模块连同它的观测门、调用点、文档与白名单一起摘。
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
| 裁剪 D2R 资产波及两套构建系统 | 删文件会断宿主链接或改写器登记 | 批 1 已按此处理；后续批次同样以完整 build 兜底 |
| `casc_overlay.py` 被 Android 着色器构建 import | 直接删除会断 `build_shaders.py` | 已探明；拆除前须先改造该脚本（批 3） |

## 必须遵守的边界

- 只能使用用户自己拥有的 TotK 副本，从自己的主机导出。
- 不提交游戏程序、美术、着色器、存档或由其生成的表和图。
- 不回显 `prod.keys` 内容。
- Ryujinx 着色器翻译与 Eden 胶水是 GPL-3.0；本仓库是 MIT，只能参考思路，不能拷代码。
- 性能与正确性结论必须写明机型、场景、热机状态；没跑就写 `NOT RUN`。
- 构建号、CUTS/OBS、NVN 表、着色器事实表、驱动配置必须按 TotK 重新验证。