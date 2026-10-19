# Agent 交接会话日志

> 只追加，不覆盖。最新记录放在最上方。
> 当前状态以 [HANDOFF](HANDOFF.zh-CN.md) 为准。
## 2026-10-19 22:35 Asia/Shanghai — [TOTK] NA-010 裁剪批 7d（药水自动拾取）进行中

[BEGIN] na-010-potpick-trim

- 命令：`git rm dm/host/dm_potpick.c`、拆掉 `diag.c` 里织着的六处（两处日志语义、`potpick_gate` 函数与调用、`pk_auto` 变量）、`dm_world.c` 调用行、`dm_custom.h` 键注释、`Makefile` 的 `SRC`、两个 README 表行、`uireg` 行，然后 `ci_checks.py` + `build.py --game-run --version trim-b9` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉药水自动拾取（含它在 `diag.c` 里的服务端一道与日志语义）后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`bc9c783c230f9a4f2bd6bfe256a61b01bc138b32`
[END] na-010-potpick-trim

- 退出码：`build.py --game-run --version trim-b9` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,151,311 字节（2026-10-19 21:40:16；比 trim-b8 小 16,384 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e dm_potpick -- dm`：0 命中（用前缀查）。
- 删除：`dm/host/dm_potpick.c`（药水自动拾取；只有 `dm_potpick_step`／`dm_potpick_auto` 两个导出符号，无观测门、无构造器）。
- 这一批与前几批不同：功能本体织在 `dm/host/diag.c` 里，所以同批拆掉六处 ——
  · 第 1294–1295 行的日志：`dm_potpick_auto(id) ? "药水自动拾取发的" : "玩家点的"` 改成恒为「玩家点的」，格式串去掉一个 `%s`；
  · 第 1298–1301 行四行「药水自动拾取的服务端一道」注释；
  · 第 1302–1314 行的静态 `potpick_gate` 函数（自动拾取专用的服务端一道：放不进腰带就丢包）；
  · 第 1338 行的 `if (potpick_gate(regs)) return;`；
  · 第 1348–1351 行的 `pk_auto` 变量与它的计算；
  · 第 1359–1360 行两条拾取日志里的 `pk_auto` 与格式串。
- 其余：`dm/host/dm_world.c` 的 `dm_potpick_step` 调用行、`dm/host/dm_custom.h` 第 7／10 行键注释里的 `pot_pick 药水自动拾取（dm_potpick.c）` 条目、`dm/host/Makefile` 的 `SRC` 一项、`dm/host/README.md` 与 `README.zh-CN.md` 的表行、`dm/ios/tools/uireg/affected.tsv` 的 `dm/host/dm_potpick*` 行。
- 自定义键 `pot_pick` 仍保留在 `dm/host/dm_custom.c` 的 `k_keys` 位置数组里（与 7b 之后已死的 `loot_filter`／`auto_buff` 两个键同一处理）：删键要整体重编号并连带 iOS 自定义页与中英表，TotK 侧整页重建时一起消失；但 `dm_custom.h` 的键注释只列活着的键，所以那里已把 `pot_pick` 条目删掉。
- `dm\android\tools\build.py --game-run --version trim-b9`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 22:15 Asia/Shanghai — [TOTK] NA-009 裁剪批 7c（开背包自动补腰带）进行中

[BEGIN] na-009-beltauto-trim

- 命令：`git rm dm/host/dm_beltauto.c`、清掉 `diag.c`／`dm_world.c` 各一处调用、`dm_potpick.c` 两行注释、`Makefile` 的 `SRC`、白名单与 `uireg` 行、两个 `dm/host/README*.md` 行，然后 `ci_checks.py` + `build.py --game-run --version trim-b8` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉自动补腰带后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`e1c004734c47f5b271e699ef7f5bc95fc9b2545a`
[END] na-009-beltauto-trim

- 退出码：`build.py --game-run --version trim-b8` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,167,695 字节（2026-10-19 21:33:50；比 trim-b7 小 32,768 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e dm_beltauto -- dm`：0 命中（用前缀查，能覆盖 `dm_beltauto_step`／`dm_beltauto_on_uimsg` 这类符号）。
- 删除：`dm/host/dm_beltauto.c`（打开背包时自动把药水补进腰带；只有 `dm_beltauto_step`／`dm_beltauto_on_uimsg` 两个导出符号，无观测门、无构造器，无隐藏耦合）。
- 调用点：`dm/host/diag.c` 的 `dm_beltauto_on_uimsg` 调用行、`dm/host/dm_world.c` 的 `dm_beltauto_step` 调用行、`dm/host/Makefile` 的 `SRC` 一项、`dm/i18n/literal_whitelist.tsv` 的 `host/dm_beltauto.c` 行、`dm/ios/tools/uireg/affected.tsv` 的 `dm/host/dm_beltauto*` 行、`dm/host/README.md` 与 `README.zh-CN.md` 的表行、`dm/host/dm_potpick.c` 两行提到 `dm_beltauto.c` 的实测记录注释（去掉已不存在的模块引用，猜想本身的记录保留）。
- 自定义键 `pot_pick` 保持不变：它仍由 `dm/host/dm_potpick.c` 在用，`dm/host/dm_custom.c` 的键表是**位置数组**（`k_keys` 与读盘/日志按下标对应），删键要整体重编号并连带 iOS 自定义页与中英表，另随 `dm_potpick` 那批一起做。
- `dm\android\tools\build.py --game-run --version trim-b8`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 21:55 Asia/Shanghai — [TOTK] NA-008 裁剪批 7b（掉落过滤 + 增益自动补）进行中

