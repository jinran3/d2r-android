# TotK 移植脚手架计划（基于 d2r-android / d2r-mobile）

日期：2026-10-18。依据：`dm/` 源码（fork 自 sydeEvans/d2r-android，基线 HEAD `5d8e322`）、上游 jhaizhou-ops/d2r-mobile（HEAD `9393b00`）的文档、源码与 Issues。

目标：把《塞尔达传说：王国之泪》(TotK) 的**原版 ARM64 程序**直接跑在 Android（一加 12 / Snapdragon 8 Gen 3 / Adreno 750）上，架构沿用 d2r-android 的「NSO 改写 + 宿主 HLE + NVN→Vulkan + 离线着色器翻译」，而不是写一个模拟器。

---

## 0. 一句话结论

d2r-android 里**约六成是可以直接搬运的通用基础设施**（Android 宿主、装载器、内核 HLE、NVN→Vulkan 回放、打包导入、触控、驱动分发、验证方法论）；**约四成是与暗黑2本体绑定的**（改写规则的 CUTS/OBS 表、D2R 专属 HLE、着色器事实表、派生表、bootlist、游戏逻辑 hook），TotK 必须重做或删除。

**最大的单点风险不是图形，而是着色器事实表**：`dm/gfx/nvn/shader_facts.tsv` 这张表由 `dmsh_facts.py --freeze` 从**PC 版游戏的 DXBC 反射**生成（源码注释写得很明确：「取自与它一一配对的 PC 版着色器的反射」）。暗黑2有 PC 版，TotK **没有 PC 版**，这条生成路径直接不可用，必须在 M3 之前找出替代方案。详见 §4.4。

---

## 1. 两个仓库的分层解剖与复用矩阵

### 1.1 架构分层（从下到上）

| # | 层次 | d2r-android 中的位置 | 游戏无关性 | TotK 处置 |
|---|---|---|---|---|
| L1 | NSO 改写器 | `dm/tools/patch_nso.py` | **机制通用，表不通用** | 复用机制；新增 `DM_RULESET=totk-run-v1`；CUTS/OBS 表按 TotK 构建号重建（首版可为空表） |
| L2 | ELF 封装 | `dm/android/tools/guest_elf.py`、`tools/guest_dylib.py` | 通用 | 直接复用 |
| L3 | 装载与重定位 | `dm/android/native/game_modules.c`、`runtime.c`、`host_sections.c` | 通用（MOD0 解析、动态符号、116034 项重定位这类通用逻辑） | 直接复用；模块数量由 TotK 实际文件决定 |
| L4 | 上下文入口/寄存器门 | `host/entry.S`、`android/tools/generate_entry.py`、`android/native/runtime_context_cache.h` | 通用 | 直接复用（x18/tpidr/SIMD 全寄存器保存这套是移植正确性的地基） |
| L5 | 内核 syscall HLE | `host/hle_svc.c`（内存）、`host/hle_thread.c`（线程/同步/事件） | **基本通用**（Horizon 内核 ABI 是公开稳定的） | 复用；按 TotK 实际触发的 syscall 号补缺口 |
| L6 | C 库直通 | `host/hle_table.c` | 通用 | 复用 |
| L7 | 系统服务 HLE | `host/hle_fs.c`、`hle_hid.c`、`hle_audio.c`、`hle_swkbd.c`、`hle_oe.c`、`hle_account.c` 等 27 个 `hle_*.c` | **接口通用，实现半通用** | 逐个评估：fs/hid/audio/swkbd/时间/生命周期可复用；D2R 专属的必须替换 |
| L8 | NVN 接口层 | `dm/gfx/nvn/hle_nvn.c`、`nvn_thunks.S`、`nvn_obj.h` | **机制通用，函数集合不通用** | 复用框架；`names.txt`/`nvn_slots.tsv` 按 TotK 重生成 |
| L9 | NVN→Vulkan 回放 | `dm/android/native/nvn_vulkan.c` + 25 个 `.inc` | 大体通用 | 复用；按 TotK 实际调用补齐命令与状态 |
| L10 | 着色器翻译链 | `dm/gfx/tools/`（Ryujinx→SPIR-V）、`dm/android/tools/build_shaders.py` | 工具通用，**事实表不通用且生成路径断了** | 工具复用；`shader_facts.tsv` 必须换来源（§4.4） |
| L11 | 打包/导入/壳模式 | `dm/android/tools/make_package.py`、`PackageArchive`、`LauncherActivity` | 通用 | 复用；改 manifest 内容与校验项 |
| L12 | 输入/触控/手柄 | `TouchControls.java`、`hle_touch.c`、`hle_hid.c` | 通用 | 复用框架；按键布局与 HUD 位置按 TotK 重排 |
| L13 | 音频/生命周期 | `hle_audio.c`（AAudio）、`hle_lifecycle.c` | 通用 | 直接复用（切后台先存档再挂起、客体时钟冻结这套已经验证） |
| L14 | GPU 驱动分发 | `native/gpu_driver.c`、`prebuilt/turnip/` | 通用 | 复用；**驱动需为 Adreno 750 选型**（现有 T30 构建面向 830，未验证 750） |
| L15 | 游戏逻辑增强 | `host/dm_*.c`（共 36 个文件：秘境/仓库/HUD/掉落/符文之语…） | **全部 D2R 专属** | **TotK 全部不要** |
| L16 | 验证体系 | `dm/verify/*`、`dm/android/tests/*`、`ci_checks.py` | 方法论通用，判据不通用 | 复用脚手架；判据（画面闸门/逻辑闸门/真值）按 TotK 重建 |

