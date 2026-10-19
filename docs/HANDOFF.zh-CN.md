---
protocol: 1
updated_at: 2026-10-19T22:50:59+08:00
phase: M0
state: ACTIVE
branch: totk/scaffold
observed_head: c0e4fc981832067c90d8039d9aeb47ec29592c6d
origin_ref: origin/totk/scaffold
origin_head_at_checkpoint: c0e4fc981832067c90d8039d9aeb47ec29592c6d
code_worktree: CLEAN
next_action_id: NA-016
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

- 快照时间：2026-10-19 22:50（Asia/Shanghai）
- 当前阶段：M0 准备 / 脚手架
- 当前分支：`totk/scaffold`
- 观测 HEAD：`c0e4fc981832067c90d8039d9aeb47ec29592c6d`（快照基线；允许是当前 HEAD 的祖先）
- origin 对应分支：`origin/totk/scaffold`，检查点为 `c0e4fc981832067c90d8039d9aeb47ec29592c6d`（与观测 HEAD 相同）
- 代码工作区：`CLEAN`（排除交接控制面）
- 未提交代码文件：无
- 未跟踪代码文件：无
- 被忽略但重要的产物：`dm/android/build/D2R-Android-port.apk`（`trim-b14`，18,987,471 字节）
- 本次会话目标：执行 NA-015 —— 摘掉起名页的随机取名（裁剪批 7i）。
- 已完成（带证据）：见下方「已完成清单」。
- 未完成：裁剪批 7j（个人仓库 2–5 页，见 NA-016）；23 个 `dm_*.c` 的其余部分 —— 秘境 UI / 仓库与百宝囊 / 首领连战 / 刷怪积分牌几族彼此纠缠且牵连 `dm/i18n/ui_text.tsv` 文案与 `touch_layout.py` 面板，宜整族一次做完；16 个牵连 `dm/ios/Sources/*` 的 iOS 应用源码（本机构建验证不了，宜合批或等 TotK 侧重建 iOS 前端）；D2R 的 CUTS/OBS 表与 `casc_overlay.py` + iOS 资产管线（与 §4.3/§4.4 合并做，阻塞在用户材料）；`dm_custom.c` 的 `k_keys` 位置数组里已死键与 iOS 自定义页（TotK 侧整页重建时一起消失）；TotK 的过场策略（摘掉 D2R 的空播实现后 TotK 会走游戏自己的 movie 路径，宿主侧 movie 支持待定）；TotK 文件准备；M0 实测；着色器事实表来源。
- 最近一次成功命令：`dm\android\tools\ci_checks.py` exit 0（10 项通过 / 0 项失败）；`dm\android\tools\build.py --game-run --version trim-b14` exit 0；`tools\agent_handoff_check.py --verify` exit 0。
- 最近一次失败命令及原因：本轮无仓库命令失败；`dm\verify\test_accept.py` 与 `dm/host/tests/Makefile` 的 macOS 测试面在本机跑不了（NOT RUN，同上一轮的 WSL `bash` 限制），已在对应动作的判据里写明。
- 已验证产物路径：`D:\Switch\d2r-android\dm\android\build\D2R-Android-port.apk`（18,987,471 字节，2026-10-19 22:49:28，`trim-b14`）
- 当前阻塞：缺少用户合法导出的 TotK 文件、`prod.keys`、`hactool`；`adb devices` 无设备。
- 需要用户提供的材料：自己的 TotK 本体 + 更新、`prod.keys`、可用 `hactool`、一加 12（开启 USB 调试）。
- 回滚点：`c0e4fc981832067c90d8039d9aeb47ec29592c6d` / `totk/scaffold`。
- 禁止事项：不得提交游戏内容、密钥、存档或构建产物；不得删除未提交代码；不得把 D2R 数据当作 TotK 数据。

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
- `agent_handoff_check.py --verify`：exit 0；负向测试确认 HEAD 不一致、密钥样式、未闭合 BEGIN 均被拒绝。

### 代码工作区（排除交接控制面）

```text
```

## 下一步唯一动作