[BEGIN] na-008-loot-buff-trim

- 命令：`git rm dm/host/dm_lootfilter.c dm/host/dm_autobuff.c`、清掉 `dm_potpick.c` 五处、`dm_pouch.c` 一处、`diag.c` 一处、`dm_actions.c` 注释、`hle_fs.c` 的 `g_dm_mount_seed_hook` 机制、白名单与 `uireg` 行、`Makefile` 的 `SRC`，然后 `ci_checks.py` + `build.py --game-run --version trim-b7` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉两个 D2R 玩法模块后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`b5b6153f1dc26c883c08d1f31594b38e653f3425`
[END] na-008-loot-buff-trim

- 退出码：`build.py --game-run --version trim-b7` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,200,463 字节（2026-10-19 21:26:54；比 trim-b6 小 65,536 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e dm_lootfilter -e dm_autobuff -e g_dm_mount_seed_hook -- dm`：0 命中（用前缀查，能覆盖 `dm_lootfilter_hidden`／`dm_autobuff_srv_tick` 这类以模块名开头的符号；词边界查不到）。
- 删除：`dm/host/dm_lootfilter.c`（掉落过滤：原版启动时载入规则文件、按难度切配置、决定哪些掉落物被藏）、`dm/host/dm_autobuff.c`（增益技能自动补）。
- 隐藏调用点一并摘掉：`dm/host/dm_potpick.c` 五处（`dm_lootfilter_pump`／`dm_lootfilter_test_dump` 调用块与两行注释、`dm_autobuff_pump`／`dm_autobuff_test_drop` 调用块、`dm_lootfilter_hidden` 调用块）、`dm/host/dm_pouch.c` 的 `dm_lootfilter_hidden` 调用块、`dm/host/diag.c` 的 `dm_autobuff_srv_tick` 调用块。
- 钩子机制整条摘掉：`dm/host/hle_fs.c` 的 `g_dm_mount_seed_hook`（定义 + 四行注释 + 调用块）—— 它原本唯一的登记者就是 `dm_lootfilter.c` 的构造函数；`DM_TOUCH_DEFAULTS` 这个开关在 `hle_fs.c` 的另外两处与 `dm/ios/Sources/front_ios.m` 仍在用，不会被孤立。
- 其余：`dm/host/dm_actions.c` 注释里「增益自动补 dm_autobuff.c …」、`dm/host/Makefile` 的 `SRC` 两项、`dm/i18n/literal_whitelist.tsv` 的 `host/dm_autobuff.c` 行、`dm/ios/tools/uireg/affected.tsv` 两行。
- `dm\android\tools\build.py --game-run --version trim-b7`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 21:40 Asia/Shanghai — [TOTK] NA-007 裁剪批 7a（转向平滑 + 商人刷新货架）进行中

[BEGIN] na-007-turn-shop-trim

- 命令：`git rm dm/host/dm_turnsmooth.c dm/host/dm_shoprefresh.c dm/ios/tools/turn_trace.py`、清掉 `diag.c` 三处调用块、`dm.h` 的 OBS 枚举、`patch_nso.py` 的 OBS 表两条、`Makefile` 的 `SRC`、`touch_layout.py` 两处注释、`uireg/affected.tsv`、两个 `dm/host/README*.md`，然后 probe NSO 规则域测试 + `ci_checks.py` + `build.py --game-run --version trim-b6` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉两个 D2R 玩法模块后 `ci_checks` 10/0、完整构建仍产出 APK、观测门号仍自洽
- 日志路径：本文件对应 [END] 记录
- 回滚点：`c9d7065678e48a0f095861d822c4eaf3b4feac33`
[END] na-007-turn-shop-trim

- 退出码：`build.py --game-run --version trim-b6` exit 0；规则域测试 `totk-run-v1` exit 0（`cuts 0 obs 0`）、`touch-run-v4` exit 1（构建号不符，符合预期）
- 产物：`dm/android/build/D2R-Android-port.apk`，19,265,999 字节（2026-10-19 21:19:04；比 trim-b5 小 16,384 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e dm_turnsmooth -e dm_shoprefresh -e OBS_ERR_SMOOTH -e OBS_MODEL_YAW -- dm`：0 命中。
- 删除：`dm/host/dm_turnsmooth.c`（转向回跳平滑 / 模型朝向门限，独占观测门 19 `OBS_ERR_SMOOTH` 与 20 `OBS_MODEL_YAW`）、`dm/host/dm_shoprefresh.c`（商人交易页「刷新货架」，消费 `OBS_C2S` 但回调本体在 `diag.c`）、`dm/ios/tools/turn_trace.py`（转向平滑逐帧位移表工具）。
- 观测门两侧同步收口：`dm/host/dm.h` 的 OBS 枚举去掉 `OBS_ERR_SMOOTH = 19`、`OBS_MODEL_YAW = 20`，`OBS_MAX` 21 → 19（`dm/host/hle.c` 的 `g_obs_fn[OBS_MAX]` / `g_obs_have[OBS_MAX]` 带越界即 die 的检查，门号必须两侧同时收）；`dm/tools/patch_nso.py` 的 OBS 表去掉 19（`0x463f40`）与 20（`0x9da5b0`）两条。
- 其余调用点：`dm/host/diag.c` 四处（`dm_shoprefresh_c2s`、`dm_shoprefresh_on_uimsg`、`dm_turnsmooth_install` 三处调用块删除；「首领连战」那段注释原本错挂在删除行上，已移回它真正说明的 `dm_bossrush_c2s` 那行）、`dm/host/Makefile` 的 `SRC` 两项、`dm/ios/tools/touch_layout.py` 两处注释（注明宿主侧实现已摘除、该按钮在 TotK 分支无宿主实现）、`dm/ios/tools/uireg/affected.tsv` 一行、`dm/host/README.md` 与 `README.zh-CN.md` 各一行。
- 规则域测试（probe NSO，`dm/android/build/probe/probe.nso`）：`DM_RULESET=totk-run-v1` exit 0，`cuts 0 obs 0 patch 684`；`DM_RULESET=touch-run-v4` exit 1（`AssertionError: Run规则构建号不符`）。输出目录已清理。
- `dm\android\tools\build.py --game-run --version trim-b6`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 21:20 Asia/Shanghai — [TOTK] NA-006 裁剪批 5（过场 movie 空播）进行中