### 1.2 两个仓库的分工（读代码时别走错）

- **`d2r-mobile`（上游）**：iOS/macOS 原版。宿主是 Darwin（`mach/`、`pthread/qos.h`、APFS `clonefile`、CoreAudio），图形是 Metal（`nvn_mtl.m`）。**它的价值是「怎么让原版程序在另一个系统上跑起来」的完整方法论 + `verify/` 的验证体系 + `docs/` 里踩过的坑。**
- **`d2r-android`（fork）**：把上面那套搬到 Android。关键桥接是 `dm/android/native/compat/host_preinclude.h`——**用宏把 Darwin 名字映射到自己实现的 POSIX 适配**（`clock_gettime_nsec_np`、`st_mtimespec`、`renamex_np`、xattr…），所以 `dm/host/*.c` 能几乎原样在 NDK 下编译（`dm/android/tools/host_compile.py --compat` 就是干这个的）。图形另写 Vulkan 回放。
- **结论**：TotK 应该 fork **d2r-android** 起步（Android 宿主已经跑通 60FPS），把 d2r-mobile 当**参考文档与方法论来源**，不作为代码基础。

---

## 2. 必须替换 / 删除的 D2R 专属资产（清单）

改写器里按暗黑2构建号 `db0507f36b84200ac05f75d76ed5026f`（版本 3.3.94012 / v2228224）绑定的东西，TotK 一律不适用：

| 资产 | 位置 | 说明 |
|---|---|---|
| `CUTS` 剪口表 | `dm/tools/patch_nso.py` L55+ | 暗黑2专属二进制定点修改（断网社区补丁、掉落光柱、技能瞄准、阴影边长 2100、通知面板、技能说明框…）。TotK 首版**空表起步**，只为「跑起来」的必要剪口逐条添加 |
| `OBS` 观测门表 | 同上 L156+ | 观测点是 D2R 内存地址，TotK 需按自己的地址重定 |
| `RULE_BUILD` 断言 | 同上 L181 | 必须改成 TotK 的 NSO 构建号 |
| 触屏/选怪/瞄准 HLE | `hle_target.c`、`hle_private_aim.c`、`hle_charname.c`、`dm_cursor*.c` 等 | 全是暗黑2的游戏内存结构，删除 |
| 游戏逻辑模块 | `host/dm_*.c` 共 36 个 | 秘境/仓库/符文之语/极乐世界…与 TotK 无关，删除 |
| TACT/CASC 数据访问 | `hle_tact.c`、`tools/tact_bootlist.py`、`tools/casc_overlay.py`、`data/bootlist_*.tsv` | 暴雪存储格式。**TotK 用标准 RomFS + SARC/Yaz0，这一整套不需要**（省掉不少工作量） |
| Granny 动画解码 | `hle_granny.c` | 暴雪格式，不需要 |
| 过场 movie 剪口 | `hle_movie.c` | 地址绑定 D2R，TotK 需另定策略（首版可直接「不支持」） |
| 派生表 | `host/dm_vault_tab.h`、`dm_hud_exp.h`、`dm_bright_levels.inc` 及 `derived.tsv` | 暗黑2的仓库/经验/关卡亮度表，删除 |
| 着色器事实表 | `gfx/nvn/shader_facts.tsv` | **生成路径断了**，见 §4.4 |
| NVN 函数表 | `gfx/nvn/names.txt`、`nvn_slots.tsv`、`pso_manifest.tsv`、`bf_want.tsv`、`c1_full.tsv` | 由 D2R 主程序静态分析得出，TotK 需重跑分析 |
| 中英文案表 | `i18n/ui_text.tsv`、`host/dm_i18n_tab.h` | 暗黑2 UI 文案，TotK 用游戏自己的文字，删除/重建 |
| 构建号/版本校验 | `tools/product.sh`、`PRODUCT`、`LEGACY_DEVICES` 等 | 换 TotK 版本 |

---

## 3. TotK 与 D2R 的结构性差异（决定工作量的几个数）

以下几项**需要在拿到自己的 TotK 文件后立刻实测填表**，不能凭印象：