- ID：NA-016
- 状态：READY
- 工作目录：`D:\Switch\d2r-android`
- 前置条件：`totk/scaffold` 的 HEAD 与 `origin/totk/scaffold` 同为 `c0e4fc981832067c90d8039d9aeb47ec29592c6d`；代码工作区干净；`HANDOFF_LOG` 无未闭合 `[BEGIN]`。
- 动作：裁剪批 7j —— 摘掉「个人仓库 2–5 页」（`dm/host/dm_pages.c`）：D2R 的编年史仓库附加页（仓库本体 `dm_vault.c` 保留，只摘个人页这个子功能）。它是 23 个剩余模块里既不牵连 iOS 应用源码、也不牵连 `dm/i18n/ui_text.tsv` 文案与 `touch_layout.py` 面板的少数几个之一，代价最低。
- 命令或编辑目标：先 `git grep -n -e dm_pages -e 'dm_page' -- .` 全量复核（**前缀与符号名两种形态都要查**）；再 `git rm dm/host/dm_pages.c`（若另有同名头文件一并删）；同一提交内修正 `dm/host/diag.c`（每拍调用）、`dm/host/dm.h`（声明）、`dm/host/dm_cursor.c`、`dm/host/dm_vault.c`、`dm/host/hle_fs.c`（存档挂载 / 提交前的钩子位）里对它的调用与声明、`dm/host/tests/` 下两处替身（`t_touch_mac.c`、`t_touch_tick_stub.c`）、`dm/host/Makefile` 的 `SRC` 一项、`dm/host/README.md` 与 `README.zh-CN.md`（表行）、`dm/ios/tools/uireg/affected.tsv`（相关行）、`dm/i18n/literal_whitelist.tsv`（若有其行）；然后按「标准验证命令」跑 `dm\android\tools\ci_checks.py`（带 `DM_ANDROID_TOOLS=D:\Switch\.tools\android`）、`dm\android\tools\build.py --game-run --version trim-b15`、`tools\agent_handoff_check.py --verify`；最后 `git add -A`、`git commit -m "totk: drop D2R personal stash pages"`、`git push`。
- 成功判据：`ci_checks.py` 10 项通过 / 0 项失败；`build.py --game-run` exit 0 且产出 APK；`git grep -n -e dm_pages -- .` 除 `docs/HANDOFF*` 外 0 命中；`dm/host/hle_fs.c` 里那组「提交前钩子」不再有空位（摘掉后要确认没有留下未使用的槽位或悬空引用）；提交只含本批文件；`git rev-parse HEAD` 与 `git rev-parse origin/totk/scaffold` 相同。**本机 NOT RUN 的部分**：`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）在本机跑不了，涉及 `dm_cursor` 的宿主单测未经本机执行验证；`ci_checks.py` 不覆盖该目录。
- 失败判据：任一验证命令非零退出，或 `ci_checks.py` 出现失败项；APK 未产出；提交混入 `casc_overlay.py`、`dm/data/**`、其余 `dm_*.c` 或交接控制面文件。
- 回滚点：`c0e4fc981832067c90d8039d9aeb47ec29592c6d` / `totk/scaffold`（单次提交，必要时 `git revert`）。
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
3. 小步裁剪 D2R 专属资产，每批后跑 `ci_checks` 与完整 `build.py --game-run`：批 1 = 宿主侧 TACT/CASC —— 完成（`b54f782`）；批 2 = bootlist 清单工具与验证面 —— 完成（`1a2f535`）；批 3 = Granny 段解码 —— 完成（`62139f0`）；批 4 = vendored `dm/third_party/libdeflate` 与文档行 —— 完成（`bf7b33f`）；批 5 = 过场 movie 空播 —— 完成（`abb0040`）；批 6 = D2R 的 CUTS/OBS 表 + `casc_overlay.py` + iOS 资产管线（与 §4.3/§4.4 合并做，阻塞在用户材料）；批 7 = 36 个 `dm_*.c` 与派生表 / i18n 表 —— 分小批推进，7a = 转向回跳平滑 + 商人「刷新货架」—— 完成（`4392313`）；7b = 掉落过滤 + 增益自动补 —— 完成（`6b261f7`）；7c = 开背包自动补腰带 —— 完成（`b4d3557`）；7d = 药水自动拾取 —— 完成（`89a38ec`）；7e = 进局落在城镇小站旁 —— 完成（`ead836a`）；7f = 高价值掉落光柱 / 落地音 / 掉落震动一族 —— 完成（`c9aadb8`）；7g = 普通文字框的注释颜色码一族 —— 完成（`a4522ed`）；7h = 极乐世界模式 —— 完成（`a66b703`）；7i = 起名页随机取名 —— 完成（`c0e4fc9`）；7j = 个人仓库 2–5 页（NA-016）；批 7 的后续按同一模式：每个模块连同它的观测门、调用点、文档与白名单一起摘。
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