[BEGIN] na-006-movie-trim

- 命令：`git rm dm/host/hle_movie.c dm/host/tests/t_movie.c dm/host/tests/movie_cut.py`、清掉 `dm/host/tests/Makefile` 的四处、`literal_whitelist.tsv`、`dm/README*.md`、`dm/host/README*.md` 里的引用，然后 `ci_checks.py`、`build.py --game-run --version trim-b5`、`agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：拆掉 D2R 专属的过场空播剪口后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`ae4bb3c1f02732ad8b0c0d5cfcfb547cae29ccdb`
[END] na-006-movie-trim

- 退出码：`build.py --game-run --version trim-b5` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,282,383 字节（2026-10-19 21:06:42；比 trim-b4 小 32,768 字节，宿主少了过场空播实现）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e hle_movie -e movie_cut -e t_movie -e mv_webm_duration_ns -- dm`：0 命中。
- 删除：`dm/host/hle_movie.c`（308 行；宿主按 D2R main 3.3.94012 原映像偏移写死游戏侧 movie 协议并强制接管播放状态机）、`dm/host/tests/t_movie.c`、`dm/host/tests/movie_cut.py`（对原版程序映像的静态核对）。同批修正 `dm/host/tests/Makefile` 五处（`run:` 依赖表里的 `$(B)/t_movie`、run 命令行里的 `$(B)/t_movie`、`$(PY) movie_cut.py …`、`t_movie` 编译规则两行）、`dm/i18n/literal_whitelist.tsv`（`host/hle_movie.c` 行）、`dm/README.md` 与 `README.zh-CN.md`（`hle_movie.c` 行）、`dm/host/README.md` 与 `README.zh-CN.md`（「两条对着原版程序映像的核对」改成只剩 `oe_notify.py` 一条）。
- `dm\android\tools\build.py --game-run --version trim-b5`：exit 0，产物同上。
- **本机 NOT RUN**：`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）在本机跑不了，被删的 `t_movie` 与 `movie_cut.py` 因此未经本机执行验证；`ci_checks.py` 不覆盖 `dm/host/tests/`。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 21:05 Asia/Shanghai — [TOTK] NA-005 裁剪批 4（vendored libdeflate）进行中

[BEGIN] na-005-libdeflate-trim

- 命令：`git rm -r dm/third_party/libdeflate`、清掉 `dm/third_party/README*.md` 与 `docs/DEPENDENCIES*.md` 的 libdeflate 行，然后 `ci_checks.py`、`build.py --game-run --version trim-b4`、`agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：TACT/CASC 依赖清零后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`377942f6dd73a0fdf84b1d8dfe6f7199a07cd724`
[END] na-005-libdeflate-trim