| 维度 | D2R（已知，来自 `docs/ANDROID_PORT_PROGRESS.zh-CN.md`） | TotK（待测） | 影响 |
|---|---|---|---|
| NSO 模块数 | 3（main 55.1MB、sdk 15.5MB、subsdk0 8.5MB） | **3 + rtld**（v1.4.2：main text 45.77MB、sdk 6.69MB、subsdk0 3.50MB、rtld 9.5KB） | L3 装载器、包布局 `game/` 项数 |
| 动态符号 / 重定位 | 38,837 符号 / 116,034 重定位 / 264 强制接管 | **33,858 符号 / 36,747 重定位 / 1,356 导入**（main 706·680·2,070；sdk 23,039·9·19,027；subsdk0 10,110·664·15,648；rtld 3·3·2） | L7 HLE 覆盖工作量；`hle_inventory.py` 直接可用 |
| NVN 取址函数数 | 523 个，其中 216 有实际调用点、203 实现 / 13 空实现 | **534 个**（加载函数 main 0xbbfa90–0xbc3510；槽走间接指针表，与 D2R 的直接 `str` 不同；「有调用点」一栏待按 TotK 的读法重算） | L8/L9 覆盖工作量 |
| 着色器键数 | 20,795 | **9,807**（唯一键；文件里 49,089 条记录；cs 18 / ps 5,557 / vs 4,232）—— 只覆盖 `/Shader` 归档，UI 布局与引擎库归档待补 | 翻译时长、包体积、预热清单 |
| RomFS 大小 | 8.4 GB | **15.87 GB / 304,207 个文件**（本体 NCA 17.1 GB 的 IVFC 数据层；更新包是 BKTR 补丁，应用后还要加一层） | 见 §5「4GB zip 限制」 |
| 存储格式 | 暴雪 CASC/TACT（`hle_tact` 自管块解码） | 标准 RomFS（游戏自读） | 反而**更简单**，`hle_fs.c` 的 `rom:/` 直读即可 |
| 真机基线 | Adreno 830（OPD2409）60 FPS | Adreno 750（一加 12）未测 | Turnip 驱动选型 |


**已填的格子来自 2026-10-20 的实测**（TotK v1.4.2，Title ID `0100F2C0115B6000`）：构建号 = main `5cb42b1cf25469fb0635fd046453d843`、sdk `5cf080e800530a7f25bd528ec875c27b`、subsdk0 `3308c1d216f788397d1451c8345a16cd`、rtld `82a3cf78789f9d9858c52379d8d2d129`（本体 v1.0.0 的 main = `082ce09b06e33a123cb1e2770f5f9147`）。测量用的是本仓库新写的 `dm/tools/switch_nca.py`（纯 Python 解 NCA3 / ExeFS / RomFS；hactool 1.4.0 解不开更新包的 NCA3 BKTR 补丁段）与 `dm/tools/nso_stats.py`（NSO 段与 MOD0 动态表统计）。游戏文件与密钥都只在本机，仓库里不放。

---

## 4. 关键技术决策点

### 4.1 分支策略

在自己的 fork `jinran3/d2r-android` 上开新分支，**不要**在 main 上直接改：

```
main (保留 D2R 可构建)
  └── totk/scaffold        # 本计划的全部工作
```

先做一次「可回滚的裁剪提交」：删掉 §2 里明确无用的 `dm_*.c`、D2R 派生表、i18n 表，让 `ci_checks.py` 仍然绿。**这一步不碰任何机制代码**，是后面所有工作的安全网。

### 4.2 新增 `DM_RULESET=totk-run-v1`

`patch_nso.py` 现在用 `DM_RULESET ∈ {native, touch-run-v4}` 控制规则域（L175-181）。扩展为三值，并让 `RULE_RUN` 分支按模块名与构建号分别取表。原则：

- **CUTS 只放「跑不起来就必须改」的**。D2R 的 CUTS 里绝大多数是玩法/触屏增强，TotK 不需要。
- 每条 CUTS 必须带：原字节断言、新字节、理由、作用域（`全` / `仅宿主`）。这一结构照抄现有代码，它是防止「换游戏版本后静默打错补丁」的关键。
- 空表是合法状态——`cuts = list(CUTS.get(BUILD_ID, []))` 本来就是按构建号查，查不到就是空。

### 4.3 NVN 函数集合的重生成

现有 `dm/gfx/nvn/names.txt`（523 行）与 `nvn_slots.tsv`（525 行，含 `slot`/`nuses`/`first_use`）是**从 D2R 主程序静态分析出来的证据表**。TotK 需要：

1. 跑现有的 `dm/gfx/tools/` 下的槽位分析脚本，对 TotK 的 `main` 重新生成这两张表（流程可参考 `nvn_slots.tsv` 头部注释「main NVN 取址槽与静态调用点（nvn_slots.py）」）。
2. 按「有实际调用点」的子集决定 `hle_nvn.c` 里哪些要真正实现、哪些进 `g_nops`、哪些进红桩——**这套分类机制本身是通用的**，D2R 是 203 实现 / 13 空 / 307 红桩。
3. 红桩被调用时会打 `【红】NVN 未实现被调用：名字` 日志——这是 TotK 早期最核心的「还差什么」清单来源。

### 4.4 ★ 着色器事实表：必须先解决的断点

**现状**（`dm/gfx/tools/dmsh_facts.py` 文件头原文）：

> 这些事实取自与它一一配对的 **PC 版着色器的反射**（NVN 槽号 = D3D 寄存器号）……表随仓库，出着色器库只读这张表，**不需要 PC 版游戏文件**。

也就是说：**d2r 项目在某个有 PC 版游戏的环境里，一次性把 2 万多条事实冻结进了仓库**。TotK 没有 PC 版，`--freeze` 无法运行。

