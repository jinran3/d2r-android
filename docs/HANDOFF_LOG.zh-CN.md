# Agent 交接会话日志

> 只追加，不覆盖。最新记录放在最上方。
> 当前状态以 [HANDOFF](HANDOFF.zh-CN.md) 为准。

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