- 退出码：`build.py --game-run --version trim-b4` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,315,151 字节（2026-10-19 20:58:26；与 trim-b3 同大小——libdeflate 自 NA-002 起已不参与构建）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -i -e libdeflate -- .`：改完后除 `docs/HANDOFF*.md`（控制面与历史记载）外 0 命中；`dm/third_party/` 只剩 `bcdec`、`flip`、`ryujinx` 三个 vendored 库。
- `git grep -n -e DEPENDENCIES -- .`：只命中文档里的交叉引用（`dm/third_party/README*.md`、`dm/ios/README*.md`、`dm/gfx/tex/README*.md`、`setup.sh`、`docs/UPSTREAM_README*.md`），没有脚本按目录核对依赖表，故删目录与删表行不产生悬空引用。
- 删除：`dm/third_party/libdeflate`（43 个跟踪文件，含 MIT 的 `COPYING`）。同批修正 `dm/third_party/README.md` 与 `README.zh-CN.md`（表行 + 「bcdec/README.md、libdeflate/VERSION.md 和 ryujinx/README.md 记着各自的来源与用途」那句）、`docs/DEPENDENCIES.md` 与 `docs/DEPENDENCIES.zh-CN.md`（libdeflate 行）。
- `dm\android\tools\build.py --game-run --version trim-b4`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 20:55 Asia/Shanghai — [TOTK] NA-004 裁剪批 3（Granny 段解码）进行中

[BEGIN] na-004-granny-trim

- 命令：`git rm dm/host/hle_granny.c`、清掉 `hle.h`/`hle_hostcall.c`/`hle_lifecycle.c`/`lifecycle_test.c`/`literal_whitelist.tsv`/`patch_nso.py`/两个 README 里的引用，然后 `ci_checks.py`、`build.py --game-run --version trim-b3`、`agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉 D2R 专属的 Granny 段解码后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`6984b0411d14341a19e631516a4af11aa100859a`
[END] na-004-granny-trim