需要记录的事实类型（来自该文件头）：
- 贴图 / 图像的**维度类型**（2d / 3d / cube / buffer）
- 图像**格式**
- 顶点属性与片元输出的**分量类型**
- 计算着色器的**线程组大小**与**共享内存字节数**

**可选出路（按推荐顺序，需在 M3 前实测选定）：**

| 方案 | 做法 | 风险 |
|---|---|---|
| A. 用默认值 + 覆盖统计 | 现有代码已支持：`表里没有的键，翻译查询按缺省作答（出包汇总里单列）`。先全量走默认，读汇总里那批「按缺省作答」的键，优先补齐会被游戏真正用到的 | 计算着色器的线程组大小若默认错，会直接导致画面错/崩溃，不能靠默认 |
| B. 从运行期 NVN Builder 调用反推 | 游戏自己会调 `nvnTextureBuilderSetDims` / `SetFormat`、`nvnCommandBufferDispatchCompute` 等；在 L8 的 `hle_nvn.c` 里**记录运行期观测值**，反填事实表 | 需要游戏先能跑到调用这些函数的地方，且覆盖度取决于跑到多少场景 |
| C. 借用开源模拟器的 shader 处理 | Ryujinx / Eden / Sudachi 对 TotK 的 Maxwell 着色器已有处理路径（它们同样要解决维度/线程组问题） | **GPL-3.0，不能把代码并入 MIT 项目**（两份 README 已明确这个红线）。只能作为「参考其推导思路/黑盒取值」，不能拷代码 |
| D. 从 TotK 自带的着色器缓存/元数据读 | 某些 Switch 游戏的着色器包自带反射信息 | 未验证，需先 dump 出来确认格式 |

**结论**：M3 之前必须用 A+B 组合拿到「能出 3D 画面」的事实表，并把 D 当备选调研。**这是本计划里唯一可能推翻「原生移植」路线、被迫退回模拟器路线的风险点**，要在 M2 结束时就给出结论，不要拖到 M3。

**2026-10-20 的实测结论（风险基本解除）**：

- 任天堂的 zstd 字典**在游戏自己里**：`/Pack/ZsDic.pack.zs` 是 SARC，装 3 份 128 KB 字典（id 1/2/3），着色器包的 zstd 帧头写明自己要哪一份（着色器用 id=1）。没有它，任何 `*.bfsha.zs` / `*.sarc.zs` 都是 `Dictionary mismatch`。
- 用这份字典，TotK 的着色器归档**能解开**：`ApplicationPackage.Nin_NX_NVN.release.sarc.zs` → SARC（19 个条目，含 `*.sharcb`），各 `*.bfsha.zs` → FSHA 容器；条目里带 `cTexSrc`、`gl_InstanceID` 这类**反射元数据**。所以 D2R 那条「从 PC 版反射冻结事实表」的路确实不存在，但**从游戏自带归档取**（方案 D）成立 —— 事实表的下一步是把 FSHA / BNSH 的结构解析出来。
- 进一步实测（2026-10-20）：归档结构摸清了 —— 每个着色器 = **控制头**（NVN 着色器控制头，魔数 0x98761234，major 1、minor 9 或 16，长 0x880）+ 机器码 + C1 块；**着色器键 = `sha256(control + program + c1)` 的前 16 个十六进制字符**（与既有事实表的键格式一致 ✓）；阶段由控制头里的 kind 决定（0 vs / 1 ps / 2 gs / 3 hs / 4 ds / 5 cs）；**计算着色器的线程组大小与共享内存字节数就在控制头 0x748 处**（local x/y/z + shared）—— 这一类事实**不需要 PC 反射**，TotK 侧直接可得（实测 cs 有 64x1x1、8x8x1、1x1x1 等，共享内存 0 / 2048 字节）。贴图维度 / 图像格式 / 属性分量类型所在的位置**还没定位**（C1 块很小，多半在控制头里的描述符表），这一部分仍按方案 A（缺省 + 统计补齐）与方案 B（运行期观测反填）走。
- 外部可参考的实现：`OJZen/totk-mobile`（Mac/iOS，已能读档游玩，v1.4.3）。**许可提醒**：它是 Apache-2.0，本仓库是 MIT，只读思路与格式事实、代码自己写；它内嵌的 Ryujinx 部分是 MIT，可按其声明使用。移植雷达（`catoncat/d2r-port-radar`）有机器可读的接口，值得定期看。

### 4.5 上游同步：哪些机制能直接搬

本 fork 与上游 `jhaizhou-ops/d2r-mobile`（iOS/macOS 原版）的共同祖先是 `sydeEvans/d2r-android`。上游的 `main` 一直在走，两边 `dm/tools/patch_nso.py` 的差异分三类：

1. **D2R 玩法剪口**（本 fork 在裁剪批次 7a–7s 已删）—— 预期差异，不必同步。
2. **Android 宿主改造**（本 fork 独有：`DM_TARGET=android`、`thread_base()` 走宿主上下文入口、键页布局）—— 上游没有，不要覆盖。
3. **可直接用的上游改进** —— 这一类要主动去看并采纳。可用的例子：上游 issue #55 的「寄存器字段预筛」（线性扫描时先看四个寄存器字段有没有 18，命中才反汇编；上游口径扫描快 3.6–3.9 倍，语义不变）。

规则（已写进 `AGENTS.md` 第 11 条）：上游有新提交 / issue 要定期看，只取对本项目有用的部分，并把「这条上游改动有没有用、为什么」的结论写进 `docs/HANDOFF_LOG.zh-CN.md`。

**x18 前提（2026-10-20 实测修正）**：D2R 改写器的前提是「客体的 x18 = TLS 指针，宿主把它换到线程槽 K18」。实测 TotK v1.4.2 的 main 把 x18 当**普通寄存器**用（.text 里 24,204 条指令提到 x18、18,572 条提到 w18），所以这套语义前提对 TotK 不成立。结论：上游那套机制的本质是**每线程保存客体 x18**，对普通寄存器一样成立；且 Android 宿主本来就保全 x18（`dm/android/native/probe.c` 每次宿主调用前后都比对，Linux AArch64 ABI 也不用 x18）——因此 **TotK 规则域不做 x18 改写、宿主侧不用改**，`svc` / `tpidr` / `cntpct` 照旧改写。

### 4.5 驱动选型（一加 12）

- 现仓库内置 Turnip：`dm/android/prebuilt/turnip/vulkan.purple.so`，版本 `26.3.0-T30-1.4.359`，作者 @Mr_Purple_666，**T30 构建**，实测机是 Adreno 830。
- 一加 12 是 **Adreno 750**。仓库 README 明确：「不同 GPU 应使用兼容的驱动和相匹配的着色器分组配置；不能直接套用另一台设备的测量结果」。
- 必做：① 启动界面保留「Turnip / 手机自带驱动」切换（已有该功能）；② 查 Adreno 750 对应的 Turnip 构建（`vulkan.purple.so` 有针对不同 Adreno 的版本）；③ `host-subgroup-size.txt` 必须按 750 实测核对——README 说着色器按 **64 子组尺寸**构建，这个值不匹配会直接出错。

---

## 5. 分阶段里程碑

每个里程碑都有**明确的验收门**（不满足就停下，不进入下一阶段），并对应一个「中断后从这里继续」的进度文档。这是照抄 d2r-android `docs/ANDROID_PORT_PROGRESS.zh-CN.md` 的做法——它开头就写「此文件随工作更新，是中断后继续移植的入口」。

### M0 — 勘察与基线（不改机制代码）

**目标**：把「不知道的数」全部变成「知道的数」。

- [ ] 准备自己的 TotK 文件（本体 + 更新）与 `prod.keys`，用现有 `dm/android/tools/extract_packages.py` 解包
- [ ] 用 `dm/tools/nso.py` 读出每个模块的段布局、**构建号**（NSO 头 `0x40–0x50`）
- [ ] 填完 §3 的表格：模块数/大小、符号数、重定位数、NVN 取址函数数、着色器键数、RomFS 大小
- [ ] 跑 `dm/tools/hle_inventory.py` 的思路，统计 TotK 主程序对宿主的导入需求（现有工具可直接用，它抽的是 `HLE_FORCE`/`HLE` 登记）
- [ ] 调研 §4.4 的方案 D，给出「事实表从哪来」的结论
- [ ] 一加 12 上先装**现有 D2R 通用 APK**（Release 里的壳包），确认宿主/驱动/触控在这台机器上能起来——**先证明地基，再动游戏**

**验收门**：§3 表格填满；§4.4 有结论；一加 12 能跑现有 APK 的启动界面（不一定要能进 D2R 游戏）。

### M1 — 模块装载到 `nnMain`（图形之前）

**目标**：TotK 的 NSO 被改写、封装成 ELF、装载、重定位、强制接管全部命中，SDK 初始化序列走完，进入 `nnMain`。

- [ ] 新增 `DM_RULESET=totk-run-v1`，`RULE_BUILD` 换 TotK 构建号，CUTS 空表
- [ ] 逐模块跑 `patch_nso.py` → `guest_elf.py`
- [ ] `game_modules.c` 装载并报告：符号数、重定位数、**未满足的导入清单**
- [ ] 按未满足清单补 `HLE`/`HLE_FORCE`（内核 syscall 优先于服务）
- [ ] 参考进度文档的启动序列判据：`_init_libc0 → nnosInitialize → _init_libc1 → nninitInitializeSdkModule → nninitStartup → _init_libc2 → 构造 → nnMain`

**验收门**：日志走到 `nnMain`（或明确的「缺哪个导入」清单，而不是崩溃在随机地址）。
**这一步最大的坑**（来自进度文档「已排除的问题」）：**不要把首轮正常返回当成功**——「加入 `hle_nv.c`、`hle_vi.c` 后，完整资源下明确到达 NVN 图形入口。不要把首轮正常返回当作游戏运行成功。」还有 ELF 链接器要合法节表、`--gc-sections` 下 HLE 登记会被删（需 `retain`）、跳表/间接跳转解析的跨片问题（LASRecomp 那一轮踩了四次）。

### M2 — NVN 接管与首帧清屏

**目标**：`nvnBootstrapLoader` 被宿主接管，Vulkan 设备建起来，清屏首帧上屏。