- 退出码：`build.py --game-run --version trim-b3` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,315,151 字节（2026-10-19 20:52:32；比上一版小 49,152 字节，宿主少了 Granny 解码）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -i -e granny -- dm`：只剩 `dm/host/hle_guestthread.c:1,6` 与 `dm/host/hle_thread.c:408,409` 四行「宿主自建线程」的例子注释（无符号引用，与 NA-004 判据一致）。
- `git grep -n -e SVC_HOST_GRANNY -e svc_granny -e granny_prof -e granny_offer -e granny_finish -- dm`：0 命中。
- 删除：`dm/host/hle_granny.c`（`hle_*.c` 在 `dm/host/Makefile` 与 `dm/android/tools/host_link.py` 里都按通配自动纳入，故无需改构建清单）。同批修正：`dm/host/hle.h`（0x83/0x84 登记行中英各两条、枚举两项、枚举尾注）、`dm/host/hle_hostcall.c`（两个 case）、`dm/host/hle_lifecycle.c`（`granny_prof_dump` 声明与调用）、`dm/android/tests/lifecycle_test.c`（桩与标记序号下移一位、期望串 `"012"`/`"0123"`）、`dm/i18n/literal_whitelist.tsv`、`dm/tools/patch_nso.py`（0x83/0x84 剪口条目与注释）、`dm/README.md` 与 `README.zh-CN.md`（该行还留着 NA-002 已删的 `hle_tact.c`，一并清掉）。
- `dm\android\tools\build.py --game-run --version trim-b3`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 20:05 Asia/Shanghai — [TOTK] NA-003 裁剪批 2（bootlist 工具与验证面）进行中

[BEGIN] na-003-bootlist-trim

- 命令：`git rm dm/tools/tact_bootlist.py dm/verify/bootchk.sh dm/verify/bootlist_static.py`、清掉 `patch_nso.py`/`accept.sh`/`test_accept.py`/README/`ios/run.sh`/`shell_build.sh`/`d2rm_pack.py` 里的引用，然后 `ci_checks.py`、`build.py --game-run --version trim-b2`、`agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：bootlist 工具与验收项摘除后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`76aad756add78ea4b882e096816e0371616b64be`
[END] na-003-bootlist-trim

- 退出码：`build.py --game-run --version trim-b2` exit 0；`bash -n` 三个被改的 shell 脚本 exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,364,303 字节（2026-10-19 20:05:54）
- 结果：SUCCESS
- 备注：`ci_checks.py`、`agent_handoff_check.py --verify` 与 `dm/verify/test_accept.py` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- `git grep -n -e tact_bootlist -e bootchk -e bootlist_static.py -- .`：仅剩 `docs/HANDOFF*.md`（控制面/历史）与 `docs/TOTK_PORT_SCAFFOLD.zh-CN.md`（历史记载）；`dm/`、`tools/`、`.github/`、`setup.sh` 下 0 命中。
- `git grep -n -e bootlist -- dm tools .github setup.sh`：0 命中（连 `bootlist.tsv` 的搬运点也一并清掉）。
- `bash -n dm/verify/accept.sh dm/ios/run.sh dm/ios/tools/shell_build.sh`（Git bash）：三个全 OK，exit 0。
- `dm\android\tools\build.py --game-run --version trim-b2`：exit 0，产物同上。
- `dm\verify\test_accept.py`：NOT RUN（本机 Python `subprocess(['bash',…])` 解析到坏掉的 WSL 启动器 `C:\Windows\System32\bash.exe`，报 `WSL2 ERROR_PATH_NOT_FOUND`；该失败发生在 bash 启动阶段、与 accept.sh 内容无关，属本机环境限制）。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。
- 备注：`accept.sh` 的 `item 2` 仍保留 `PREFETCH 预取命中` 只读读数与其单测（`test_prefetch_hit_is_report_only`）。该读数宿主侧已不可能产生真值（预取代码在 NA-002 删除），属同一 D2R 验收面的遗留，留待后续批次处理，本轮未动。