- [ ] 重生成 TotK 的 `names.txt` / `nvn_slots.tsv`（§4.3）
- [ ] `nvn_thunks.S` 按新集合重出（`dm/android/tools/generate_nvn.py`）
- [ ] 逐个补 NVN 实现，红桩日志驱动迭代
- [ ] 交换链/表面接上（参考 `nvn_vulkan.c`、`vulkan_front.c`）

**验收门**：真机上稳定清屏出帧、日志无红桩被调用、`front_game_res` 分辨率正确。
**同时必须给出 §4.4 的最终方案**（因为 M3 立刻要用）。

### M3 — 着色器翻译与 3D 首帧

**目标**：Maxwell 着色器翻译成 SPIR-V，画出第一帧真正有内容的 3D 画面。

- [ ] 按 §4.4 方案生成 TotK 的 `shader_facts.tsv`
- [ ] 跑 `dm/android/tools/build_shaders.py`（需要 .NET 10；参考 Issue #19：`DOTNET_ROOT` 没设时会报「翻译器不是用仓内源编的」这种**误导性错误**）
- [ ] 按打包方式选择 `--host-subgroup-size`（Adreno 750 实测值）
- [ ] 处理 §4.5 驱动选型

**验收门**：真实场景 3D 画面正确（不是清屏、不是菜单）；着色器构建汇总里「按缺省作答」的键为 0 或已知可控。
**这一步的坑**（Issue #5，非常值得提前防范）：`setup.sh` 曾经在**全部着色器失败**时仍打印「工作区就绪」并 exit 0——因为 `| tail` 吃掉了退出码、且 `_b_build.json` 这个写着失败明细的文件**从来没被读过**。TotK 的脚手架必须：
  1. `set -o pipefail`
  2. 「完成」的判据是**读 `_b_build.json` 且无失败项 + 产物数等于键数**，不是「文件存在且至少有一个」
  3. 翻译脚本有任何失败就非零退出

### M4 — 输入、音频、存档、生命周期 → 可玩

**目标**：能用触屏/手柄玩、有声音、能存读档、切后台再回来状态正确。

- [ ] 手柄映射按 TotK 重排（现有 `hle_hid.c` 已支持 AXIS_HAT_X/Y 方向键与 ZL/ZR 模拟轴，这套通用）
- [ ] 触控布局按 TotK 的 HUD 重排（现有 `TouchControls.java` 的六窗口 + pointer ID 归属机制通用，坐标要重算）
- [ ] 音频：`hle_audio.c` 的 AAudio 路径（上游 Issue #77 刚修了「中断其他 App 语音」的混音问题，记得同步）
- [ ] 存档：`hle_fs.c` 的事务式存档（Commit/回滚/写失败拒绝）**是通用设计**，换 TotK 的存档目录即可
- [ ] 生命周期：先请存盘 → 冻结客体时钟 → 挂起图形（进度文档已验证 241–262ms 内落盘；顺序不能反，反了会挡住游戏线程）
- [ ] 切后台回来：进程保留、窗口/交换链重建（注意进度文档那个坑：**Android 给窗口的时机在 `onResume` 之后**，重建时必须自己先挡住出图线程）

**验收门**：能完整玩一段（移动/战斗/交互/存档/读档），无红桩，切后台回游戏不崩。

### M5 — 打包分发与壳模式

**目标**：产出「通用 APK + 打包套件」，别人能用自己的一份文件复现。

- [ ] `make_package.py` 适配 TotK 的包内容与校验项
- [ ] **保留 `PackageArchive` 的九文件成套校验、暂存目录 + 验收通过才换入、失败回滚**——进度文档记录过一次真实事故：13KB 的最小包被判导入成功，且「上一次能用的模块在打开新包之前就被删掉了」
- [ ] **模块必须解到内部存储**（外部 `/storage/emulated` 是 `noexec`，从那里 `dlopen` 会失败）
- [ ] **RomFS 必须整个目录打包，不按扩展名筛选**（漏掉隐藏文件 `.build.config` 会让游戏报错后静默返回 `nnMain`，症状像「游戏无故退出」；`ls` 不带 `-a` 还会显示「完全一致」）
- [ ] `host-subgroup-size.txt` 必须随包发布，缺了运行时直接中止
- [ ] **RomFS 超过 4GB 时 zip 方案要重做**：README 明确记录「`zipalign` 打不开超过 4GB 的 zip、`apksigner` 会在 4GB 边界报 Malformed ZIP Central Directory record」——D2R 的 8.88GiB 包是把大文件放 `romfs/` 绕开的，TotK 体积更大，要提前设计分卷或不进 zip 的传输方式
- [ ] CI：`build.yml` 推 `v*` tag 出 Release

**验收门**：一台干净电脑 + 自己的文件 + 套件，能完整跑通打包 → adb 装 → 手机导入 → 启动进游戏。

### M6 — 性能与稳定性

**目标**：热机稳态可用帧率，无系统性卡顿。

**直接照抄 Issue #59（上游给 Android 移植的性能建议，dodola/sydeEvans 都在这条下面）：**