## 2026-10-19 19:05 Asia/Shanghai — [TOTK] NA-002 裁剪批 1（宿主侧 TACT/CASC）进行中

[BEGIN] na-002-tact-trim

- 命令：`git rm dm/host/hle_tact.c`、新增 `dm/host/hle_hostcall.c`、修正构建/测试/登记表引用，然后 `ci_checks.py`、`build.py --game-run --version trim-b1`、`agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：拆掉宿主 TACT 解码后 `ci_checks` 8/0，完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`8965544565b687de9a6d78436d108cae817a1386`
[END] na-002-tact-trim

- 退出码：`build.py --game-run --version trim-b1` exit 0（本次长操作的主体）
- 产物：`dm/android/build/D2R-Android-port.apk`，19,364,303 字节（18.47 MiB），2026-10-19 19:40:00
- 结果：SUCCESS
- 备注：宿主侧 TACT 解码拆除后完整构建仍绿；`ci_checks.py` 与 `agent_handoff_check.py --verify` 的退出码见本条目下方的证据行
证据（本条目对应的命令与退出码）：

- `git grep -n -e hle_tact -e PROF_TACT -e libdeflate -e SVC_HOST_TACT -e tact_prefetch -e tact_chk_init`：源码／头文件／构建脚本／测试／白名单中已无活引用；`libdeflate` 仅剩 vendored 库自身；`dm/ios/tools/uireg/affected.tsv` 仍留 1 行 `dm/host/hle_tact*`（划归批 3）。
- `dm\android\tools\ci_checks.py`：exit 0，10 项通过 / 0 项失败（首跑 exit 1，两项红及其原因见 HANDOFF 快照「最近一次失败命令」）。
- `dm\android\tools\build.py --game-run --version trim-b1`：exit 0，产物 `dm/android/build/D2R-Android-port.apk`，19,364,303 字节。
- `tools\agent_handoff_check.py --verify`：exit 0。
- 提交：代码 `b54f782e10a5ae2ea4146ffaf59407f6740b1d13`（15 个文件，+61 / -337）；`git push` exit 0（`8965544..b54f782`）；`git rev-parse HEAD` 与 `git rev-parse origin/totk/scaffold` 相同。
- 范围外说明：宿主调用分派器（0x85–0x8e）原本寄生在被删文件里，已拆到新文件 `dm/host/hle_hostcall.c`（`dm/host/Makefile` 的 `hle_*.c` 通配与 `dm/android/tools/host_link.py` 的 `*.c` glob 都会自动纳入）；0x80 的 TACT 剪口登记与 `SVC_HOST_TACT_ZLIB` 一并摘除，0x85 门保留；`libdeflate` 的构建接线已断但 vendored 源码与文档保留（批 4）。

## 2026-10-19 18:43 Asia/Shanghai — [TOTK] 执行 NA-001：提交两处 TotK 适配代码

- 会话目标：按 HANDOFF 的下一步唯一动作 NA-001，审查并单独提交两处 TotK 适配代码。
- 恢复序列：读 `AGENTS.md`、`docs/HANDOFF.zh-CN.md`；`tools/agent_handoff_check.py --resume` exit 0；`--verify` exit 0（当时 HEAD `c405782`、DIRTY）；日志长操作记录 `[BEGIN]` 与 `[END]` 各 1 条，无未闭合。
- 审查证据：`git diff --check` exit 0；`py_compile` 两文件 exit 0；`program()` 改为返回二元组后无外部调用者（仅 `extract_packages.py` 内两处调用，`make_package.py` 走子进程 CLI）；`patch_nso.py` 的 `cuts.append`/`obs.append` 全部位于 `RULE_RUN` 或 `PRIVATE_AIM` 分支内，表按构建号取值。
- 独立复跑规则域测试（probe NSO，输出到 `%TEMP%`）：`DM_RULESET=totk-run-v1` exit 0 且 `cuts 0 obs 0`（`main.cuts.tsv`/`main.obs.tsv` 只有表头行）；`DM_RULESET=touch-run-v4` exit 1（构建号不符，符合预期）；未知规则域 exit 1 并列出可选值。
- 提交与推送：`git commit` exit 0；`git push` exit 0（`c405782..1d915ab`）；提交只含 `dm/android/tools/extract_packages.py` 与 `dm/tools/patch_nso.py`；`git status --short` 为空；`git rev-parse HEAD` 与 `git rev-parse origin/totk/scaffold` 同为 `1d915aba0df285bb8e0cb2d7175e184659b0cd52`。
- 裁剪盘账（为 NA-002 探路，只读）：`ci_checks.py` 不引用 tact/casc/bootlist；`hle_tact` 的活引用分布在 `dm/host/hle.h`、`dm/host/dm.h`（`PROF_TACT`）、`dm/host/diag.c`、`dm/host/hle_svc.c`、`dm/host/hle_fs.c`、`dm/host/Makefile`、`dm/android/tools/host_link.py`、`dm/tools/patch_nso.py`（0x80 剪口登记）、`dm/host/tests/mode_scan.py`、`dm/i18n/literal_whitelist.tsv`；libdeflate 仅被 `hle_tact.c` 使用。据此把裁剪拆为批 1（宿主侧，NA-002）/ 批 2（工具、验证脚本、文档）/ 批 3（36 个 `dm_*.c` 与派生表）。
- 下一步：NA-002，裁剪批 1（宿主侧 TACT/CASC 拆除）。
- 交接控制面提交：本轮以独立提交推送；以 `origin/totk/scaffold` 为准。
## 2026-10-19 17:47 Asia/Shanghai — [DOCS] 交接协议 v1 落地

- 会话目标：建立上下文压缩后可恢复的 Agent 交接控制面。
- 完成：重构 HANDOFF 为当前快照；新增自动校验脚本；新增独立日志；更新 AGENTS 入口。
- 未完成：两处 TotK 适配代码提交；TotK 文件与 M0 实测。
- 验证：`ci_checks.py` exit 0（8/0）；`build.py --game-run --version handoff-check` exit 0；规则域负向测试符合预期。
- 阻塞：缺少 TotK 文件、`prod.keys`、`hactool` 和真机。
- 下一步：NA-001，提交两处 TotK 适配代码。
- 交接提交：已提交并推送；以 `origin/totk/scaffold` 为准。

## 2026-10-19 17:10 Asia/Shanghai — [VERIFY] 交接构建验证

[BEGIN] handoff-build-check

- 命令：`build.py --game-run --version handoff-check`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：生成 APK
- 日志路径：`D:\Switch\handoff-build-check.log`
- 回滚点：`a919fdb`

[END] handoff-build-check

- 退出码：0
- 产物：`dm/android/build/D2R-Android-port.apk`
- 结果：SUCCESS
- 备注：APK 为通用壳包，不含游戏模块。

## 2026-10-19 17:34 Asia/Shanghai — [DOCS] 初版交接规则

- 会话目标：把压缩恢复规则写入 HANDOFF。
- 完成：初版规则、实时快照、会话日志。
- 未完成：结构化下一步契约、独立日志、自动校验。
- 验证：文档结构人工检查。
- 阻塞：无。
- 下一步：重新设计并落地 v1 协议。