1. **先同步上游**——宿主层/录制层与平台无关的改进可以直接受益（这条是针对当时的 fork 说的，但原则不变：**每次大改前先把上游 `d2r-mobile` 的宿主层改动合过来**）
2. **图形翻译挪到独立线程**：游戏线程只录命令，翻译+提交在另一根线程流水并行（iOS 实测掉帧中位数 85→56）
3. **分块渲染省带宽**（Adreno 同为分块渲染）：
   - 首绘覆盖全附件 → `loadOp = DONT_CARE`
   - 帧末不再读 → `storeOp = DONT_CARE`
   - 清屏并进通道开头 → `loadOp = CLEAR`
   - 连续通道合并
   - ⚠️ **必须先证明「首绘真的覆盖全附件」**，Issue #59 记录过翻车：800×450 中间缓冲有约 26 像素没被覆盖，按可省处理就出花点。要加哨兵回读核查，**并且先用故意判错的反例证明核查会报红**，否则「0 红」不可信；第一版探针因为回读和被核通道不在同一队列，读到上一帧，一直假绿。
4. **管线冷建卡顿**：`VkPipelineCache` 落盘 + 常用路线清单预热 + 新管线放后台线程建（D2R 已验证：菜单 30 条管线 826ms → 1.1ms；跨启动预热 127 条 447.7ms）。⚠️ **不要穷举预建**——组合数几十万量级，实际只用几百对。
5. **测量方法**（防自欺）：
   - 同进程内**运行时开关交替**（A/B 交替几十对 + 符号检验 p 值），不要跨局比
   - **热机稳态**：一局 ≥5 分钟，只取最后 30 秒
   - 掉帧按**上屏间隔**算（60 帧档 >25ms 算一次）
   - **到达场景用游戏内存判定**（关卡号/坐标），不要只看截图——「其实停在标题画面」出过好几次
   - **Vulkan 校验层一定要关掉再量**
6. **60 帧**：出图节拍跟显示刷新走、逻辑节拍不变——前提是先确认 TotK 的逻辑步进是否也与出图解耦（D2R 是固定 25 拍所以安全，**TotK 未验证，不能假设**）

**D2R 已验证、TotK 可直接借的优化**（来自进度文档第三轮，都有实测数）：
- UBO 改**动态偏移**描述符（`VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`）：描述符重建 1131→538 次/帧，`bind_shader` 5.4→2.77ms。⚠️ 该改动必须**同步动五处**（`dependencies.inc`、描述符 payload 编码、池配额、工作区选择、探针偏移记录），漏一处静默出错且编译不报。
- 分段计时 `nvn_vulkan_cpu_phases.inc`（只读、零行为改动）先量再改——D2R 就是靠它发现真凶是描述符重建，而不是原本怀疑的 UBO 重读。

**验收门**：一加 12 热机稳态实测数据（帧率/掉帧/GPU 耗时/温度），按上面第 5 条方法测，写进进度文档。

---

## 6. 从 Issues 与文档提炼的「开工前检查单」

这些是两个项目**真实踩过**的坑，直接搬进 TotK 脚手架：

| # | 坑 | 出处 | 在 TotK 里怎么防 |
|---|---|---|---|
| 1 | 着色器流水线全失败仍报成功 | 上游 Issue #5 | `set -o pipefail`；「完成」= 读 `_b_build.json` 无失败项；任何失败非零退出 |
| 2 | `DOTNET_ROOT` 未设 → 报成「翻译器不是用仓内源编的」 | 上游 Issue #19 | 先验证 dotnet 运行时，报错信息要区分「找不到运行时」和「哈希不匹配」 |
| 3 | bash 3.2 把 `$VAR` 后的全角字符当变量名一部分 | 上游 Issue #4 | 脚本显式声明支持的 shell 版本，或用 `#!/usr/bin/env bash` + 最低版本检查 |
| 4 | `timeout` 是 coreutils 的裸命令，Mac 上没有 → 设备离线假象 | 上游 Issue #7 | 脚本里不要依赖 GNU 专有命令 |
| 5 | 外部存储 `noexec` → 从 `/storage/emulated` `dlopen` 失败 | 进度文档 | 模块只解到应用内部目录 |
| 6 | 漏打包隐藏文件 `.build.config` → 游戏静默返回 `nnMain`，像「无故退出」 | 进度文档 | RomFS **整目录**打包；对比用 `ls -a` |
| 7 | 导入验收只查「至少一个文件」→ 13KB 假包判成功，且**先删了能用的旧包** | 进度文档 | 保留 `PackageArchive` 的成套校验 + 暂存换入 + 失败回滚 |
| 8 | 切后台顺序反了（先挂起图形再请存盘）→ 游戏线程被挡，0 次提交 | 进度文档 | 先存盘 → 冻结时钟 → 挂起图形 |
| 9 | `onResume` **之后**才给窗口 | 进度文档 | 重建交换链时自己先挡住出图线程 |
| 10 | 「首绘覆盖全附件」证明不足 → 花点；哨兵核查读到上一帧 → 假绿 | Issue #59 | 哨兵回读同队列；先用反例证明核查会报红 |
| 11 | 把静止场景数据当移动/战斗数据 | 进度文档 + Issue #59 | 性能结论必须标注场景与热机状态 |
| 12 | `hactool` 解密失败仍返回 0 | 进度文档 | 检查工具自身错误输出，不认退出码 |
| 13 | 不同 GPU 不能套用驱动与子组配置 | GPU 驱动文档 | Adreno 750 单独选型 + 实测 subgroup |
| 14 | GPL-3.0（Ryujinx 翻译、Eden 胶水）不能并入 MIT 项目 | 两份 README + 超分调研 | 参考思路，不拷代码；许可证边界写进 CONTRIBUTING |

---

## 7. 建议的脚手架目录（fork 后新增部分）

```
<本仓库>                          # 分支 totk/scaffold
├── dm/
│   ├── tools/
│   │   ├── patch_nso.py          # 改：三值 RULESET + TotK 构建号
│   │   └── hle_inventory.py      # 直接用，产出 TotK 的 HLE 需求清单
│   ├── host/
│   │   ├── (hle_svc/hle_thread/hle_fs/hle_hid/hle_audio ...)   # 复用
│   │   └── (删除全部 dm_*.c、D2R 专属 hle_*.c)
│   ├── gfx/
│   │   ├── nvn/
│   │   │   ├── names.txt         # ★ TotK 重生成
│   │   │   ├── nvn_slots.tsv     # ★ TotK 重生成
│   │   │   └── shader_facts.tsv  # ★ 换生成来源（§4.4）
│   │   └── tools/                # 翻译链复用
│   └── android/                  # 宿主/打包/驱动/触控基本复用
├── docs/
│   ├── TOTK_PORT_PROGRESS.zh-CN.md   # ★ 唯一的「中断后继续入口」，随工作更新
│   ├── TOTK_GAME_FILES.zh-CN.md      # 自己的文件怎么准备（版本要钉死）
│   ├── TOTK_DIFF_FROM_D2R.zh-CN.md   # §3 表格的持续更新版
│   └── TOTK_SHADER_FACTS.zh-CN.md    # §4.4 的方案与证据
├── .claude/skills/totk-package/      # 从 d2r-package 技能改名改内容
└── (d2r-mobile 只读参考，不检出到工作树)
```

**文档纪律**（照抄上游）：
- `TOTK_PORT_PROGRESS.zh-CN.md` 开头写「此文件随工作更新，是中断后继续移植的入口」，每轮工作把**当前状态**放最前面，旧记录保留仅供追溯。
- 每个性能/正确性结论必须带**真机日志、场景、热机状态**；没跑的直接写「没跑」（上游 CONTRIBUTING 的原话：「提交改动时写明你实际跑了哪些、结果如何；没跑的直接说没跑」）。
- **不提交任何游戏内容**：程序、美术、着色器、存档、以及由它们生成的图/表/代码都不进仓库。随仓库带的只有「接口信息」（NVN 函数表、着色器接口描述、程序内地址），加这类东西要先开 Issue 商量。

---

## 8. 立即可以动手的前三步

1. ~~在本仓库开 `totk/scaffold` 分支~~ —— **已完成**（分支已建并推到 origin）。拆成两步走：先提交检查工具的 Windows 诚实性修复建立**可验证基线**（`ci_checks.py` 5 通过 / 0 失败），再做「裁剪提交」删 §2 清单里的 D2R 专属资产。先修检查的理由：不先有可信基线，后面的裁剪就无法区分「删对了」和「删坏了」。
2. **填 §3 的表**：把自己的 TotK 文件放进工作区，用 `dm/tools/nso.py` + `extract_packages.py` 读出构建号、模块清单、大小；用现有分析脚本统计 NVN 取址函数数。—— 决定后面每一阶段的实际工作量。
3. **在 M0 阶段就解决 §4.4**：确认 TotK 着色器包里有没有可用的反射/元数据（方案 D），并实测「全默认值翻译 → 画面是否可接受」。—— 这是唯一可能推翻整条路线的风险点，越早知道越好。

---

## 9. 必须说清楚的边界

- **合法前提**：你必须拥有自己的一份 TotK（从自己的主机用 nxdumptool 导出）。仓库、Release、数据包、Issues 里都不出现游戏文件或密钥。两个上游项目在这点上立场一致，照做即可。
- **工作量级**：D2R 走到「60 FPS 可玩」，上游从 iOS 起做了约半年、fork 从零到 Android 60FPS 约一周（AI 辅助高强度开发，见 Issue #59 的评论）。TotK 的模块/符号/NVN/着色器规模都更大，且**着色器事实表没有现成来源**，实际周期应按「D2R 的 2–4 倍」预留，并把 §4.4 当作 go/no-go 检查点。
- **不承诺**：本计划不承诺 TotK 能达到 60 FPS，也不承诺全部 NVN 特性都被覆盖。d2r-android 自己的 README 也写着「尚未达到全场景稳定 60 FPS，也不是完成全部验证的正式发行版」。
- **备选路线**：如果 M3 的事实表问题无解、或 M1 的服务面大到不可行，退回 Eden/Sudachi 这类模拟器是**合理结论而非失败**——它们已经解决了同一套问题，且对一加 12 有成熟的社区配置。原生移植的价值在于学习与技术挑战。
