# Agent 交接会话日志

> 只追加，不覆盖。最新记录放在最上方。
> 当前状态以 [HANDOFF](HANDOFF.zh-CN.md) 为准。

## 2026-10-21 03:05 Asia/Shanghai — [TOTK] NA-038：TotK 调用到的 NVN 接口全部补齐（缺口 103 → 0）

- 会话目标：按 NA-038 的清单，把「TotK 真正调用、宿主还接报红桩」的 NVN 接口逐个实现。
- 结果：**取址缺口 0、缺实现 0**（还剩 5 个是 `g_nops` 的空实现：`nvnCommandBufferWaitSync` 98 次、
  `nvnCommandBufferSetDepthBounds` 15 次、`nvnCommandBufferDispatchComputeIndirect` 3 次、
  `nvnCommandBufferSetShaderScratchMemory` 2 次、`nvnWindowFinalize` 2 次）。覆盖情况由 `dm/gfx/tools/nvn_coverage.py` 复查，并接进 `ci_checks.py` 当常设闸门。

[BEGIN] na-038-nvn-implement

- 命令：`dm/gfx/tools/nvn_coverage.py`、`dm/android/tools/build.py --game-run --version trim-b32 / trim-b33`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：TotK 调用的接口在宿主里都有实现；构建与闸门全绿。
- 日志路径：无
- 回滚点：`8136185`

[END] na-038-nvn-implement

- 退出码：`nvn_coverage.py --check` exit 0（缺实现 0）；`build.py --game-run --version trim-b33` exit 0；`ci_checks.py` 13 项通过（交接控制面那一项在本条更新后复跑）。
- 产物：`dm/gfx/nvn/hle_nvn.c`（a/b/c 三批实现）、`dm/gfx/nvn/nvn_obj.h`（`buffer_t` / `buffer_builder_t`、`p_draw` 加实例数、`p_clear_color` 加整数位）、
  `dm/android/native/nvn_vulkan_draw.inc`（实例绘制）、`dm/android/native/nvn_vulkan_tex.inc`（整数清除）、`dm/gfx/tools/nvn_coverage.py`（分类与闸门）、`dm/android/tools/ci_checks.py`（接线）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。合并句柄拆分、整数清除、实例绘制都只有静态依据。

证据（本条目对应的命令与退出码）：

- **缓冲族**：新增 `buffer_t` / `buffer_builder_t`（`nvn_obj.h`，用 `FITS` 断言塞进 `NVNbuffer` 0x30 / `NVNbufferBuilder` 0x40）；
  `nvnBufferMap` 返回 `池首地址 + 偏移`，`nvnBufferGetAddress` 同理；宿主用游戏给的真实内存（GPU 地址 = CPU 地址），
  所以 flush / invalidate 是空操作。
- **绘制**：`p_draw` 加 `base_instance` / `instances` 两个字段（`nvnCommandBufferDrawArrays` 记 1，保持旧行为）；
  Vulkan 侧 `vkCmdDraw(command, draw->count, draw->instances>0?draw->instances:1, draw->first, draw->base_instance>0?draw->base_instance:0)`。
- **整数清除**：`p_clear_color` 尾部加 `is_int` + `rgba_i[4]`；Vulkan 侧 `if(c->is_int) memcpy(color.uint32,...) else memcpy(color.float32,...)`。
- **返回值 ABI 的坑**：`NVNmemoryPool`（0x100 字节）与 `NVNmemoryPoolFlags`（0x60 字节）按值返回会走间接返回约定（x8），
  而游戏那边把 `NVNmemoryPool` 当指针用（值在 x0）→ 这几个接口改用 `NVN_NOPROTO` 按 64 位返回，不做签名检查。
- **明确的 no-op**（都写了理由）：虚拟内存池映射（明确失败并报红）、CPU 写贴图（报红）、预排布贴图上传（报红）、
  条件渲染（一律渲染，多画不少画）、保守光栅、tiled cache、transform feedback、ZCull 数据、shader scratch memory。
- 下一步：**NA-039** —— 把那 5 个空实现补成真实现（`WaitSync` 与 `DispatchComputeIndirect` 要动后端：新增录制 op + Vulkan 侧实现）。

## 2026-10-21 01:32 Asia/Shanghai — [TOTK] NA-037：TotK 的 NVN 接口面对齐（查出会直接崩的取址缺口 + 补 13 个接口 + 103 个缺口清单）

- 会话目标：手机断开期间，把 TotK 的 **NVN 接口面**查清并对齐到宿主（这是 M2「NVN 接管」的前置）。
- 结果：① **查出一个会直接崩的坑**：TotK 取址 **534** 个 NVN 名，其中 **13 个宿主的名字表里没有** → `nvn_lookup` 返回 NULL → 客体拿到空函数指针；② 名字表补到 536（D2R 的 523 个顺序不动 → 槽索引不变 → D2R 行为逐字节不变），13 个新接口落地；③ 静态扫描出 TotK 真正调用的 **213** 个接口，宿主已实现 **110** 个，**还缺 103 个**（M2 的工作清单）。

[BEGIN] na-037-nvn-surface

- 命令：`dm/gfx/tools/nvn_slots_auto.py`、`dm/gfx/tools/nvn_table.py`、`dm/gfx/tools/nvn_coverage.py`、`dm/android/tools/build.py --game-run --version trim-b31`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：名字表覆盖 TotK 的全部取址名；13 个新接口有实现；缺口清单可复查。
- 日志路径：无（只读核对 + 构建）
- 回滚点：`0dab668`

[END] na-037-nvn-surface

- 退出码：`build.py --game-run --version trim-b31` exit 0；`nvn_table.py --check` exit 0；`nvn_coverage.py` exit 0（取址缺口 0 / 实现缺口 103）。
- 产物：仓库内 `dm/gfx/tools/nvn_slots_auto.py`、`dm/gfx/tools/nvn_table.py`、`dm/gfx/tools/nvn_coverage.py`、`dm/gfx/nvn/nvn_names_totk.txt`、`dm/gfx/nvn/nvn_calls_totk.tsv`；改动 `dm/gfx/nvn/names.txt`（523→536）、`nvn_thunks.S`、`nvn_count.h`、`nvn_protos.h`、`hle_nvn.c`；APK `dm/android/build/D2R-Android-port.apk`（trim-b31）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。合并句柄拆分只有静态依据，待真机出图确认。

证据（本条目对应的命令与退出码）：

- **取址缺口（会崩）**：`nvn_slots_auto.py` 在 `D:\Switch\totk-work\nso\upd_main.img`（.text 尾 `0x2ba61f0`）自动定位到取址函数 `0xbbfac0`，
  解析出 **534** 个名字（TotK 的加载函数形态是 `adrp 槽页; ldr x8,[x8,#off]; str x0,[x8]` 的二次间接，与 D2R 的直接存储不同，
  工具两种都认）。与 `dm/gfx/nvn/names.txt` 比对：**13 个名字宿主的表里没有**
  （`nvnTextureBuilderGetViewOffset`、`nvnProgramGetSubtileSize`、`nvnCommandBufferSetControlMemoryCallbackEnabled`、
  6 个 `…Deferred`、`nvnCommandBufferOverrideSubtileSize`、`nvnCommandBufferSetZCullZF32CompressionEnable`、
  `nvnCommandBufferSetProvokingVertexMode`、`nvnDeviceSetAutomaticCheckpointsMask`）
  → `hle_nvn.c` 的 `nvn_lookup` 查不到就返回 NULL → 客体拿到空函数指针。
- **名字表扩展可复现**：`nvn_table.py` 先在改动前跑 `--check`，能把 `nvn_thunks.S` / `nvn_count.h` / `nvn_protos.h`
  **逐字节复现**（exit 0），再 `--merge` TotK 名字表 → 追加 13 个名字、重生成三张表（536）。
  `gen_protos.py` 需要仓外的 Nintendo `nvn.h`，所以新工具只依赖名字表。
- **13 个新接口的实现依据**：从 TotK 二进制里读出实际调用形态（例：`nvnCommandBufferSetControlMemoryCallbackEnabled`
  在 `0xd8960` 处是 `x0=cmdbuf; w1=0` 两参）；6 个延迟绑定转调对应的普通绑定（同参同义，把「延后生效」改成「即时生效」）；
  两个查询（视图偏移 / 子块尺寸）**不写出参**，避免写错地址。
- **合并贴图绑定**：`nvnCommandBufferBindTextures` 此前是报红桩（D2R 不调；TotK 调 **260** 次）→
  按合并句柄（纹理 ID 低 20 位 + 采样器 ID 第 20..31 位，与 `dm/android/native/nvn_c2_layout.h` 的 TotK 档位一致）
  拆成贴图 / 采样器两条绑定记录，后端在合并档位下正好用这两个数组重新打包。
- **调用面清单**：静态扫描 TotK main 的 .text 里 `adrp 槽页; ldr [xN,#off]; ldr [xN]; blr xN` 这种间接调用
  → **213** 个接口被调用、**2,946** 个调用点（`dm/gfx/nvn/nvn_calls_totk.tsv`）。
  与宿主实现表比对（`nvn_coverage.py`）：**缺 103 个**，缺口最大的依次是
  `nvnBufferFlushMappedRange`(132)、`nvnCommandBufferDrawElementsBaseVertex`(103)、`nvnDeviceGetTexelFetchHandle`(103)、
  `nvnCommandBufferWaitSync`(98)、`nvnCommandBufferSetRenderEnableConditional`(60)、`nvnMemoryPoolInvalidateMappedRange`(55)、
  `nvnCommandBufferClearColori`(39)、`nvnCommandBufferBindImage`(29)。
- **D2R 不变**：名字表前 523 个名字顺序未动 → 槽索引未动；新增的 13 个接口 D2R 不调用；
  `nvnCommandBufferBindTextures` D2R 也不调用（D2R 走分离贴图）。D2R 路径逐字节不变。
- 下一步：**NA-038** —— 按调用点数从高到低补齐那 103 个接口（不需要手机）。

## 2026-10-21 07:40 Asia/Shanghai — [TOTK] 收口三件事：x18 那条其实是空谈、D2R 的 Android 翻译器是上一轮改坏的、数据路径对得上

- 会话目标：把交接清单里剩下的、能在本机查清的三条查清。
- 结果：① 「分支跳进独占窗口中间」那类形态**在 TotK 下根本不会被处理**（整套 x18 机制由 `REWRITE_X18` 开关控制，TotK 规则域为关）；② **D2R 的 Android 着色器翻译器是上一轮（`3a9ea0c`）改坏的**（基座新增了按作业作答的 fp64，模板又注入了一个同名成员 → CS0111，编译不过），本轮修好；③ 宿主的数据路径映射**不假设 D2R 的 `data/` 前缀**，`rom:/Shader/xxx` 直接落到 `<DM_ROMFS>/Shader/xxx`，TotK 的 RomFS 树能原样对上。

[BEGIN] na-036-loose-ends

- 命令：`git log -S`、`dm/tools/verify_totk_rewrite.py`、读 `dm/tools/patch_nso.py` 与 `dm/host/hle_fs.c`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：把这三条查清并写进交接。
- 日志路径：无（只读核对）
- 回滚点：`36807df`

[END] na-036-loose-ends

- 退出码：只读核对，无构建。
- 产物：交接文档与日志更新。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **x18 / 独占窗口**：`dm/tools/patch_nso.py` 里 `REWRITE_X18 = RULESET != 'totk-run-v1'`（第 206 行），
  而 `kinds` 里的 'x18' 条目只在 `REWRITE_X18` 为真时才会写入（第 616 行）；
  独占窗口与 `br x18` 跳转表的搜索只在「含有 x18 条目的函数」里做（第 625 行）——
  所以 TotK 规则域下**窗口与跳转表一个都找不到**，「分支跳进独占窗口中间」这类形态压根不会被处理 ✓。
  与 `verify_totk_rewrite.py` 的实测一致：改动只落在登记的改写点上，没有一处涉及 x18 ✓。
- **D2R 的 Android 翻译器是被上一轮改坏的**：`git show 3a9ea0c^:…/Program.cs` 里基座**没有** `QueryHostSupportsShaderFloat64`，
  模板注入一个不重名 ✓ 能编译 ✓；`3a9ea0c` 给基座加了按作业作答的 `host_no_fp64` ✓ → 模板再注入一个同名成员 ✗ → CS0111 ✗ →
  **D2R 的 Android 着色器库从那以后就构建不出来**。本轮把注入改成**替换**基座那一条 ✓，
  并让 c[2] 句柄表区间按作业给（缺省仍是 D2R 的 0x168/0x568 ✓，D2R 产物不变 ✓）。已实测能构建 ✓。
- **数据路径**：`dm/host/hle_fs.c` 的 `host_path_ex()` 把客体的 `rom:/<路径>` 逐段拼到挂载目录上，
  **没有**任何 D2R 专属的 `data/` 前缀假设 ✓；`DM_ROMFS_OVERLAY` 的多层覆盖也保留着 ✓（将来接上 BKTR 补丁时用得上）。
  所以包里 `romfs/Shader/...` 会被解到 `<外部>/d2r-package/romfs/Shader/...` ✓，正是宿主要开的路径 ✓。
- **歧义控制键**：两个变体差的是 Maxwell 私有编码的机器码（**不是 ARM64**，capstone 解不了），
  其中一部分落在 SPH 之后的填充区 ✓。要判"游戏用的是哪一个"只能靠真机画面 ✓，静态判不了。
- 下一步：**NA-036** —— 手机回来后推包、导入、开机看日志。

## 2026-10-21 06:10 Asia/Shanghai — [TOTK] 客体导入符号的落地核对：1,350 个导入全部有提供者

- 会话目标：在等手机的这段时间里，把"开机第一道门"先验掉。
- 结果：TotK 三个模块的导入符号**全部有提供者**（160 个来自宿主 HLE、1,182 个来自 sdk/subsdk0 两个模块本身、只有 8 个 `glslc*` 无人提供而那 8 个本就不该被调用）—— 符号解析这一关是通的，真机开机不会因为"少一个符号"直接死掉。

[BEGIN] na-036-guest-imports

- 命令：`D:\Switch\.tools\venv\Scripts\python.exe dm\tools\check_guest_imports.py --modules D:\Switch\totk-work\upd-exefs --inventory D:\Switch\handoff-hle-inventory.tsv`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：每个导入都有提供者（宿主 HLE 或别的模块），否则列出并以非零码退出。
- 日志路径：无（只读核对）
- 回滚点：`36807df`

[END] na-036-guest-imports

- 退出码：exit 0 ✓；数据包清单核对 exit 0 ✓；`ci_checks.py` 13 项通过 / 0 失败 ✓。
- 产物：仓库内新增 `dm/tools/check_guest_imports.py`（提交 `36807df`）；仓库外：重出的数据包 `D:\Switch\totk-work\package-totk\totk-package.zip`（16.31 GiB，着色器已是按 Android 口径重译的 ✓）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **数字**：main 导入 679 / 导出 26，sdk 导入 8 / 导出 23,030，subsdk0 导入 663 / 导出 9,446；
  合计 1,350 个导入 —— 宿主 HLE 提供 160，其它模块提供 1,182，**无人提供 0**（只有 8 个 `glslc*`：NVIDIA 的运行时 GLSL 编译器，
  着色器已离线预译，游戏不会调它 ✓）。
- **一处自我纠错**：我第一次只拿「宿主 HLE 表」去比，得出"缺 575 个"的结论 —— 那是**比错了对象**：
  nn::os / nn::util / nn::prepo 这些是 **sdk 与 subsdk0 自己导出的**（sdk 导出 23,030 个 ✓），不是宿主的活。
  宿主与模块之间的符号解析本来就该按「HLE ∪ 其它模块的导出」判定，这正是新工具采用的口径 ✓。
- **工具**：`dm/tools/check_guest_imports.py` 按装载器的口径解析（`dm/tools/nso_stats.py` 的 NSO 读取 ✓），
  逐个模块列出导入/导出，再用 HLE 清单（`dm/tools/hle_inventory.py` 的产物 ✓）判定落地；
  `--allow-prefix` 默认放行 `glslc` 前缀 ✓。
- **数据包已重出**：清单为 game 9 / romfs 304,207 / shaders 11,069，着色器 314,580,877 字节
  （上一版是 314,730,665 ✓ —— 差值正是按 Android 口径重译的结果 ✓）。
- **BKTR 的排查结果**：更新包那个段的 fs_header 与本体同构（只有 media type 是 4 而不是 3），逻辑大小 17 GB 而物理 456 MiB。
  依次排除：明文 Brotli ✗；按其它段同样的 CTR 解密后 Brotli ✗；XTS+头密钥 ✗；
  **在正确的第 5 层偏移（base=0x1fe0000）上重试 CTR 与 XTS（头密钥）也仍是随机字节** ✗
  （同一套代码解本体段在 base=0x1fe8000 上得到结构化的 RomFS 头 ✓，说明探针本身没问题）。
  结论：这一段的加密方式与其它段不同，**在没有参考实现（本机连不上 GitHub 取不到 hactool 源码）时解不开**。
- 下一步：**NA-036** —— 手机回来后推包、导入、开机看日志。

## 2026-10-21 06:10 Asia/Shanghai — [TOTK] 客体导入符号的落地核对：1,350 个导入全部有提供者

- 会话目标：在等手机的这段时间里，把"开机第一道门"先验掉。
- 结果：TotK 三个模块的导入符号**全部有提供者**（160 个来自宿主 HLE、1,182 个来自 sdk/subsdk0 两个模块本身、只有 8 个 `glslc*` 无人提供而那 8 个本就不该被调用）—— 符号解析这一关是通的，真机开机不会因为"少一个符号"直接死掉。

[BEGIN] na-036-guest-imports

- 命令：`D:\Switch\.tools\venv\Scripts\python.exe dm\tools\check_guest_imports.py --modules D:\Switch\totk-work\upd-exefs --inventory D:\Switch\handoff-hle-inventory.tsv`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：每个导入都有提供者（宿主 HLE 或别的模块），否则列出并以非零码退出。
- 日志路径：无（只读核对）
- 回滚点：`36807df`

[END] na-036-guest-imports

- 退出码：exit 0 ✓；数据包清单核对 exit 0 ✓；`ci_checks.py` 13 项通过 / 0 失败 ✓。
- 产物：仓库内新增 `dm/tools/check_guest_imports.py`（提交 `36807df`）；仓库外：重出的数据包 `D:\Switch\totk-work\package-totk\totk-package.zip`（16.31 GiB，着色器已是按 Android 口径重译的 ✓）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **数字**：main 导入 679 / 导出 26，sdk 导入 8 / 导出 23,030，subsdk0 导入 663 / 导出 9,446；
  合计 1,350 个导入 —— 宿主 HLE 提供 160，其它模块提供 1,182，**无人提供 0**（只有 8 个 `glslc*`：NVIDIA 的运行时 GLSL 编译器，
  着色器已离线预译，游戏不会调它 ✓）。
- **一处自我纠错**：我第一次只拿「宿主 HLE 表」去比，得出"缺 575 个"的结论 —— 那是**比错了对象**：
  nn::os / nn::util / nn::prepo 这些是 **sdk 与 subsdk0 自己导出的**（sdk 导出 23,030 个 ✓），不是宿主的活。
  宿主与模块之间的符号解析本来就该按「HLE ∪ 其它模块的导出」判定，这正是新工具采用的口径 ✓。
- **工具**：`dm/tools/check_guest_imports.py` 按装载器的口径解析（`dm/tools/nso_stats.py` 的 NSO 读取 ✓），
  逐个模块列出导入/导出，再用 HLE 清单（`dm/tools/hle_inventory.py` 的产物 ✓）判定落地；
  `--allow-prefix` 默认放行 `glslc` 前缀 ✓。
- **数据包已重出**：清单为 game 9 / romfs 304,207 / shaders 11,069，着色器 314,580,877 字节
  （上一版是 314,730,665 ✓ —— 差值正是按 Android 口径重译的结果 ✓）。
- **BKTR 的排查结果**：更新包那个段的 fs_header 与本体同构（只有 media type 是 4 而不是 3），逻辑大小 17 GB 而物理 456 MiB；
  依次试过：明文 Brotli ✗、按其它段同样的 CTR 解密后 Brotli ✗、XTS+头密钥后 Brotli ✗ → 都不是 Brotli 流，
  只能逆向或等一份参考实现。
- 下一步：**NA-036** —— 手机回来后推包、导入、开机看日志。

## 2026-10-21 04:40 Asia/Shanghai — [TOTK] 着色器按 Android 口径重译：修掉「32 子组 + 描述符集撞车」

- 会话目标：把不依赖手机的事做完，并核实上一轮「已验证」的说法。
- 结果：**发现并修掉一个真实缺陷** —— TotK 的着色器此前是用**桌面版翻译器**译的，它既不认作业里的 `host_subgroup_size`（一律按 32 宽子组），也不分每阶段的描述符集；一加 12 实测是 **64** 宽子组，顶点与片元的绑定号还挤在同一个描述符集里。已改用 **Android 口径的翻译器**全量重译（9,807/9,807，0 失败）并重打包。顺带发现 **D2R 的 Android 翻译器根本构建不出来**（重名成员 CS0111），也一并修好了。另用实测证明 TotK 的改写不碰 x18。

[BEGIN] na-036-android-shaped-shaders

- 命令：
  1. `dm/android/tools/build_android_translator.py --out … --dotnet …\tools\dotnet10\dotnet.exe`
  2. `dm/gfx/tools/totk_xlate.py --index … --spirv … --xlate …\dmsh_android.dll --shards 6`
  3. `dm/gfx/tools/totk_shader_package.py --index … --spirv … --out …` 与 `--verify-shaders …`
  4. `dm/tools/verify_totk_rewrite.py --exefs … --patched …`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：Android 翻译器能构建；重译全绿；描述符集与子组口径正确；包重建；改写不碰 x18。
- 日志路径：`D:\Switch\totk-work\xlate-android.log`、`D:\Switch\totk-work\cache\package-totk3.log`
- 回滚点：`837228b`

[END] na-036-android-shaped-shaders

- 退出码：翻译器构建 exit 0 ✓；全量重译 exit 0（9,807 成功 / 0 失败 ✓）；重打包 exit 0 ✓；`--verify-shaders` exit 0 ✓；`verify_totk_rewrite.py` exit 0 ✓；`ci_checks.py` 13 项通过 / 0 失败 ✓。
- 产物：`D:\Switch\totk-work\xlate-android\`（重译的 SPIR-V）、`D:\Switch\totk-work\android-translator\`（Android 翻译器）、`D:\Switch\totk-work\package-totk\`（着色器包与数据包）；仓库内新增 `dm/android/tools/build_android_translator.py` 与 `dm/tools/verify_totk_rewrite.py`，修改 `dm/android/tools/build_shaders.py` 与 `dm/gfx/tools/totk_xlate.py`（提交 `837228b`）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **★ 上一轮「已验证」的说法过头了，这里纠正**：TotK 的 SPIR-V 是用 `dm/gfx/tools/dmsh_xlate`（桌面版）译的，
  而 D2R 的 Android 管线用的是 `dm/android/tools/build_shaders.py` 从同一份源再注入几处得到的**另一个**翻译器。
  桌面那个**不认** `host_subgroup_size`（一律 32 宽子组）、**不分**每阶段描述符集 →
  ① 一加 12 实测子组是 **64**（探针实测），子组运算会按错的宽度算；
  ② 顶点与片元的绑定号挤在描述符集 0 里，互相撞车。
  上一轮我校验的是**文件格式与键命名**，没校验**翻译口径**，就说"已验证通过"，这个说法不成立。
- **重译结果**：9,807 个键全部成功、0 失败，SPIR-V 539,594,700 字节；逐个校验魔数 **0 个坏** ✓；
  描述符集分布：**vs 4,232 个全在集 0**、**ps 5,453 个是 {0,1}**（另 104 个无绑定，只有 {0}）、cs 18 个全在集 0 ✓。
- **D2R 的 Android 翻译器此前构建不出来**：模板往源里注入 `QueryHostSupportsShaderFloat64`，而基座里已经有一个
  （按作业的 `host_no_fp64` 作答）→ 同名成员 CS0111，编译直接失败。现在改成**替换**而不是追加 ✓，
  并且 c[2] 句柄表区间改成**按作业给**（`c2_tex_base` / `c2_tex_end`，缺省仍是 D2R 的 0x168/0x568 ✓ 所以 D2R 产物不变）。
- **TotK 作业改成 Android 口径**：`totk_xlate.py` 现在带 `host_subgroup_size=64`（真机实测值）、每阶段独立描述符集、
  以及 c[2] 区间 0x20..0x120 ✓（桌面翻译器会忽略这三项，正是它们之前被漏掉的原因）。
- **x18 的担心被证伪**：新增 `dm/tools/verify_totk_rewrite.py`，把原始 NSO 的 .text 与改写后的映像逐字节比：
  main 改 3,248 字节 / 814 段（全部 `tpidr_r`）、sdk 改 919 字节 / 230 段（tpidr_r / tpidrro_r / tpidr_w / cntpct / svc）、
  subsdk0 无改动；**每一处差异都落在登记的改写点上，没有旁改**，且**没有一个改写点涉及 x18 / w18** ✓。
  结论：「TotK 规则域不做 x18 改写」这条决定是安全的（交接里"分支跳进独占窗口中间"那类形态仍无实测覆盖）。
- **Mac 侧成本不变**：`build_shaders.py` 不在翻译链版本的计算文件里，所以本轮改动不移动链版本；
  `dmsh_chain.h` 里的版本本来就过期（上一轮改 `dmsh_xlate/Program.cs` 时就变了），Mac 侧仍需按原清单重建。
- 下一步：**NA-036** —— 手机回来后推包、导入、开机看日志。

## 2026-10-21 02:10 Asia/Shanghai — [TOTK] 启动界面的游戏档位、导入上限、着色器包按档位校验

- 会话目标：把不依赖手机的事做完。
- 结果：启动界面能切「暗黑2 / 王国之泪」两档；导入器的条目上限原本会把 TotK 的包判成「太大」，已修；着色器包现在能按档位自动核对句柄表区间 —— **从翻译产物独立印证了 TotK 用合并句柄表 0x20+8r**。手机仍完全断开，推包与开机顺延。

[BEGIN] na-036-launcher-and-caps

- 命令：`dm/ios/tools/dm_i18n.py --check`、`dm/android/tools/build.py --game-run --version trim-b30`、`dm/gfx/tools/totk_shader_package.py --verify-shaders …`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：中英表一致、APK 能构建、着色器包的句柄偏移落在 TotK 的区间里、闸门全绿。
- 日志路径：`D:\Switch\totk-work\`
- 回滚点：`047c0dc`

[END] na-036-launcher-and-caps

- 退出码：`dm_i18n.py --check` exit 0（204 条 ✓）；`build.py --game-run --version trim-b30` exit 0 ✓；
  `totk_shader_package.py --verify-shaders` exit 0 ✓；`ci_checks.py` 12 项通过（交接控制面一项在本条更新后重跑）。
- 产物：启动界面的「游戏」行与三条文案、导入条目上限 600,000、着色器包的 `--verify-shaders` 模式；
  APK `dm/android/build/D2R-Android-port.apk`（trim-b30）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **启动界面**：`LauncherActivity.java` 新增 `GAME_STATES = {"d2r", "totk"}`、「游戏」行、状态文件里的 `game=`，
  以及写进 `launch-settings.conf` 的 **`game_profile=`** ✓（并把 `game_profile` 加进 `OWNED_KEYS`，
  重写配置时不会抹掉 ✓）。native 侧早就支持这个键（`launch_settings.c` → `DM_GAME_PROFILE` ✓），缺的是界面这一头。
- **导入上限**：`PackageArchive.java` 的 `MAX_ENTRIES` 原本是 **300,000**，而 TotK 的包有 **315,286** 个条目
  → 会被判成「太大」直接拒掉。现在改成 600,000（仍然只用来挡恶意包 ✓），注释里写明哪个包需要余量 ✓。
  `MAX_TOTAL_BYTES`（24 GiB）与 `MAX_ENTRY_BYTES`（12 GiB）本来就够 ✓。
- **★ 独立印证 c[2] 布局**：新增 `totk_shader_package.py --verify-shaders` —— 逐个 `.meta` 解析贴图/图像绑定的
  c[2] 字节偏移 `(handle & 0x3fff) * 4`，要求落在该档位的句柄表区间且 8 字节对齐。
  实测 TotK 包：**5,534 个 meta、31,626 个贴图绑定、恰好 32 个不同偏移（0x20 .. 0x118）**，
  **全部落在 [0x20, 0x120) 且 8 字节对齐 ✓** —— 说明机器码里的贴图立即数真的指着合并句柄表那张表，
  宿主按 `0x20 + 8r` 去取是对的 ✓（此前只有「立即数落在 0x20..0x118」这一个统计口径，现在由翻译产物本身复核了一遍）。
- **BKTR 的进展**：那个段的 fs_header 与本体同构，只是 media type 是 4 而不是 3；IVFC 声称逻辑大小 17 GB 而物理只有 456 MiB
  → **确实是增量补丁** ✓。但按 CTR 解出来整段都是随机字节（哈希表本该有大量零）→ **加密方式与其它段不同** ✗。
  上游 hactool 1.4.0 报 "Invalid BKTR layout!"，而本机连不上 GitHub 取不到它的实现 → 只能逆向，暂缓。
- **部署脚本**：`deploy_totk.py` 改成「推包 zip + 写 game_profile」，其余交给启动界面的导入流程
  （它本来就把 `game/` 放内部存储、`romfs/` 与 `shaders/` 放外部存储 ✓）。
- 下一步：**NA-036** —— 手机回来后推包、导入、开机看日志。

## 2026-10-21 01:20 Asia/Shanghai — [TOTK] 启动界面加「游戏」档位（D2R / TotK）

- 会话目标：把剩下的、能不依赖手机做完的事做完。
- 结果：启动界面多了一行「游戏」，可以在**暗黑破坏神 II**与**塞尔达传说：王国之泪**之间切换；它写进 `launch-settings.conf` 的 `game_profile` 键，native 据此选 c[2] 的句柄表布局（D2R 分离表 / TotK 合并表）。手机仍掉线，推包与开机顺延。

[BEGIN] na-036-launcher-game-profile

- 命令：`dm/ios/tools/dm_i18n.py --header`、`dm/ios/tools/dm_i18n.py --check`、`dm/android/tools/build.py --game-run --version trim-b30`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：中英表一致、APK 能构建、闸门全绿。
- 日志路径：`D:\Switch\totk-work\`
- 回滚点：`e946844`

[END] na-036-launcher-game-profile

- 退出码：`dm_i18n.py --check` exit 0（204 条 ✓）；`build.py --game-run --version trim-b30` exit 0（APK ✓）；`ci_checks.py` 12 项通过（交接控制面一项在本条更新后重跑）。
- 产物：启动界面的「游戏」行与三条中英文案；APK `dm/android/build/D2R-Android-port.apk`（trim-b30）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机掉线）。

证据（本条目对应的命令与退出码）：

- **启动界面**：`dm/android/java/org/d2r/android/port/LauncherActivity.java` 新增 `GAME_STATES = {"d2r", "totk"}`、
  「游戏」行（点一下切换 ✓）、显示文案、状态文件里的 `game=` ✓，
  以及写进 `launch-settings.conf` 的 **`game_profile=`** ✓（并把 `game_profile` 加进 `OWNED_KEYS`，
  这样重写配置时不会把它抹掉 ✓）。native 侧早就支持这个键（`launch_settings.c` 解析后写成 `DM_GAME_PROFILE` ✓），
  缺的是界面这一头。
- **中英表**：新增 `dmAndroidLaunchGame` / `dmAndroidLaunchGameD2R` / `dmAndroidLaunchGameTotK` 三条 ✓，
  `dm/ios/tools/dm_i18n.py --check` exit 0（204 条 ✓），生成头 `dm/host/dm_i18n_tab.h` 一并重出 ✓。
- **BKTR 的现状**（更新包的数据补丁解不开）：那个段的 `fs_header` 与本体同构，只是 media type 是 4 而不是 3 ✓；
  IVFC 的最后一层声称逻辑大小 17 GB 而物理只有 456 MiB → **确实是增量补丁** ✓。
  本机连不上 GitHub，取不到 hactool 的 BKTR 实现，只能逆向。
- 下一步：**NA-036** —— 手机回来后把包推上去、走启动界面的导入与「游戏」档位、开机看日志。

## 2026-10-21 00:30 Asia/Shanghai — [TOTK] NA-036 数据侧就绪：数据包打好并逐条校验，并修掉一个路径 bug

- 会话目标：把 TotK 的数据变成能推到手机上的东西，并查清有没有别的坑。
- 结果：**数据包已打好并逐条校验**（315,286 条目、0 重名、抽样逐字节一致）；**途中发现并修掉一个真的数据 bug**（RomFS 目录树遍历丢了父目录前缀）；手机中途掉线，推包与开机顺延。

[BEGIN] na-036-package-verify

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\totk_package.py --romfs-image … --ivfc … --shaders … --game … --output …`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build_package.py inspect …`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work\`）
- 预期结果：包内条目与清单一致、路径不重名、内容与映像一致；闸门全绿。
- 日志路径：`D:\Switch\totk-work\cache\package-totk2.log`
- 回滚点：`e946844`

[END] na-036-package-verify

- 退出码：出包 exit 0（16.31 GiB，RomFS 304,207 + 着色器 11,069 + 模块 9）；`inspect` 清单核对通过（`subgroup_size=64` ✓）；抽样 8 个文件与映像逐字节一致 ✓；`ci_checks.py` 12 项通过 / 0 项失败。
- 产物：`D:\Switch\totk-work\package-totk\totk-package.zip`；仓库内：`dm/tools/switch_nca.py` 与 `dm/android/tools/totk_package.py` 的遍历修复（提交 `e946844`）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机掉线）。

证据（本条目对应的命令与退出码）：

- **★ 修掉一个真的数据 bug**：RomFS 目录树遍历把每个目录**只带着自己的名字**入栈，父目录前缀丢了 ——
  于是嵌套目录里的文件路径被截断，不同层级里同名的目录会撞成同一个路径。
  实测本体 RomFS：**1,693 条重名路径，且同一路径下的内容不同**（说明是不同文件被放错了地方），
  第一次出的包就带着这个问题。修复后：**304,207 个文件、304,207 条唯一路径、0 重名**，
  路径深度也对了（最深 `Voice/Resource/USfr/EventFlowMsg/…` 五层 ✓）。
  这个 bug 在**原解包工具里也有**（`dm/tools/switch_nca.py` 的 `romfs_entries`），一并修了 ✓。
- **包的核对**：`build_package.py inspect` 给出清单 —— `game 9 / romfs 304,207 / shaders 11,069`，
  `subgroup_size=64`（一加 12 实测的子组大小 ✓），总字节 17.4 GB；包里 315,286 个条目、**0 重名** ✓；
  抽样 8 个文件与映像**逐字节一致** ✓。
- **启动界面的导入流程本来就够用**：`dm/android/java/org/d2r/android/port/PackageArchive.java` 里
  `game/` 落到**暂存目录（内部存储**，外部存储是 noexec 挂载、dlopen 会失败），其余落外部存储 ✓ ——
  所以包走 zip 导入这条路，宿主侧的目录约定不用改。
- **还差的数据层**：合并包里的 `d214ebdad75878d540c13f3155640f39.nca`（499.5 MB）的 romfs 段是 **`crypt: bktr`**，
  `switch_nca.py` 的 `read_section` 只支持 CTR 段 → **更新包的数据补丁解不开**（上游 hactool 1.4.0 同样报
  "Invalid BKTR layout!"；本机取不到 hactool 源码，GitHub 也连不上，只能逆向）。本体数据已完整可用，先按它跑。
- 下一步：**NA-036** —— 把包推上一加 12，走 M1 的「装载 → `nnMain`」。

## 2026-10-20 23:40 Asia/Shanghai — [TOTK] NA-036 第一阶段：TotK 数据管线打通（RomFS 映像 → 数据包 zip）

- 会话目标：把 TotK 的数据变成**能推到手机上**的东西。
- 结果：**本体数据完整可用**（解密后的 RomFS 映像 15.93 GiB、304,207 个文件，逐字节抽样验证过），数据包正在出；**更新包的 BKTR 补丁是唯一还差的数据层**。真机部署因设备掉线顺延。

[BEGIN] na-036-totk-data-pipeline

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\tools\switch_nca.py --prod-keys … romfs-export <NCA> --out D:\Switch\totk-work\base\romfs.img`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\totk_package.py --romfs-image … --ivfc … --shaders … --game … --output …`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\deploy_totk.py --romfs-image … --shaders … --game …`
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work\`）
- 预期结果：包里 RomFS 条目数与映像一致；推到手机后游戏活动能起来。
- 日志路径：`D:\Switch\totk-work\cache\package-totk.log`
- 回滚点：`dcd73cc`（数据管线提交）

[END] na-036-totk-data-pipeline

- 退出码：`romfs-export` exit 0（15.93 GiB / 304,207 个文件 / 2.5 分钟）；抽样比对 8 个一致、0 个不一致；`totk_package.py` 出包中；`ci_checks.py` 12 项通过 / 0 项失败。
- 产物：`D:\Switch\totk-work\base\romfs.img` + `romfs.img.ivfc`、`D:\Switch\totk-work\package-totk\totk-package.zip`（打包中）；仓库内新增 `dm/android/tools/totk_package.py`、`dm/android/tools/deploy_totk.py`、`dm/android/tests/test_package_layout.py`，修改 `dm/tools/switch_nca.py`。
- 结果：SUCCESS（数据侧第一阶段）
- 备注：**真机部署与开机本批 NOT RUN**（手机在会话中途掉线）。

证据（本条目对应的命令与退出码）：

- **为什么换路线**：TotK 的 RomFS 是 304,207 个文件（15.93 GiB）的深目录树。逐个解到盘上在这台机器上要几十小时
  （NTFS 小文件 + Defender，日志实测约 10,000 个/2.5 小时），而且 adb 没有推目录的本事（只能一个文件一个文件推）。
  → 改成**导出解密后的整段 RomFS 映像**（一个文件），再从映像直接出包。
- **导出**：`dm/tools/switch_nca.py romfs-export` 把 NCA 的 RomFS 段按 CTR 解密后顺序写出（15.93 GiB，2.5 分钟），
  并把 **IVFC 头**另存为 `romfs.img.ivfc` —— IVFC 头本来在 NCA 的头区（不在段数据里），
  读取方靠它才知道 RomFS 头在哪、各级偏移是多少。
- **验证**：从映像里按路径读出 8 个抽样文件，与先前解出的目录树**逐字节一致**（0 个不一致；另 5 个抽样当时还没解出来 ✓）。
- **出包**：`dm/android/tools/totk_package.py` 直接在映像上走目录树（304,207 个条目 ✓），把每个文件按**真实相对路径**
  写进 zip（`romfs/<路径>`），连同模块与着色器包一起打成启动界面能导入的数据包（zip64 ✓）。
  包内结构与 D2R 侧一致（`manifest.json` / `game/` / `romfs/` / `shaders/`）。
- **打包器的 TotK 布局**：`dm/android/tools/build_package.py` 新增 `--romfs-layout data|root` ——
  `data` 是 D2R 的老行为（`romfs/data/<名字>`，一字未动），`root` 保留整棵树的相对路径。
  新闸门 `dm/android/tests/test_package_layout.py` 用两棵合成目录各打一个包，核对包内路径、模块与分组档位文件。
- **部署脚本**：`dm/android/tools/deploy_totk.py` —— 模块推到**内部**存储（外部存储是 noexec 挂载，dlopen 会失败），
  资源与着色器推到外部存储，写 `manifest.json`（宿主看到它才走导入包那条路），
  并把 `game_profile=totk` 写进 `launch-settings.conf`（native 据此选 c[2] 的合并句柄布局；启动界面重写该文件时保留别人的键 ✓）。
- **还差的数据层**：合并包里的 `d214ebdad75878d540c13f3155640f39.nca`（499.5 MB）romfs 段是 **`crypt: bktr`**，
  而 `switch_nca.py` 的 `read_section` 只支持 CTR 段 → **更新包的数据补丁解不开**（上游 hactool 1.4.0 同样报
  "Invalid BKTR layout!"）。本体数据已完整可用，所以先按「本体数据 + v1.4.2 的模块」跑一遍。
- 下一步：**NA-036** —— 把包推上一加 12，走 M1 的「装载 → `nnMain`」。

## 2026-10-20 22:10 Asia/Shanghai — [TOTK] NA-035 第一版：TotK 着色器包按宿主口径打好（5,534 个宿主键）

- 会话目标：接着 NA-034 往下推 —— 让 TotK 的着色器**真的能被宿主按名找到**（此前两边键口径不同，宿主一个也找不到）。
- 结果：着色器包已生成并逐个按宿主的校验规则核对通过；**1,640 个歧义控制键**（同一个控制段对应多种机器码）有报告，取舍规则写在工具里。下一步转向 TotK 数据与真机装载。

[BEGIN] na-035-totk-shader-package

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\totk_shaders.py D:\Switch\totk-work\shaders-out D:\Switch\totk-work\shaders-index5`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\totk_shader_package.py --index D:\Switch\totk-work\shaders-index5\shader_index.tsv --spirv D:\Switch\totk-work\xlate-full --out D:\Switch\totk-work\package-totk --facts D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\test_totk_shader_package.py`
  4. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work\`）
- 预期结果：索引带宿主键；包按宿主键命名且 meta 全部合规；测试与闸门全绿。
- 日志路径：`D:\Switch\totk-work\package-totk\`（包与歧义报告）
- 回滚点：`2a140a8`（NA-034 业务提交）

[END] na-035-totk-shader-package

- 退出码：索引 exit 0（9,807 变体键 / 5,534 宿主键）；打包 exit 0（**5,534 个宿主键，缺翻译结果 0**）；格式测试 exit 0；`ci_checks.py` 11 项通过 / 0 项失败（交接控制面一项在本条更新后重跑）。
- 产物：`D:\Switch\totk-work\package-totk\shaders\<宿主键>.spv` 与 `.meta`（5,534 套）、`D:\Switch\totk-work\package-totk\ambiguity.tsv`、`D:\Switch\totk-work\package-totk\host-profile.json`、`D:\Switch\totk-work\shaders-index5\shader_index.tsv`；仓库内新增 `dm/gfx/tools/totk_shader_package.py` 与 `dm/gfx/tools/test_totk_shader_package.py`，修改 `dm/gfx/tools/totk_shaders.py`。
- 结果：SUCCESS
- 备注：**真机出图与进 `nnMain` 本批 NOT RUN**（TotK 数据还没装进手机）。

证据（本条目对应的命令与退出码）：

- **两个键口径本来就对不上（根因）**：宿主 `dm/android/native/nvn_vulkan_shader.inc` 的 `shader_get(control)` 用
  `sha256(控制段前 0x880 字节)[:16]` 当键，再按这个键去数据包找 `<键>.meta` 与 `<键>.spv`；
  而流水线 `dm/gfx/tools/totk_shaders.py` 的键是 `sha256(控制段+机器码+c1)[:16]`。
  **两个口径不同 → 宿主一个着色器都找不到**。
- **为什么 TotK 非得带机器码**：TotK 的归档里**同一个 NVN 控制段被多个机器码变体共用** ——
  实测 49,089 个变体，按 `(控制段+机器码+c1)` 只有 9,807 个唯一值，按控制段只有 **5,534** 个，
  其中 **1,640 个控制段对应多种机器码**（最多的一个 47 种），差异中位数 1,297 字节（最大 35,463 字节）——
  是真的不同着色器，不是填充差异。
- **本批做法**：新增 `dm/gfx/tools/totk_shader_package.py`，按**宿主口径**重新出包：
  索引里同时给出变体键与宿主键（`totk_shaders.py` 多一列 `host_key`）；
  包里每个宿主键一对 `<键>.spv` + `<键>.meta`；
  `meta` 用与 D2R 侧 `dm/android/tools/build_shaders.py` **完全相同**的 DMVK 格式
  （魔数、版本、阶段、描述符组、绑定数、c1 长度、属性数 + 每绑定 40 字节 + c1 + 32 个属性类型）；
  绑定表来自翻译产物的 `res.json`（cbufs/sbufs/textures/images），属性类型来自 SPIR-V 的输入位置加事实表的分量类型。
  **歧义控制段**按「出现次数最多」选一个变体，并把每个歧义控制段的全部候选写进 `ambiguity.tsv`。
- **逐个按宿主规则核对**：5,534 个 `meta` 全部满足宿主 `shader_load_by_key` 的校验
  （魔数 DMVK、版本 1、绑定数 ≤ 256、c1 长度 ≤ 65536、属性数 32，且**总字节数正好等于 28 + 绑定数×40 + c1 长度 + 128**），
  **不合规 0 个**；5,534 个 SPIR-V 的魔数 `0x07230203` **全部正确**；阶段分布 vs 1,725 / ps 3,791 / cs 18。
- **新闸门**：`dm/gfx/tools/test_totk_shader_package.py` 用合成的 res.json 与最小 SPIR-V 走一遍打包工具，
  再按宿主那条规则逐字节核对（绑定数、c1 字节、属性类型、文件总长）；已接进 `ci_checks.py`（11 项通过）。
- **仍要真机确认的**：1,640 个歧义控制段上「游戏实际用的是哪个变体」—— 现在的取舍规则是「出现次数最多」，
  真实规则要等游戏跑起来看画面才能定；这也是下一步数据装好之后的检查项之一。
- 下一步：**NA-036** —— 把 TotK 数据装进一加 12，走 M1 的「装载 → `nnMain`」。

## 2026-10-20 20:30 Asia/Shanghai — [TOTK] NA-034 收口：c[2] 布局按档位、驱动选型真机实测，并查出着色器键口径的新拦路虎

- 会话目标：执行 NA-034（把 c[2] 驱动常量段的句柄表布局做成按规则集可选，宿主与翻译器两侧一起改），并把 TotK 往一加 12 上推。
- 结果：**NA-034 完成并在一加 12 真机上验证**；**驱动选型收口**（系统驱动就是 Adreno 750 硬件驱动，仓库内置的 Turnip 在这台机器上根本装不上）；**查出比 c[2] 更要紧的新拦路虎**：宿主按 `sha256(控制段)` 找 SPIR-V，而 **TotK 的控制段不唯一**（1,640 个控制键对应多种机器码）→ 渲染必错。
- 用户侧：**一加 12 已插上并保持连接**（`3b864e51` / PJD110 / Android 16 / Adreno 750），本会话的验证全部在真机上做的。

[BEGIN] na-034-c2-layout-device

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b30`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\ci_checks.py`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\run_vulkan_probe.py`
  4. 真机：`vulkan-test`（NDK 编译 → `adb push` → `DM_VK_SHADERS=... /data/local/tmp/d2r-port/vulkan-test-arm64`）
  5. 真机：`launch-settings-test`（NDK 编译 → `adb push` → `/data/local/tmp/d2r-port/launch-settings-test /data/local/tmp/d2r-port`）
  6. `D:\Switch\.tools\venv\Scripts\python.exe tools\agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`（设备侧产物在 `dm/android/build/`，仓库外产物在 `D:\Switch\totk-work\`）
- 预期结果：宿主与真机两侧都按档位取 c[2] 布局；真机测试全绿；ci_checks 全绿；build exit 0；--verify exit 0。
- 日志路径：`D:\Switch\totk-work\`（勘察表）、`dm/android/build/`（APK 与测试二进制）
- 回滚点：`2a140a8`（NA-034 业务提交）

[END] na-034-c2-layout-device

- 退出码：`build.py --game-run --version trim-b30` exit 0（APK 17,742,287 字节）；`ci_checks.py` 10 通过 / 0 失败；真机 `vulkan-test` exit 0；真机 `launch-settings-test` exit 0（58 cases）；`run_vulkan_probe.py` exit 0；`agent_handoff_check.py --verify` exit 0。
- 产物：仓库内新增 `dm/android/native/nvn_c2_layout.h`、`dm/android/tools/vulkan_probe.c`、`dm/android/tools/run_vulkan_probe.py`、`dm/android/tests/c2_layout_test.c`、`dm/android/tests/c2_layout_test.inc`；修改宿主读侧/写侧、启动设置与四处测试；APK `dm/android/build/D2R-Android-port.apk`（trim-b30）。
- 结果：SUCCESS
- 备注：**TotK 真机出图与进 `nnMain` 本批 NOT RUN**（TotK 数据还没装进手机，且宿主的着色器键口径还没改 —— 见下一步 NA-035）。

证据（本条目对应的命令与退出码）：

- **c[2] 布局的实现**：新增 `dm/android/native/nvn_c2_layout.h`（D2R：分离贴图 0x168+8r、分离采样器 0x568+8r、图像 0x120+8r；TotK：合并句柄 0x20+8r 共 32 槽、图像 0x120+8r），布局由环境变量 `DM_GAME_PROFILE` 选；
  `dm/android/native/launch_settings.c` 新增 `game_profile` 键（d2r / totk）→ 写入 `DM_GAME_PROFILE`；
  读侧 `nvn_vulkan_handles.inc` 与写侧 `nvn_vulkan_shader.inc` 都改成按布局取；
  **D2R 的偏移与字节一字未动**（tex/samp/img 三段与原来完全一样）。
- **合并句柄的打包**：NVIDIA 的合并句柄 = 纹理 ID 低 20 位 + 采样器 ID 第 20..31 位；
  宿主本来就按 `handle & 0xfffff` 取纹理 ID、`(handle>>20)&0xfff` 取采样器 ID（`nvn_vulkan_shader.inc` 第 328/329 行），
  所以 TotK 侧写 `纹理ID | (采样器ID<<20)` 即可对上（`dm_nvn_combined_handle`）。
- **真机验证**：`vulkan-test` 在一加 12 上 exit 0，新增用例输出
  「Vulkan c[2] handle tables: D2R separate and TotK combined layouts match the shader offsets PASS」；
  启动设置测试 PASS（58 cases，含新增的 `game_profile` 三例与两个非法值用例）。
- **驱动选型（真机实测，不再是猜）**：新增 `dm/android/tools/vulkan_probe.c` + `run_vulkan_probe.py`，在手机上实测：
  `VK_ICD_FILENAMES=(unset)`、加载器 1.4.0、**物理设备 `Adreno (TM) 750`（type=1 独显，api=1.3.128，driver=0.762.41，vendor=0x5143）**、
  **subgroupSize=64**（与着色器按 64 子组构建的口径一致）、maxImageDimension2D=16384、maxComputeWorkGroupInvocations=1024、
  132 个设备扩展（含 `VK_EXT_shader_atomic_float`、`VK_EXT_depth_clip_control`、`VK_EXT_subgroup_size_control`、`VK_KHR_shader_float16_int8`，**没有** fp64）。
  仓库内置的 `dm/android/prebuilt/turnip/vulkan.purple.so`（meta.json 写明是 T30 / Adreno 830 构建）**`.dynsym` 里没有任何 `vk*` 导出**（只有 `tu_*` 模板与 libc 符号），
  而宿主是 `dlsym(driver, "vkGetInstanceProcAddr")` 取入口 → 在这台机器上装不上；**结论：走系统驱动**，启动界面保持「系统驱动」。
  （设备上 `/vendor/lib64/hw/vulkan.adreno.so` 在，`/vendor/etc/vulkan/` 等目录没有 ICD 清单，加载器靠 `ro.hardware.vulkan=adreno` 兜底找到驱动。）
- **三处既有的真机测试缺陷（本批修好）**：`uniform_arena_test.inc:27`、`binding_cache_test.inc:18`、`texel_forward_test.inc:48` + `index_test.inc:73`
  在一加 12 上失败。**用 stash 对比实测确认是既有问题**（未改动的基线代码在同一处同样失败），
  根因都是**断言了精确的内部计数器增量**（分配次数 / 读字节数 / flush 次数），而这些量随构建与 GPU 变；
  同一批里的**像素断言全部通过**（即渲染结果是对的）。现改成断言真正要保的契约：
  ① uniform 页按内容寻址 → 内容不变就复用同一页；内容变了必须换新页且**旧页的字节在本批 fence 前不能变**（原来要求 20 次同样的读给出 20 个不同的页，与实现的按内容寻址直接矛盾）；
  ② 第二次 draw 不得再分配新页（读了多少字节不是契约）；
  ③ c[0]/c[2] 的页只随**重新绑定**而变 → 测试改成走真实的 `OP_BIND_UBO` / `OP_BIND_TEX` 绑定路径（原来直接改 `state`，绕过了绑定路径，缓存当然不会失效）；
  ④ flush 的**次数**不是契约（宿主可以换一种方式满足依赖），要保的是「后来的部分写被合并进去」——由像素断言把关。
- **★ 新拦路虎：宿主着色器键的口径与 TotK 不匹配**：实测 TotK 的 49,089 个着色器变体里，
  `(控制段+机器码+c1)` 只有 **9,807** 个唯一值；而宿主口径 `sha256(控制段前 0x880 字节)[:16]` 只有 **5,534** 个唯一值，
  其中 **1,640 个控制键对应多种机器码**（最多的一个 **47 种**）→ **同一个控制段在不同变体里配不同机器码**。
  宿主 `dm/android/native/nvn_vulkan_shader.inc` 的 `shader_get(control)` 用的正是控制段哈希，
  而 `dm/gfx/tools/totk_shaders.py` 的键是 `sha256(控制段+机器码+c1)[:16]` → **两个口径不同**，
  同一控制键的多个变体会共用一个 SPIR-V，**TotK 渲染必错**。这就是下一步 NA-035。
- **仍未做**：TotK 数据装进手机、真机跑 TotK 到 `nnMain`、TotK 侧的宿主演示器数据（绑定反射）、翻译器侧的 c[2] 基址、
  更新包 RomFS 的 BKTR 补丁、改写器的 x18 适配、启动界面的游戏档位。
- 下一步：**NA-035** —— 让宿主的着色器键包含机器码（与流水线口径逐字节一致）。

## 2026-10-20 21:40 Asia/Shanghai — [TOTK] NA-033 收口：SPH 解析完、事实表坐实，并查出真机渲染的头号拦路虎（c[2] 布局）

- 会话目标：按交接文档执行 NA-033 —— 把「贴图维度 / 图像格式 / 属性分量类型」这三项事实的来源查清楚（SPH 里到底有什么），据此给计划 §4.4 画句号；同时把 TotK 往真机（一加 12）推。
- 结果：**§4.4 收口**（三类事实的来源全部落实）；**并查出一个比事实表更要紧的问题**：TotK 与 D2R 的 **c[2] 布局不同**，宿主把 D2R 的写死了 → **TotK 上一个贴图都绑不上，画面必然是黑的**。下一步动作因此从「继续查事实」改成「改 c[2] 布局」（NA-034）。
- 用户侧：一加 12 **本会话没有接上**（`adb devices` 返回空列表），真机部分顺延到 NA-034 之后；本会话的活全是本机可完成的。

[BEGIN] na-033-sph-facts

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\totk_facts.py --index D:\Switch\totk-work\shaders-index4\shader_index.tsv --code D:\Switch\totk-work\shaders-index4\code --out D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\totk_xlate.py --index D:\Switch\totk-work\xlate-full\changed_index.tsv --code D:\Switch\totk-work\shaders-index4\code --work D:\Switch\totk-work\xlate-facts2b --facts D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv --xlate D:\Switch\totk-work\tools\xlate\dmsh_xlate.dll --dotnet D:\Switch\totk-work\tools\dotnet\dotnet.exe --shards 6`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\ci_checks.py`
  4. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b29`
  5. `D:\Switch\.tools\venv\Scripts\python.exe tools\agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work\`）
- 预期结果：事实表 9,807 键；重译 4,778 个受影响键全部成功；ci_checks 全绿；build exit 0；--verify exit 0。
- 日志路径：`D:\Switch\totk-work\xlate-facts2b.log`、`D:\Switch\totk-work\build-trim-b29.log`
- 回滚点：`45d5254`（NA-033 业务提交）

[END] na-033-sph-facts

- 退出码：事实表 exit 0；重译 exit 0（4,778 成功 / 0 失败）；`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b29` exit 0；`agent_handoff_check.py --verify` exit 0。
- 产物：`D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv`（9,807 键的新事实表，仓库外）；`D:\Switch\totk-work\xlate-full\changed_index.tsv`（4,778 个受影响键）；`D:\Switch\totk-work\xlate-facts2b\out0..5\`（4,778 个新 SPIR-V + res.json）；`D:\Switch\totk-work\probe\sph\sph.tsv` 与 `sph\ctrl\`（9,807 个着色器的 SPH / 控制头勘察表）；仓库内新增 `dm/gfx/tools/totk_facts.py`（提交 `45d5254`）。
- 结果：SUCCESS
- 备注：**真机上的实际出图与进 `nnMain` 本批 NOT RUN**（一加 12 本会话未接上）；iOS / macOS 侧编译 NOT RUN。

证据（本条目对应的命令与退出码）：

- **SPH 的口径更正**：图形着色器的机器码区布局是 `0x30 字节 NVN 头（魔数 0x12345678） + 0x50 字节 SPH + 指令`。
  之前交接里写的「机器码前 0x30 字节是 SPH」**是错的** —— 0x30 是 NVN 头的大小，**SPH 是 0x50 字节**。
  权威来源是仓内 vendored 的 Ryujinx `Translation/ShaderHeader.cs`（`gpuAccessor.GetCode(address, 0x50)`），
  我们自己的 `dm/gfx/tools/dmsh_xlate/Program.cs` 写的也是「graphics = 0x50-byte SPH + instructions」，
  `dm/gfx/tools/maxwell_refs.py` 也写着「0x30 NVN 头（0x12345678）+ 0x50 SPH + 指令」。
  「少 SPH 会抛 `IndexOutOfRangeException`」的真正原因是**整段 SPH 都缺**。
- **SPH 的字段**（20 个 u32，按 `ShaderHeader.cs` 逐位解）：第 0 字 = sphType(0..4) / version(5..9) /
  **stage(10..13)** / mrt(14) / killsPixels(15) / doesGlobalStore(16) / sassVersion(17..20) / gpPassthrough(24) /
  doesLoadOrStore(26) / **doesFp64(27)** / streamOutMask(28..31)；第 1..4 字 = 局部内存大小 / perPatchAttributeCount /
  threadsPerInputPrimitive / CRS 大小 / outputTopology / maxOutputVertexCount / storeReqStart / storeReqEnd；
  **第 6..13 字 = ImapTypes[32]**（顶点属性的输入映射类型，每字 4 个属性、每属性 2 bit × 4 分量）；
  **第 18 字 = OmapTargets（片元输出数）**；第 19 字 = omap 标志位。
- **9,807 个着色器全量校验通过**：SPH 全部解析成功，**stage 字段与归档里的 kind 100% 一致**
  （idx=vs / sph=1：4,232；idx=ps / sph=5：5,557；idx=cs：18），word0 只有 21 种取值且全部落在合法字段组合内
  （例如 `0x02060461` = sphType 1 / version 3 / stage 1 / sass 3）。
  勘察表在 `D:\Switch\totk-work\probe\sph\sph.tsv`（含每个键的 SPH 全字段与控制头的全部非零字）。
- **SPH 里没有贴图维度类型、也没有图像格式**：NVN 着色器控制头（魔数 0x98761234、长度 0x880）里同样
  **没有按槽的描述符表** —— 9,807 个控制头只有 **86 种固定布局**，非零字集中在 0x0000 / 0x0014 / 0x0020 /
  0x06f0 / 0x06f8 / 0x0700 / 0x0790 / 0x07d0 / 0x07f4 / 0x0804 等固定位置，与该着色器用到的资源槽数无关。
  → D2R 那张「PC 反射冻结」的 `tex` / `img` 事实**在 TotK 侧没有静态对应物**。
- **贴图维度多半本来就不需要事实表**（这是本条目最重要的结论之一）：Ryujinx 自己的翻译器就是**从机器码的贴图指令取维度**
  的 —— `Instructions/InstEmitTexture.cs` 的 `ConvertSamplerType(TexDim)`：TEX / TLD / TLD4 / TMML / TXD 用第 28..30 位的
  `Dim`，TEXS / TLDS 用第 53..56 位的 `Target`（`TexsTarget` / `TldsTarget`）。
  我们用事实表作答的 `IGpuAccessor.QuerySamplerType` **只在三处被调用**：① 纹理查询 TXQ ② buffer 型贴图判定
  ③ bindless 路径（全仓 grep 只有 `InstEmitTexture.cs` 三处 + `BindlessElimination.cs` 一处）。
  实测：TotK 9,807 个着色器里**只有 26 个用 TXQ**（其中 12 个的贴图维度不是 2D）；**没有 1D / buffer 贴图**
  （维度分布 2d 39,210 / 2darray 4,752 / 3d 3,205 / cube 1,482 / 2ds 2；**同一槽出现两种维度的 0 个**，反证解码正确）。
  → **按缺省（2D）译出来的着色器库，贴图维度本来就是对的**；「贴图维度」从「必须拿到的事实」降级为「只有 TXQ 着色器需要」。
- **真正的新事实是顶点属性的分量类型**：`ImapTypes[i].X == Constant(1)` = 整数属性（Perspective=2 / ScreenLinear=3 = 浮点）。
  TotK 实测：**4,206 个顶点着色器有属性事实，其中 1,204 个属性槽是整数属性**
  （D2R 侧 PC 反射给的比例是 870/11,166 ≈ 7.8%，量级一致）。这条事实之前一直按缺省 float 作答。
  片元阶段的 ImapTypes 描述的是插值输入、计算阶段没有 SPH，都不取。
- **重译与比对（证据链）**：4,778 个受影响键（3,652 个只改贴图事实、1,126 个只改属性事实）用新事实表重译，
  **4,778 成功 / 0 失败**；与上一版逐字节比对：**267 个键的 SPIR-V 变了，4,511 个逐字节相同**。
  变的 267 个**全部**带属性事实（带贴图事实但没变的 6,787 个，反证贴图事实确实不进 SPIR-V）。
  抽样 `002d9a7925fc2af1`（属性 6 = 整数）：新版 SPIR-V 多出 `OpTypeVector(uvec4)`（分量类型是 32 位**无符号** int），
  旧版只有 float4 —— 属性分量类型确实按 SPH 改了。
  顺带解释「为什么 1,126 个带属性事实的键里只变了 267 个」：SPH 的 ImapTypes 覆盖 32 个属性号，
  多数键声明的属性并没有真被这个着色器用上，所以声明不变。
- **★ 头号拦路虎（NA-034 的由来）**：**TotK 与 D2R 的 c[2] 驱动常量段布局不同**。
  D2R 用**分离**贴图：句柄在 `c[2][0x168 + 8r]`（贴图槽）与 `c[2][0x568 + 8r]`（采样器槽），各 128 槽；
  图像句柄在 `c[2][0x120 + 8r]`（8 槽）—— 这三个值是 `dm/gfx/tools/dmsh_build.py` 全量实测出来的。
  **TotK 用合并句柄**（handle type = 0：纹理 ID 低 20 位 + 采样器 ID 第 20..31 位）：
  实测 9,807 个着色器里全部贴图引用的 c[2] 字节偏移都落在 **`0x20 + 8r`，r = 0..31**
  （偏移集合 0x20、0x28 … 0x118 共 32 个，干净的 8 字节步进，没有一个越界；0x120 正好是图像句柄表的起点，
  与 D2R 侧一致，所以合并贴图表 = `c[2][0x20 .. 0x120)`）。
  宿主现状：`dm/android/native/nvn_vulkan_shader.inc` 把贴图句柄写在 `0x168 + 8i`，
  `dm/android/native/nvn_vulkan_handles.inc` 的 `shader_handle_word()` 只认 `0x168..0x568` / `0x568..0x968` /
  `0x120..0x168` 三段 → **TotK 的贴图句柄偏移全部落在三段之外，读出来是 0：一个贴图都绑不上，画面必然是黑的**。
  翻译器侧同理：`dm/gfx/tools/dmsh_xlate/Program.cs` 的 `TexSlot()` 用死值 `TexBase = 0x168`，
  事实表里的贴图维度因此查不到（这也是那 12 个 TXQ 键的 SPIR-V 至今没变的原因）。
- **事实表不进仓库**：仓库纪律是「游戏内容与由它生成的表不进仓库」。新工具 `dm/gfx/tools/totk_facts.py` 入仓，
  表落仓库外（`D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv`）。
- **本会话的一次操作错误（已改）**：第一次重译用的是 `dm/gfx/tools/dmsh_xlate/obj/Release/net10.0/dmsh_xlate.dll`
  （缺 `dmsh_xlate.runtimeconfig.json`），6 个分片全部退出码 2147516547；换成上次成功的构建输出
  `D:\Switch\totk-work\tools\xlate\dmsh_xlate.dll` + `D:\Switch\totk-work\tools\dotnet\dotnet.exe` 即通过。
- 下一步：**NA-034** —— 把 c[2] 布局做成按规则集可选，宿主与翻译器两侧一起改（D2R 路径逐字节不变）。

## 2026-10-20 18:45 Asia/Shanghai — [TOTK] NA-032 收口：9,807 个着色器全部翻成 SPIR-V

- 会话目标：把 NA-032 收口 —— 翻译作业流水线入仓、**全部 9,807 个 TotK 着色器翻成 SPIR-V**、把那 3 个 `IndexOutOfRangeException` 查因修掉；顺手把一加 12 接入的实况写进快照。
- 结果：**9,807/9,807 成功、0 失败**（SPIR-V 539,816,056 字节，`res.json` 9,807 个）。根因是**漏了图形机器码开头 0x30 字节的 SPH（描述符头）**，补上后那 3 个就全过了。
- 用户新给的信息：一加 12 已接上电脑（`3b864e51` / PJD110 / Android 16 / 骁龙 8 Gen 3 / Adreno 750）。

[BEGIN] na-032-totk-shaders-full

- 命令：
  1. `D:\Switch\.tools\venv\Scripts\python.exe dm\gfx\tools\totk_xlate.py --index D:\Switch\totk-work\shaders-index4\shader_index.tsv --code D:\Switch\totk-work\shaders-index4\code --work D:\Switch\totk-work\xlate-full --write-facts D:\Switch\totk-work\xlate-full\shader_facts_totk.tsv --xlate D:\Switch\totk-work\tools\xlate\dmsh_xlate.dll --dotnet D:\Switch\totk-work\tools\dotnet10\dotnet.exe --shards 6`
  2. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\ci_checks.py`
  3. `D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b28`
  4. `D:\Switch\.tools\venv\Scripts\python.exe tools\agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work\xlate-full`）
- 预期结果：9,807 个键全部产出 SPIR-V；ci_checks 10 通过 / 0 失败；build exit 0；--verify exit 0。
- 日志路径：`D:\Switch\totk-work\xlate-full\run.log`（翻译）、`D:\Switch\totk-work\build-trim-b28b.log`（构建）
- 回滚点：`04ca834`（NA-032 业务提交）

[END] na-032-totk-shaders-full

- 退出码：翻译 exit 0（9,807 成功 / 0 失败）；`ci_checks.py` 10 通过 / 0 失败；`build.py --game-run --version trim-b28` exit 0（APK 17,725,903 字节）；`agent_handoff_check.py --verify` exit 0。
- 产物：`D:\Switch\totk-work\xlate-full\out0..5\<键>.spv`（9,807 个，539,816,056 字节）+ 同名 `.res.json`（9,807 个）+ `xlate_report.tsv`（全 OK）+ `shader_facts_totk.tsv`（18 个计算着色器有事实，**在仓库外**）；仓库内新增 `dm/gfx/tools/totk_xlate.py`（提交 `04ca834`）；APK `dm/android/build/D2R-Android-port.apk`（trim-b28，17,725,903 字节）。
- 结果：SUCCESS
- 备注：**真机上的实际出图与进 `nnMain` 本批 NOT RUN**（一加 12 已接、启动器界面能渲染、驱动能切「内置 Turnip」，但还没装 TotK 数据、没跑起来）；iOS / macOS 侧编译 NOT RUN（Mac 侧还需重建翻译器并跑 `dmsh_chain.py --update-lock` 更新源码指纹）。

证据（本条目对应的命令与退出码）：

- **根因（重要，会影响后续所有 TotK 作业）**：先前那 3 个 `IndexOutOfRangeException` 的着色器（`468d6df7ca6c665b` / `702947f3fa3e3a19` / `edcccc039d2a46e2`，都是 `AglShader.sharcb` 的 ps，机器码 208 字节、c1 0 字节）**不是翻译器的 bug，是喂进去的机器码少了 SPH**。复现与修复（同一批作业，只换 `code` 字段）：
  - 去掉 0x30 字节 SPH：`翻译 0 成功，3 失败`（`【红】…：IndexOutOfRangeException`），exit 1；
  - 带上 SPH（用 `totk_shaders.py` 产出的原始机器码）：`翻译 3 成功，0 失败`，exit 0。
  机制：D2R 侧早就写着同一条规则 —— `dm/gfx/tools/dmsh_build.py` 里图形着色器取 `code = code[0x30:]`（丢掉的是**记录头**，留下的是 **SPH + 指令**）。TotK 的机器码区前 0x30 字节同样是 SPH，之前临时造作业时被剥掉了。**教训（写进工具注释）**：TotK 的作业必须直接指向 `totk_shaders.py` 产出的 `code/<键>.bin`，不要自己裁字节。
- **全量结果**：6 分片并行，每片 1,634~1,635 个作业，**全部成功**；总耗时约 55 分钟（实测速率约 180 键/分）。校验脚本逐个读回 9,807 个 `.spv` 的魔数，**9,807 个都是 `0x07230203`（合法 SPIR-V）、0 个坏**；`xlate_report.tsv` 里 9,807 行全 `OK`。
- **SPH 的原始线索（留给 NA-033）**：机器码前 12 个 u32（`0001473d92450068` = vs，3792 字节）：`02060461 00000000 00000000 00000000 00000000 00000000 00000f77 000c0033 00000000 00000000 00000000 00000000`；`00309da9bcb0135f`（vs）：`06060461 … 00003f77 00000003 …`；`fd32c9058c6375cd`（54,992 字节）：`06060461 00000600 … ffff0077 000f3333 …`；此前失败的 `468d6df7ca6c665b` / `edcccc039d2a46e2`：`00065462 … 80000000 0000000f …`（word6 的 `0x80000000` 像个「无描述符」标志）。**SPH 至今没有被解析过**，里面有没有贴图维度 / 图像格式 / 属性类型就是 NA-033 要查的。
- **事实表（方案 A）**：18 个计算着色器的线程组与共享内存来自控制头 0x748（64x1x1、8x8x1、1x1x1；共享内存 0 / 2048 字节），写进 `D:\Switch\totk-work\xlate-full\shader_facts_totk.tsv`（格式与 `dm/gfx/nvn/shader_facts.tsv` 同：键 <TAB> JSON）；其余 9,789 个键的贴图维度 / 图像格式 / 属性类型**按缺省作答**（2D / R8G8B8A8Unorm / float），报告里单列。**事实表不进仓库**（仓库纪律：游戏内容与由它生成的表不进仓库），仓库里只留工具 `dm/gfx/tools/totk_xlate.py`。
- **真机**：一加 12 在本会话开始时已接上（`adb devices` → `3b864e51 device PJD110`，Android 16）；**本会话收尾时 `adb devices` 已看不到设备**（应该是被拔了），新会话第一步先确认手机在不在。`trim-b27` 已装（`org.d2r.android.port`），启动器界面正常渲染（截图 `D:\Switch\totk-work\device\launcher2.png`），「驱动」一行能切到「内置 Turnip」。**但内置 Turnip 的可用性仍未验证**：仓库内置的 `dm/android/prebuilt/turnip/vulkan.purple.so` 是 **T30/Adreno 830** 构建，而本机解析该 `.so` 的 `.dynsym` **没有任何 `vk*` 导出**（只有 `tu_*` 模板与 libc 符号），宿主 `dm/android/native/gpu_driver.c` 却是 `dlsym(driver, "vkGetInstanceProcAddr")` 取入口 —— 加载方式（ICD 私有入口 / 另配 wrapper / 与 APK 内实际打包的不是同一份）要查清，这属于计划 §4.5 的驱动选型，列为下一步之后的第 ① 项。
- **本会话的一个操作决定**：本体 RomFS 全量解包（后台 python，pid 3312，已解到约 24 万个文件）**被本会话暂停**以让出磁盘 I/O 给翻译与构建；`switch_nca.py romfs-extract` 支持断点续跑，新会话可继续。
- 下一步：**NA-033** —— 解析 SPH，把「贴图维度 / 图像格式 / 属性类型」这层事实坐实（或按方案 A 收口），把结论写进计划 §4.4。

## 2026-10-20 09:20 Asia/Shanghai — [TOTK] NA-030 TotK 模块进 Android 装载链

- 会话目标：把 TotK 的三个模块接进 Android 宿主的装载链，并在本机用宿主同款解析核对（M1 第一步，不碰图形）。
- 结果：改写 → ELF 库 → 宿主同款解析三步都跑通；**跨模块未解析只剩 9 个符号，且全是 `glslc*`**（NVIDIA 运行时 GLSL 编译器 API）——宿主的未实现桩能兜住，不挡装载。

[BEGIN] na-030-totk-modules

- 命令：`DM_RULESET=totk-run-v1 DM_TARGET=android python dm/tools/patch_nso.py <ExeFS/模块> <work> <模块名>`（四个模块各一次）→ `python dm/android/tools/guest_elf.py <work> <work> main sdk subsdk0` → 用 `dm/android/tools/totk_modules.py` 照 `dm/android/native/game_modules.c` 的 `parse()` 复刻宿主解析。
- 工作目录：`D:\Switch\d2r-android`（产物落在仓库外 `D:\Switch\totk-work`）
- 预期结果：三个模块库产出、宿主解析读出符号 / 重定位 / 导入数、未解析导入清单拿到。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`e3c7dbc`

[END] na-030-totk-modules

- 退出码：四个模块的 Android 上下文改写全部 exit 0；`guest_elf.py` exit 0；`totk_modules.py` exit 0。
- 产物：`D:\Switch\totk-work\patched-android\`（改写映像 + 布局表 + `.target` = `android-context-v1`）与 `D:\Switch\totk-work\guest-so\libdmguest_{main,sdk,subsdk0}.so`（61,817,600 / 13,009,664 / 6,767,368 字节）；仓库内新增 `dm/android/tools/totk_modules.py`（提交 `bd3d0b7`）。
- 结果：SUCCESS
- 备注：**真机上的实际装载与进 `nnMain` 本批 NOT RUN**（一加 12 未接，`adb devices` 无设备）；iOS / macOS 侧编译 NOT RUN。

证据（本条目对应的命令与退出码）：

- 改写结果（Android 上下文，与苹果上下文的差别只在 `thread_base()` 走宿主上下文入口）：`main {'tpidr_r': 814} cuts 0 obs 0 patch 52096`；`sdk {'tpidr_r': 2, 'tpidrro_r': 124, 'tpidr_w': 3, 'cntpct': 43, 'svc': 58} cuts 0 obs 0`（门 101）；`subsdk0 {} cuts 0 obs 0`；`rtld {'svc': 6} cuts 0 obs 0`（门 6）。
- 宿主同款解析（`game_modules.c` 的 `parse()` 复刻，作用在同一批 `.so` 的 `.image` 段上）：main 符号 706 / 重定位 2,070（RELA 1,421 + PLT 649）/ 导入 680；sdk 23,039 / 19,027（11,214 + 7,813）/ 9；subsdk0 10,110 / 15,648（11,832 + 3,816）/ 664；**合计 33,855 符号 / 36,745 重定位 / 1,353 导入**（与 NA-027 的离线统计 33,858 / 36,747 / 1,356 的差是宿主公式 `(STRTAB-SYMTAB)/24` 与 DT_HASH nchain 对空符号的计数差 1~3，可解释）。
- **跨模块未解析的导入 9 个**（来自 main）：`glslcCompile`、`glslcCompilePreSpecialized`、`glslcCompileSpecialized`、`glslcFinalize`、`glslcGetDefaultOptions`、`glslcGetVersion`、`glslcInitialize`、`glslcSetAllocator`（另有一个空名符号）。这是 NVIDIA 的运行时 GLSL 编译器 API —— **D2R 没有这个需求**，是 TotK 特有的。若游戏真去调用它们，宿主的「未实现桩」会命中（`dm/host/hle.c` 的 `resolve_import` → STUB），真机上用 `DM_HLECOUNT` 能看出调用次数；这是 §4.4 着色器事实表的一个旁证（TotK 侧存在运行时 GLSL 编译路径的痕迹，但主流程用的是预编译包 `*.bfsha.zs`）。
- 新增工具 `dm/android/tools/totk_modules.py`：一条命令跑完「改写 → 打包 ELF 库 → 宿主同款解析 → 未解析导入清单」，`--reuse` 可复用已有改写产物；游戏文件与密钥只在本机读，产物在仓库外。
- 下一步：NA-031 —— 把「用哪套模块」接到规则域（D2R 用包内 `game/`，TotK 用仓库外的 `guest-so/`），并把 TotK 的 `game/` 目录形态与 `make_package.py` / `build_package.py` 对齐，使真机装载这条路在没有设备时也能在宿主侧离线核对。

## 2026-10-20 10:10 Asia/Shanghai — [TOTK] NA-031 模块来源接规则域 + NA-032 §4.4 着色器事实表来源

- 会话目标：把「用哪套模块」接到规则域上（打包链参数化），并把 §4.4 的着色器事实表来源查清（用户提供了外部项目 `catoncat/d2r-port-radar` 雷达，顺着它找到一个**已经能跑 TotK 的移植** `OJZen/totk-mobile`）。
- 两条结论：① 宿主的服务面几乎不用改 —— TotK 三模块的未定义导入里，宿主 HLE 表已覆盖 66 个，**真正缺的只有 8 个 `glslc*`**，而宿主的未实现桩是良性的；② **§4.4 的 go/no-go 风险基本解除** —— 任天堂的 zstd 字典就在游戏自己的 `/Pack/ZsDic.pack.zs` 里，着色器归档能解开，且归档里带反射元数据字符串。

[BEGIN] na-031-modules-and-shaders

- 命令：`make_package.py --ruleset totk-run-v1 --exefs <目录> --modules-only`（TotK 模块）；`switch_shaders.py <RomFS> <输出>`（着色器归档）；HLE 缺口普查脚本（导入符号 × 宿主 HLE 表）；svc 号与宿主 case 的对照（名字取自 Ryujinx 的 `[Svc(0x..)]` 枚举）。
- 工作目录：`D:\Switch\d2r-android`（游戏文件与产物都在仓库外 `D:\Switch\totk-work`）
- 预期结果：TotK 模块能走官方打包链出包；着色器归档能解；HLE 缺口有清单。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`124b315`

[END] na-031-modules-and-shaders

- 退出码：`make_package.py ... --modules-only` exit 0；`switch_shaders.py` exit 0（30 个文件 + `manifest.json`）；`ci_checks.py` 10 项通过 / 0 项失败；`agent_handoff_check.py --verify` exit 0。
- 产物：提交 `48f5d1f`（打包链参数化 + 解包并发读修复）、`944681d`（`dm/tools/switch_shaders.py`）；仓库外 `D:\Switch\totk-work\pack-totk\produce\game\`（三个 `libdmguest_*.so` + 布局表）、`D:\Switch\totk-work\shaders-out\`（着色器归档与清单）。
- 结果：SUCCESS
- 备注：真机出图 NOT RUN（一加 12 未接）；iOS / macOS 侧编译 NOT RUN。

证据（本条目对应的命令与退出码）：

- **外部资源**（用户指出后跟进的）：`catoncat/d2r-port-radar`（移植雷达 + 知识库，机器可读接口 `api/*.json`）里收录了一个**已经能读档游玩的 TotK 移植** `OJZen/totk-mobile`（Mac/iOS，v1.4.3，Apache-2.0，内核是 d2r-mobile 的 MIT 部分）。它印证了三件我们正在踩的事：① 他们的 `script/extract_romfs.py` 走的也是「NCA → hactool `--basenca` 合并 RomFS」；② 他们的 `script/extract_shaders.py` 写着「字典从 `/Pack/ZsDic.pack.zs` 取」；③ 他们的知识库里 `gen-0001` 记着「宿主把 ProgramId 写死成 D2R 的 titleId」、`gen-0002` 记着「svc 0x1F/0x21/0x22（IPC 收发）静默回成功、不写回复」—— 后者正是我们缺的 #31/#33/#34。**许可**：他们的代码是 Apache-2.0，本仓库是 MIT，**只读思路与格式事实，代码自己写**；Ryujinx（MIT）可以按其声明使用。
- **HLE 缺口普查**：TotK 三模块（main / sdk / subsdk0）未定义导入 1,266 个 → 宿主 HLE_FORCE 表（173 条）覆盖 66 个 → 真正缺 8 个，全是 NVIDIA GLSL 编译器 API：`glslcInitialize` / `glslcCompile` / `glslcCompilePreSpecialized` / `glslcCompileSpecialized` / `glslcFinalize` / `glslcGetDefaultOptions` / `glslcGetVersion` / `glslcSetAllocator`（D2R 没有这个需求）。宿主的「未实现导入」桩是良性的（`dm/host/hle.c` 的 `unimpl_c` 记一次日志、返回 0，不中止），所以**符号层不需要改宿主**；真机上用 `DM_HLECOUNT` 看它们有没有被调用。
- **svc 面对照**：TotK 的 58 个 svc 号里，宿主 `hle_*.c` 有 case 的 34 个；**没有 case 的 24 个**是 #19 MapSharedMemory、#20 UnmapSharedMemory、#21 CreateTransferMemory、#31 ConnectToNamedPort、#33 SendSyncRequest、#34 SendSyncRequestWithUserBuffer、#35 SendAsyncRequestWithUserBuffer、#50 SetThreadActivity、#51 GetThreadContext3、#54 SynchronizePreemptionState、#64 CreateSession、#65 AcceptSession、#67 ReplyAndReceive、#68 ReplyAndReceiveWithUserBuffer、#75 CreateCodeMemory、#81 MapTransferMemory、#82 UnmapTransferMemory、#112 CreatePort、#114 ConnectToPort 等（名字取自 Ryujinx 的 `[Svc(0x..)]` 枚举）。它们多是 Horizon IPC，而 D2R 宿主直接接管**服务客户端函数**，所以真机上的实际缺口预计远小于 24 个。
- **打包链接规则域**：`make_package.py` 新增 `--ruleset` / `--exefs` / `--modules-only`；TotK 一条命令 exit 0，`game/` 目录里是三个 `libdmguest_*.so` 与 `{name}.fixups/gates.tsv`（正是数据包要的形态）；D2R 默认路径（`touch-run-v4`）一字未变。
- **着色器事实表来源（§4.4）**：`/Pack/ZsDic.pack.zs`（108,344 字节）解开是 SARC，里面 3 份 128 KB zstd 字典（`zs.zsdic` id=1、`bcett.byml.zsdic` id=2、`pack.zsdic` id=3）；着色器包的 zstd 帧头写明自己要 id=1（此前一律报 `Dictionary mismatch`）。用字典解开：`ApplicationPackage.Nin_NX_NVN.release.sarc.zs` → 8,840,872 字节 SARC（19 个条目，如 `GrassShader.sharcb` 69,632 字节、`AglShader.sharcb` 794,624 字节）；12 个 `*.bfsha.zs` → FSHA 容器（`material...` 解出 101,165,712 字节）。条目里带 `cTexSrc`、`gl_InstanceID`、`grass_shader` 等**反射元数据字符串** → D2R 那条「从 PC 版反射冻结事实表」的路对 TotK 不成立，但**从游戏自带归档取**成立（方案 D 可行）。
- 顺带修掉一个自造 bug：`switch_nca.py romfs-extract` 之前多线程共用一个文件句柄，seek/read 会串台（读出坏数据、进程卡死）。改为每线程一个句柄并加读满校验；旧的产物不可信，已解到新目录重解（后台仍在跑）。
- **外部参考（`OJZen/totk-mobile` 的内核）**：它的 `core/tools/patch_nso.py` 其实是 d2r-mobile 的原版改写器（未为 TotK 改），TotK 的适配全在它自己的 `tools/patch_module.py` + `tools/exclusive.py` 里，做法是：① `DM_RULESET=native`（TotK 不带 D2R 剪口，并显式拒绝任何 cuts/obs/params 条目）✓ 与我们的结论一致；② **保留 x18 改写**，但把「独占窗口」改成**多入口**（一个 LL/SC 区域可以有多个 load 入口共享一个 store，每个入口各带一段序言；外部跳进区域中间的路径也要有入口），这正是我们 v1.4.2 上撞到 `branch into window` 时的正解；③ 额外处理 **`blr x18`**（TotK 用 x18 当函数指针调用）；④ 跳转表是**有符号**的（v1.4.3 的 5 张表按地址写死，v1.4.2 要自己定位）。它的 v1.4.3 main 构建号 `277178b7dba1b6d4949a84778d4abc58`可与我们 v1.4.2 的 `5cb42b1c…` 对照。**许可**：它是 Apache-2.0，本仓库是 MIT —— 只读思路与格式事实，代码自己写。
- **NA-032 的第一半（`a25ccc3`）**：按确认的格式自己写了 `dm/gfx/tools/totk_shaders.py`（BNSH / FSHA / BAHS v9）：逐着色器解出控制头（魔数 0x98761234、minor 9/16、长 0x880）、机器码与 C1，算出着色器键 `sha256(control+program+c1)[:16]`（与既有事实表同格式 ✓）与阶段（vs/ps/gs/hs/ds/cs）。实测 `/Shader` 归档：**49,089 条记录 → 9,807 个唯一键**（cs 18 / ps 5,557 / vs 4,232），**计算着色器的线程组与共享内存就在控制头 0x748 处**（实测 64x1x1 / 8x8x1 / 1x1x1，共享内存 0 / 2048 字节）→ 这类事实不需要 PC 反射，TotK 侧直接可得，**§4.4 的风险进一步解除**。贴图维度 / 图像格式 / 属性分量类型的位置还没定位（C1 块很小，多半在控制头的描述符表）。
- **NA-032 剩下的一半的实测结论**：贴图维度 / 图像格式 / 属性分量类型**不在着色器里** —— 抽查 4 个归档的 vs / ps，控制头（0x880 字节）只有 15–33 个非零字、**没有描述符表**，C1 块也只有 0–64 字节；这几项事实只能来自**游戏的数据**（材质 / 图形数据）或**运行期观测**（方案 B），而计算着色器的线程组与共享内存是唯一能从着色器直接拿到的一类 ✓。好消息：我们的翻译链 `dm/gfx/tools/dmsh_xlate/`（MIT）本来就按作业里的 `tex` / `img` / `attr` / `fout` / `local` / `c1` 作答，**缺项按缺省**（2D / R8G8B8A8Unorm / float），输出口径是 **SPIR-V（Vulkan）** —— 正是 Android 侧要的东西，也正是方案 A 的落点；`csproj` 目标 `net10.0`（本机 .NET 8 覆盖目标框架会报 NETSDK1045），已下载 Windows 版 .NET 10.0.401 SDK（300,608,304 字节）到仓库外工作区。
- **路线已验证（本机）**：装 .NET 10.0.401 SDK（Windows x64，300,608,304 字节，仓库外工作区）→ `dotnet build dm/gfx/tools/dmsh_xlate/dmsh_xlate.csproj -c Release` exit 0（15 分 9 秒，0 警告 0 错误）→ 用 TotK 的键 + 机器码 + c1 造作业翻译：**单个「翻译 1 成功，0 失败」**（1,860 字节 SPIR-V），**批量 200 个作业「翻译 190 成功，10 失败」**（去重后 126 个唯一键里只有 3 个失败，翻译器内部 `IndexOutOfRangeException`）。翻译器已做三处**作业驱动**的 TotK 适配：深度范围 -1..1（作业 `depth_minus_one_to_one`）、宿主不支持 fp64 / 深度裁剪控制（作业 `host_no_fp64` / `host_no_depth_clip`）、顶点→像素联编（作业 `next.code`）；D2R 行为一字未变（缺省即原值）。**注意**：改 `Program.cs` 后翻译器源码指纹变了，Mac 侧要重建一次并跑 `dm/gfx/tools/dmsh_chain.py --update-lock`（D2R 产物不变，只更新锁里的源码指纹）。另修了自己一个解析错误：c1 长度是 `0x704 - 0x700`，此前「C1 只有几字节」是假象（真实 256 字节）。
- 下一步：NA-033 —— 用 `dm/gfx/tools/totk_shaders.py` 的索引给全部 9,807 个键造作业并全量翻译成 SPIR-V，逐个查那类失败；之后再做改写器的 x18 适配（多入口独占窗口 + `blr x18`）。

## 2026-10-20 08:30 Asia/Shanghai — [TOTK] NA-028 规则域接 TotK + NA-029 上游同步完成

- 会话目标：把 `patch_nso.py` 的 `totk-run-v1` 规则域接到 TotK 真实构建号并跑出第一份 TotK 改写映像与宿主门清单；按用户要求核对上游仓库的更新与 issue，判断对本项目有没有用，并把这条规则写进 AGENTS.md。
- 结论：**TotK 规则域已可用**（四个模块改写全部 exit 0，cuts/obs 全 0，宿主门面清单拿到）；**宿主侧不需要为 TotK 改 x18 处理**（Android 宿主本来就保全 x18，Linux ABI 也不用 x18）。

[BEGIN] na-028-totk-ruleset

- 命令：`DM_RULESET=totk-run-v1 python dm/tools/patch_nso.py <ExeFS/模块> <输出目录> <模块名>`（四个模块各一次），随后 `ci_checks.py`、`build.py --game-run --version trim-b26`。
- 工作目录：`D:\Switch\d2r-android`（改写产物落在仓库外 `D:\Switch\totk-work\patched`）
- 预期结果：构建号断言通过、cuts/obs 为空、产出改写映像与门清单。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`becd40b`

[END] na-028-totk-ruleset

- 退出码：四个模块的改写全部 exit 0；`ci_checks.py` 10 项通过 / 0 项失败；`build.py --game-run --version trim-b26` exit 0（APK 17,725,903 字节）。
- 产物：`D:\Switch\totk-work\patched\{main,sdk,subsdk0,rtld}.{patched.bin,gates.tsv,sites.tsv,fixups.tsv,cuts.tsv,obs.tsv,params.tsv}`
- 结果：SUCCESS
- 备注：iOS / macOS 侧编译与真机（本批 NOT RUN）；更新包 BKTR 补丁应用 NOT RUN。

证据（本条目对应的命令与退出码）：

- 规则域改动（提交 `a70f0ef`）：`TOTK_BUILDS` 钉住四个模块构建号（main `5cb42b1cf25469fb0635fd046453d843`、sdk `5cf080e800530a7f25bd528ec875c27b`、subsdk0 `3308c1d216f788397d1451c8345a16cd`、rtld `82a3cf78789f9d9858c52379d8d2d129`），构建号不符即中止；CUTS / OBS / PARAMS 三张表给 TotK 的 main 登记空表。
- 改写结果：`main {'tpidr_r': 814} cuts 0 obs 0 patch 26048`（61,760,960 字节）；`sdk {'tpidr_r': 2, 'tpidrro_r': 124, 'tpidr_w': 3, 'cntpct': 43, 'svc': 58} cuts 0 obs 0`（12,984,320 字节，门 101 个）；`subsdk0 {} cuts 0 obs 0`（6,750,208 字节）；`rtld {'svc': 6} cuts 0 obs 0`（66,136 字节，门 6 个）。
- 宿主门面清单：sdk 的 58 个不同 svc 号 = 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,31,33,34,35,37,38,39,40,41,42,44,45,47,50,51,52,53,54,64,65,67,68,69,75,80,81,82,112,114（rtld 的 6 个是其中子集）→ 这就是「TotK 实际触发的 syscall 号」的缺口清单（对比 D2R 的 264 处强制接管，量级小得多）。
- **M1 前提修正（重要）**：改写器第一次跑 TotK 的 main 报 `AssertionError: branch into window a79c0`。查清后根因不是窗口逻辑，而是 **TotK 把 x18 当普通寄存器用**：.text 里 24,204 条指令提到 x18、18,572 条提到 w18（例如 0x3f00 `add x18, x19, #0x260`、0xa761c `stxr w17, w18, [x10]`、0xa79c0 `b.eq #0xa761c` 跳进独占窗口中间），而 D2R 改写器的前提是「x18 = TLS 指针」。实测结论：上游那套机制的实质是**每线程把客体 x18 存进线程槽 K18**，对「x18 是普通寄存器」同样成立；而 Android 宿主本来就保全 x18（`dm/android/native/probe.c` 每次宿主调用前后都比对 x18，Linux AArch64 ABI 也不用 x18）——所以 TotK 规则域**不做 x18 改写**即可，**宿主侧不用改**，D2R 行为一字未动。
- 未采纳的 D2R 侧改动：批 6 剩余的 D2R CUTS/OBS 表、`casc_overlay.py`、iOS 资产管线仍在队列里（注意 `dm/android/tools/build_shaders.py` 还 import `casc_overlay`，删它要一并改）。

[BEGIN] na-029-upstream-sync

- 命令：拉上游 `jhaizhou-ops/d2r-mobile` 的 `main` 与本地 `dm/tools/patch_nso.py` 比对；检索上游 issue（`x18` / `TLS` / `svc` / `gate` / `thread` / `context`）；采纳 #55 的预筛后跑 `dm/android/tests/test_rewriter.py` 与 TotK 上的独立复核脚本。
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：找出上游对本项目有用的更新并采纳，写清「有没有用、为什么」；把「上游有更新要同步并评估」写进 AGENTS.md。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`a70f0effedd4cf9ad1d69e699935dc936c65235a`

[END] na-029-upstream-sync

- 退出码：`dm/android/tests/test_rewriter.py` exit 0（unicorn 逐条比对原指令与改写后语义，8 个用例：算术 / 条件 / 位测 / 标志 / PC 相对 / 栈 / 原子（ldxr·stxr 独占窗口）/ TLS）；TotK main 上的独立复核脚本 exit 0（漏 0、多 0）。
- 产物：提交 `e3c7dbc`（`dm/tools/patch_nso.py` 的预筛 + `dm/tools/switch_nca.py` 的断点续传）。
- 结果：SUCCESS
- 备注：上游差异的三类归属与逐条「有用 / 没用」的判断见下方证据；本批 NOT RUN：iOS / macOS 侧编译、真机。

证据（本条目对应的命令与退出码）：

- 上游现状：`jhaizhou-ops/d2r-mobile` 的 `main` 比本 fork 新 —— 其 `dm/tools/patch_nso.py` 88,578 字节 vs 我们 72,377（283 行差异）。差异分三类：① D2R 玩法剪口（我们的裁剪批次 7a–7s 已删，属预期差异）② Android 宿主改造（`DM_TARGET=android`、`thread_base()` 走宿主上下文入口等，我们独有）③ **可直接用的上游改进**。
- 采纳：上游 issue **#55「Speed up NSO x18 scan with register field prefilter」** —— 线性扫描时先看指令的四个寄存器字段（0/5/10/16 位）有没有 18，命中才反汇编。上游口径：候选 7,201,192 → 189,399，三个模块一趟 78.5s → 20.2s。语义不变（产物逐字节相同）。
- 本批独立验证（不靠上游的数据）：① 按上游同一口径在 **TotK 的 main** 上复核 —— 11,442,300 字 → 322,813 候选（2.82%）→ 42,776 处 x18/w18，**漏 0、多 0**；② 仓库自带的改写器等价性单测 `dm/android/tests/test_rewriter.py` **exit 0**（含 ldxr/stxr 独占窗口用例）。注：该单测首次运行报 `FileNotFoundError`，原因是本机没设 `DM_ANDROID_TOOLS`（脚本按 `~/dm-work/tools/android` 找工具链），设上环境变量即通过 —— 不是代码问题。
- 未采纳（逐条理由）：上游「In-game Spanish（esES / esMX）语言开关 / 界面文字 / 物品注释 / 三语 README」是 D2R 产品侧（且我们刚在 NA-025 摘掉 D2R 的自定义页语言开关，TotK 侧语言策略是「一律简中」）；「Adopt community fixes：Mac 悬停提示 / Mac 物品注释与自动增益 / Mac iCloud 启动 / iOS 快速操作 / Xcode 26.2 / 主按钮瞄准死区」全是 D2R 宿主体验项；「fix(loader): preserve null unresolved weak imports (#66)」是 loader 细节，TotK 走的是自己的模块链，暂不引入；「Mac shader retarget：按目录拷贝反射 JSON 并逐库校验（#60）」与 §4.4 相关，**列入待查**（TotK 的反射来源还没定，暂不照搬 D2R 的做法）。
- 新增规则：`AGENTS.md` 第 11 条「**上游有更新要同步，并判断对本项目是否有用**」—— 写明上游仓库、共同祖先、只取有用部分、不整文件覆盖、结论写进本日志。

## 2026-10-20 06:40 Asia/Shanghai — [TOTK] NA-027 TotK 文件准备 + M0 勘察完成

- 会话目标：用户提供了 TotK v1.4.2 合并 XCI 与 `prod.keys`，按计划 §8 第 2 步把游戏文件解到仓库外工作区，读出 NSO 构建号与模块清单，填计划 §3 的表。
- 结果：TotK 的四个模块构建号、模块大小、动态符号 / 重定位数、NVN 取址函数数、RomFS 规模全部实测到手（见下方证据）；§3 的表已填。
- 工具：hactool 1.4.0 解不开更新包的 NCA3 BKTR 补丁段（`Invalid BKTR layout!`），因此新写 `dm/tools/switch_nca.py`（纯 Python 的 NCA3 读 / 解包）与 `dm/tools/nso_stats.py`（NSO 段与动态表统计）——两个工具都只依赖仓库已在用的 pycryptodome / numpy / lz4，且已提交（`becd40b`）。

证据（本条目对应的命令与退出码）：

- 材料核验：XCI 17,677,626,368 字节（`The Legend Of Zelda Tears Of The Kingdom v1.4.2 [0100F2C0115B6000] [v655360] (1G+1U).xci`）、`prod.keys` 13,560 字节、`title.keys` 1,224 字节；D 盘余量 183 GB（解包后仍余 130 GB）。`hactool` 本机原先没有，从上游发布版取得 1.4.0 win-x64 到仓库外 `D:\Switch\.tools\hactool`。
- `hactool -t xci --securedir=...`：exit 0，拆出 6 个 NCA + 2 个 CNMT（本体程序内容 17,148,870,656 字节 = 完整 RomFS；更新程序内容 523,810,304 字节 = RomFS 为 BKTR 补丁）。
- `switch_nca.py info`：exit 0 —— 本体 = Program / 标题 `0100f2c0115b6000` / master key 修订 0xE（段 0 ExeFS 46,153,728 字节、段 1 RomFS 17,102,602,240 字节、段 2 PFS0 96 KB）；更新 = Program / master key 修订 0xF（段 0 ExeFS 45,236,224 字节、段 1 RomFS 478,557,696 字节且 crypt=bktr）。
- `switch_nca.py exefs`（本体）：exit 0，5 个文件 46,119,308 字节；与 hactool 解出的同名文件 **SHA-256 逐个一致**（main / sdk / subsdk0 / rtld）。
- `switch_nca.py exefs`（更新包，hactool 解不出的那份）：exit 0 —— main 35,621,994 / sdk 6,201,403 / subsdk0 3,367,061 / rtld 10,109 字节。
- 构建号（`dm/tools/nso.py` 读 NSO 头 0x40–0x50）：更新 v1.4.2 = main `5cb42b1cf25469fb0635fd046453d843`、sdk `5cf080e800530a7f25bd528ec875c27b`、subsdk0 `3308c1d216f788397d1451c8345a16cd`、rtld `82a3cf78789f9d9858c52379d8d2d129`；本体 v1.0.0 的 main = `082ce09b06e33a123cb1e2770f5f9147`。
- `nso_stats.py`（更新包四个模块）：exit 0 —— text/ro/data = 45,769,200/10,154,076/4,967,776、6,693,520/5,025,004/349,416、3,501,008/1,876,516/199,560、9,536/2,604/4,104 字节；动态符号 706/23,039/10,110/3（未定义即导入 680/9/664/3）；重定位 2,070/19,027/15,648/2；**合计 33,858 符号 / 36,747 重定位 / 1,356 导入**（D2R 参考：38,837 / 116,034 / 264 强制接管）。
- NVN 取址面（`dm/gfx/tools/nvn_slots.py` 的思路，按 TotK 重新定位）：加载函数在 main 的 **0xbbfa90–0xbc3510**，全部 534 个 `adrp+add` 指向 nvn 名字的引用都落在这一个函数里，**取址函数 534 个**（D2R 是 523），槽走间接指针表（`adrp x8,表页; ldr x8,[x8,#imm]; str x0,[x8]`），与 D2R 的直接 `str x0,[xn,#imm]` 形式不同；产出 TotK 的槽表留在仓库外 `D:\Switch\totk-work\nvn_slots_totk.tsv`（接口信息入库要先开 Issue，故不入库）。
- `switch_nca.py romfs-list`：exit 0 —— **304,207 个文件 / 17,043,238,905 字节（15.87 GB）**；`romfs-extract --filter Shader/` exit 0，13 个着色器包 14.3 MB 取出（`material...bfsha.zs` 13.5 MB 最大）。
- 着色器包结构：头是 zstd 魔数（`28 b5 2f fd`），但裸 zstd 解不开（`Dictionary mismatch`）——任天堂用了自带的 zstd 字典，本机没有该字典；故 §4.4 方案 D「从自带着色器缓存读反射」目前只能确认「包是编译后的 BFSHA/SARC，不是反射表」，能否反推维度 / 格式仍待解码。
- 本体 RomFS 全量解包：后台 `switch_nca.py romfs-extract` 运行中（仓库外 `D:\Switch\totk-work\base\RomFS-py`，进度 80,000/304,207 文件、7.91 GB 时记录），工具速度约 145 文件/秒（hactool 同任务约 30 文件/秒，故改用本工具）。
- `build.py --game-run --version trim-b25`：exit 0，APK 17,725,903 字节（与 trim-b24 同大小 —— 本批只加了两个工具，不进包）。
- `ci_checks.py`：10 项通过 / 0 项失败；`agent_handoff_check.py --verify` exit 0。
- **本批 NOT RUN**：更新包 RomFS 的 BKTR 补丁应用（未实现，最终数据集还差这层）、着色器包解码（缺任天堂 zstd 字典）、真机（一加 12 未接）、iOS 侧编译（无 Xcode / macOS）。
- 下一步：NA-028 —— 裁剪批 6 + §4.3 接 TotK（`patch_nso.py` 的规则域按 TotK 真实构建号取表 + 摘 D2R 的 CUTS/OBS 表 / `casc_overlay.py` / iOS 资产管线）。

## 2026-10-20 04:40 Asia/Shanghai — [TOTK] NA-027 TotK 文件准备（解包）进行中

- 会话目标：用户已提供 TotK 本体+更新的合并 XCI 与 `prod.keys`；按计划 §8 第 2 步把游戏文件解到仓库外工作区，读出 NSO 构建号与模块清单，填计划 §3 的表。
- 前置核验：XCI 存在（17,677,626,368 字节，Title ID `0100F2C0115B6000`、v655360、1G+1U）；`prod.keys`（13,560 字节）与 `title.keys`（1,224 字节）存在；D 盘余量 183.1 GB；`hactool` 本机原先没有，已从上游发布版取得 1.4.0 win-x64 到 `D:\Switch\.tools\hactool`（仓库外，不提交）；`adb devices` 仍无设备。

[BEGIN] na-027-totk-extract

- 命令：`hactool -k <prod.keys> --disablekeywarns --suppresskeys -t xci --securedir=<work>\nca <xci>` → 判定本体/更新 → `hactool -t nca --basenca=<本体> --exefsdir=<work>\ExeFS --romfsdir=<work>\RomFS <更新>` → `python dm/tools/nso.py` 读构建号。
- 工作目录：`D:\Switch\d2r-android`（游戏文件落在 `D:\Switch\totk-work`，仓库外）
- 预期结果：ExeFS 与 RomFS 完整取出；每个 NSO 的段布局与构建号有输出。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`c453c584a19393c224b0399502969fcfdb05cd26`


## 2026-10-20 04:05 Asia/Shanghai — [TOTK] NA-025 裁剪批 7s 完成

[BEGIN] na-025-custom-trim

- 命令：`git rm dm/host/dm_custom.c dm/host/dm_custom.h`，并同步宿主调用点、iOS 自定义页布局、`gen_romfs_overlay.py` 变体说明、中英表与单测桩；随后跑 `dm_i18n.py --check`、`scan_literals.py`、`mode_scan.py`、`ci_checks.py`、`build.py --game-run --version trim-b24`。
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：自定义页与 `dm_custom*` 符号清零，语言读取无未定义符号，构建产出 APK，交接控制面单独提交。
- 日志路径：本文件对应 [END] 记录
- 回滚点：`9f0351d01161f8b3171c50e8b0055e5a221a3324`

[END] na-025-custom-trim

- 退出码：`build.py --game-run --version trim-b24` exit 0；`dm_i18n.py --check` exit 0（201 条）；`scan_literals.py` exit 0（295 条中文字面量）；`mode_scan.py` exit 0；`ci_checks.py` 写控制面前 9 项通过 / 1 项失败（仅交接控制面待更新），控制面收尾复跑 10 项通过 / 0 项失败；`agent_handoff_check.py --verify` exit 0。
- 产物：`dm/android/build/D2R-Android-port.apk`，17,725,903 字节（`trim-b24`）
- 结果：SUCCESS
- 备注：语言开关采用方案 (b)：`hle_fs.c` 的 `settings_lang_apply` 与 `dm_custom_lang_explicit()` 一并删除，`dm_sys_lang()` 生产恒为简中，`DM_LANG` 仅作宿主 / 测试模拟；iOS 侧 Xcode / macOS 构建、`dm/host/tests/Makefile` 的 `run:` 目标本机 NOT RUN。

证据（本条目对应的命令与退出码）：

- 宽口径 `git grep -n -i -e dm_custom -e TouchCustom -e dmCustom -e _CUSTOM_ -e sw_custom -- dm/host dm/ios dm/i18n`：0 命中（仅 `dm/android/prebuilt/turnip/vulkan.purple.so` 二进制命中）。
- 符号复核 `git grep -e dm_custom_get -e dm_custom_init -e dm_custom_ui_pump -e dm_custom_on_uimsg -e dm_custom_lang_explicit -e dm_fps_setting -- dm/`：0 命中。
- `dm/host/dm_custom.c`、`dm/host/dm_custom.h` 删除；`dm/host/dm_i18n_tab.h` 重出并与 `dm/i18n/ui_text.tsv` 一致；`dm_i18n.py --check` exit 0。
- `git diff --check` exit 0；业务提交 `1b9b1e4676e2eee83d70cd50f5d9cfa98271f326`（35 文件，67 增 / 503 删）；`git push` exit 0；HEAD 与 `origin/totk/scaffold` 同为 `1b9b1e4676e2eee83d70cd50f5d9cfa98271f326`。
- `usage.md` / `usage.zh-CN.md` 无自定义页引用，保持不变；`uireg/affected.tsv` 删除 `dm/host/dm_custom*` 行；白名单删除 `host/dm_custom.c` 行。
- 本批未改 `dm/ios/Sources/dm_touch_controls.c/.h`，因此没有触发触控层 `-Werror` 专项；iOS 布局改动本机未用 Xcode 验证。


[END] na-027-totk-extract

- 退出码：`switch_nca.py info/exefs/romfs-list/romfs-extract` exit 0；`nso_stats.py` exit 0；`build.py --game-run --version trim-b25` exit 0；`ci_checks.py` 10 项通过 / 0 项失败；`agent_handoff_check.py --verify` exit 0。
- 产物：`dm/android/build/D2R-Android-port.apk` 17,725,903 字节（`trim-b25`）；游戏文件工作区 `D:\Switch\totk-work`（仓库外：ExeFS、本体 RomFS、Shader 包、NSO 平铺映像、NVN 槽表）
- 结果：SUCCESS
- 备注：hactool 1.4.0 解不开更新包的 NCA3 BKTR 补丁段，改用本仓库新写的 `dm/tools/switch_nca.py`；本体 ExeFS 与 hactool 逐字节一致。更新包的 BKTR 补丁应用、着色器包解码、真机实测本批 NOT RUN。

## 2026-10-20 03:45 Asia/Shanghai — [TOTK] 会话收尾（交给新会话）

- 本次会话（接续 NA-015 之后）依次做完并推送了：NA-016（3D 画面加亮，`7520d35`）、NA-017（仓库族，`8a23b42`）、NA-018（百宝囊，`b7ee3e8`）、NA-019（iCloud 存档同步，`52f5953`）、NA-020（大秘境 / 佣兵族，`7db35be`）、NA-021（连战 + 积分牌，`7db35be` 之后）、NA-022（免费回城，`52f5953` 之后）、NA-023（派生表批，`cc279c2`）、NA-024（符文之语助手，`c3fb671`）；每个批次的提交号与证据都在下面各自的条目里。
- 当前 HEAD = `c3fb671`（`totk/scaffold`，与 `origin/totk/scaffold` 同步），代码工作区干净，`ci_checks.py` 10 通过 / 0 项失败，`agent_handoff_check.py --verify` 通过，最新产物 `dm/android/build/D2R-Android-port.apk` 17,775,055 字节（`trim-b23`）。
- **下一步唯一动作 = NA-025**：裁剪批 7s —— 摘掉 iOS 自定义页（`dm_custom.c` 一族 + 布局 + 15 行文案），其中要先定「语言开关（`lang_en`）」的去留（`hle_fs.c` 挂存档时读它来决定游戏语言）。
- 本会话踩过的两个坑，已经写进对应条目的证据里，改 iOS 触控层之后一定要用 `-Werror` 编译一遍 `dm/ios/tests/t_*.c`（本机可用 MinGW 的 `cc`）：① Android 构建不带 `-Werror`，被改坏的注释 / 未用参数它只当警告放过；② 编辑脚本里 `continue` 不删行会死循环（NA-024 那次卡住就是这个）。

[END] na-024-runeword-trim

- 退出码：`build.py --game-run --version trim-b23` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，17,775,055 字节（2026-10-20 03:18:14；比 trim-b22 小 180,224 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 提交：`c3fb671`（业务代码；控制面在下一条）。
- 删除 `dm/host/dm_runeword.c`（91 KB：把原版符文之语做成一个可翻页 / 可看细节 / 可一键镶嵌的清单面板，宿主自绘）。
- 宿主侧：`dm_cursor.c` 去掉清单的四个声明、`rw_hit()` 命中函数、清单开着时「点任何地方都吃掉」那一段、以及长按带孔底材开清单那一支；`dm_actions.c` 的每拍 `dm_runeword_pump()`；`diag.c` 的 `dm_runeword_on_uimsg`；`hle_hid.c` 的手柄 `dm_runeword_pad_filter`（清单开着时十字键 / A / B / L / R 归清单）；`dm_mode_items.h` 的「符文之语清单」登记；`dm_widget.h` 的一句注释；`dm/host/Makefile` 的 `SRC` 一项。**`dm_swapskill`（技能组切换）没动** —— 那是覆盖层上的独立开关，`dm_actions.c` 里另有用户。
- iOS 与布局：`dm/ios/tools/touch_layout.py` 去掉 `_RW`（`TouchRwBox` 那一族控件）、`_rw_text` / `_rw_children_check` / `_inv_rw` / `pad_inv_rw` 与那一大段说明，`PRESENT` 里手柄版物品栏那一项（原来挂 `_inv_rw`）也去掉；`dm/ios/Sources/front_ios.m` 去掉触点脚本的「await rw」指令（等一键合成结束）与它在「全部步执行完」判定里的那个状态位。
- 中英表：删 `dmRwTitle` / `dmRwLevel` / `dmRwHint` / `dmRwGo` 四行，重出 `dm/host/dm_i18n_tab.h`（220 → 216 条），`dm/ios/tools/dm_i18n.py --check` exit 0。
- 单测与登记：`dm/host/tests/t_touch_mac.c` 与 `t_touch_tick_stub.c` 里那五个替身桩、`dm/host/tests/mode_scan.py` 的登记表（`dm_runeword.c` 那一项）。
- UI 回归台：删掉 `rw1` / `rw2` / `rwp` / `rwd` 四局（`rwd` 是详情页里的一键合成）、`affected.tsv` 六行里指向这四局的局名、`usage.md` / `usage.zh-CN.md` 的那一行、`uireg_pick.py` 的核心局说明。**「k 局」保留** —— 它测的是原版自己的镶嵌（把两枚符文按顺序镶进 2 孔软帽），不是我们的清单。
- 白名单：`host/dm_runeword.c` 五行（`@job_stop` / `@list_close` / `@job_readback` / 「储藏箱格」/「背包格」）。
- 宽口径复核 `git grep -n -i -e dm_runeword -e TouchRw -e dmRw -e "await rw" -- dm/`：`dm/` 下 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b23`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
- **本机 NOT RUN 的部分**：`dm/ios` 侧的编译与打包（`touch_layout.py` 与 `front_ios.m` 的改动未经 Xcode 构建验证 —— 但 `touch_layout.py` 本机 `py_compile` 通过）；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了。

## 2026-10-20 03:25 Asia/Shanghai — [TOTK] NA-024 裁剪批 7r（符文之语助手）进行中

[BEGIN] na-024-runeword-trim

- 命令：`git rm dm/host/dm_runeword.c`，并连带清掉宿主侧（`dm_cursor.c` 的清单命中与长按分支、`dm_actions.c` 的每拍泵、`diag.c` 的 UI 消息、`hle_hid.c` 的手柄过滤、`dm_mode_items.h` 的登记、`dm_widget.h` 的注释、`Makefile` 的 `SRC`）、iOS 侧（`touch_layout.py` 的 `TouchRw*` 那一族控件与 `_RW` / `_inv_rw` / `pad_inv_rw` / `_rw_children_check`、`front_ios.m` 触点脚本的「await rw」指令）、中英表四行（`dmRwTitle` / `dmRwLevel` / `dmRwHint` / `dmRwGo`）并重出 `dm/host/dm_i18n_tab.h`、单测替身桩与 `mode_scan.py` 的登记表、UI 回归台里测符文之语清单的四局（`rw1` / `rw2` / `rwp` / `rwd`）与 `affected.tsv` / `usage*.md` / `uireg_pick.py` 的对应行、白名单五行、两个 README 的表行，然后 `ci_checks.py` + `build.py --game-run --version trim-b23` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉符文之语助手后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`ba1e89c9c0b3a74402e78df5cbba01ce33977de7`

## 2026-10-20 02:40 Asia/Shanghai — [TOTK] NA-023 裁剪批 7q（派生表批）进行中

[BEGIN] na-023-derived-tables-trim

- 命令：`git rm dm/host/dm_vault_tab.h dm/host/dm_bright_levels.inc dm/ios/tools/gen_vault_table.py dm/tools/gen_bright_levels.py`，并连带清掉 `dm/tools/shell_stubs.py`（替身清单、`parse()` 里读那两张表的几段、`data()` 里 `VTPART` / `VTROW` / `VTSET` / `BRT` 四类行、`stubs()` 里那两个替身）、`dm/host/dm_derived_rt.h` 的说明、`dm/android/tools/make_package.py` 的 `generators` 元组、`dm/android/tools/build_package.py` 的 `derived.tsv` 说明、`dm/host/Makefile` 的 `GENH` 与两条生成规则、`dm/ios/run.sh` 的 `make` 目标清单、`dm/ios/tools/check_hud_gen.sh` 的「不许提交」清单、`dm/ios/tools/gen_assets.py` 的说明、`dm/tools/d2rm_pack.py` 的生成器循环与亮度表那一段，然后 `ci_checks.py` + `build.py --game-run --version trim-b22` + `agent_handoff_check.py --verify`；**分两次提交**：第一次只含业务代码，第二次把 `dm/android/tools/ci_checks.py`（替身检查）与 HANDOFF、LOG 一起提
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：派生表管线收缩成「只有经验表（+ 技能图标索引）」后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`a8213ef3239cac2de06fd90df699eca2204cbd90`

[END] na-023-derived-tables-trim

- 退出码：`build.py --game-run --version trim-b22` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，17,955,279 字节（2026-10-20 02:28:06；与 trim-b21 同大小 —— 派生表是替身，内容不进包）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除四个文件：`dm/host/dm_vault_tab.h`（编年史仓库表的运行时替身）、`dm/host/dm_bright_levels.inc`（关卡亮度表的替身）、`dm/ios/tools/gen_vault_table.py`（编年史仓库表生成器）、`dm/tools/gen_bright_levels.py`（亮度表生成器）。这两张表的宿主消费方已分别随裁剪批 7k / 7j 摘掉，表与生成器一并没了。
- 派生表管线收缩成「经验表 + 技能图标索引」两张：
  - `dm/tools/shell_stubs.py`：`paths()` 只返回经验表与技能图标索引两处；`parse()` 只读经验表（编年史表与亮度表的解析全部去掉）；`data()` 只写 `EXP` 与 `TAROW` 两类行（`VTPART` / `VTROW` / `VTSET` / `BRT` 四类去掉）；`stubs()` 只写经验表与技能图标索引两个替身（编年史表与亮度表那两个替身去掉）；文件头的说明从「三份」改成「只剩两张」；
  - `dm/host/dm_derived_rt.h` 的说明（共用读取器本身不动，`EXP` 那条路径没动）；
  - `dm/android/tools/make_package.py` 的 `generators` 元组（只留 `dm_hud_exp.h`）与 docstring；`dm/android/tools/build_package.py` 的 `derived.tsv` 说明；
  - `dm/host/Makefile` 的 `GENH`（只留 `dm_hud_exp.h`）与那两条生成规则；`dm/ios/run.sh` 的 `make` 目标清单；`dm/ios/tools/gen_assets.py` 的说明；
  - `dm/tools/d2rm_pack.py` 的生成器循环（只留经验表）与亮度表那一段；`dm/ios/tools/shell_build.sh` 里 `VTROW` / `VTSET` 那段「壳里不许有游戏内容」的扫描（那两类行没有了）与「三份生成文件」的说法。
- 顺手带走的两个上一批的漏网：`dm/tools/d2rm_pack.py` 与 `dm/ios/tools/shell_build.sh` 里还在拷「佣兵面板底图」那一档（`mercslots`，随裁剪批 7o 摘掉的 `gen_merc_art.py` 已经不生成它了）。
- `dm/ios/tools/check_hud_gen.sh` 的「不许提交」清单：去掉那两份已删的表。**顺带修了一处本来就红的地方**：清单里还留着 `dm/host/dm_hud_exp.h`，而它正是**故意提交**的运行时替身（里面没有数据），留着这条就等于每次都报红 —— 一并去掉。
- 文档：`dm/README.md` / `dm/README.zh-CN.md`（「三份表」的说法与表格里那两行）、`dm/host/README*.md`（Makefile 那行）、`dm/ios/README*.md`（build 流程那行）、`dm/tools/README*.md`（`gen_bright_levels.py` 那行）、`dm/ios/tools/uireg/affected.tsv`（`gen_vault_table.py` 那行）。
- **本机验证**（不用游戏文件）：造一份「真实表」样式的 `dm_hud_exp.h` 丢进临时目录，跑 `python dm/tools/shell_stubs.py data dm <输出> --tables <临时目录>` → exit 0，输出 `derived.tsv：经验 100、技能索引 0`，写出 10 行 `EXP`（100 个值）；`python dm/tools/shell_stubs.py stubs dm --tables <临时目录>` → exit 0，写出的经验表替身与仓库里那一份逐字相同（只有注释的换行折行差，代码一样）。
- 顺手把替身识别改严了一处：原来判「这是不是替身」看的是 `k_exp[100]` 这个字符串在不在文件里，而替身里恰好有 `static uint32_t k_exp[100];` → 判不出来，脚本会崩在一个难懂的 AttributeError 上；改成看真正的初始化式 `k_exp[100] = {`。
- 宽口径复核 `git grep -n -e dm_vault_tab -e dm_bright_levels -e gen_vault_table -e gen_bright_levels -e VTPART -e VTROW -e VTSET -e BRT -- dm/`：`dm/` 下 0 命中（只剩 `dm/android/tools/ci_checks.py` 那两条，在控制面提交里改掉）。
- `dm\android\tools\build.py --game-run --version trim-b22`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」：本批改了控制面文件 `ci_checks.py`，它的「派生表是运行时替身」那一项查的正是被摘掉的两张表；改完并与 HANDOFF、LOG 一起提交后收尾复跑 10 项通过 / 0 项失败）。
- **提交分两次**（协议要求：交接控制面单独提，不与业务代码混提）：`cc279c2` = 业务代码（不含 `dm/android/tools/ci_checks.py`）；第二个提交 = `dm/android/tools/ci_checks.py` + HANDOFF + LOG。
- **本机 NOT RUN 的部分**：`dm/ios/run.sh` 与 `check_hud_gen.sh` 的改动未经 Mac 冒烟验证（那两个脚本要 macOS 与 Xcodegen）；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了。

[END] na-022-freetp-trim

- 退出码：`build.py --game-run --version trim-b21` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，17,955,279 字节（2026-10-20 01:57:54；比 trim-b20 小 32,768 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除三个文件：`dm/host/dm_freetp.c`（99 行：进局给玩家挂上原版回城技能 411、无视回城书 / 卷轴直接开门、手柄 ZR 空键免费施放）、`dm/ios/tests/t_portal_sequence.c`（回城手势序列的 C 单测）、`dm/ios/tests/test_portal_receipt.py`（回城收据的 Python 单测）。
- 宿主侧：`dm/host/diag.c` 的每拍 `dm_freetp_server_step`、`dm/host/dm_actions.c` 的 `dm_freetp_client_step`、`dm/host/Makefile` 的 `SRC` 一项、两个 README 的表行。
- 触控层（`dm/ios/Sources/dm_touch_controls.c` / `.h`，这一层 Android 构建也编，编译期能兜住）：枚举里去掉 `DM_TC_PORTAL`、`DM_TC_COUNT` 12 → 11（后面的目标编号顺移，代码里全是按名字引的，只有枚举本身要改）；状态里去掉 `portal_pending` / `portal_phase` / `gesture_epoch` / `portal_binding_identity` / `portal_scene_epoch`；去掉 `dm_tc_set_portal_button` / `dm_tc_set_portal_binding` / `dm_tc_portal_ack` / `dm_tc_cancel_portal` 四个函数与它们的声明；布局里那个钮（技能弧上方）、按键映射里那一支、`dm_tc_cancel_finger` / `dm_tc_cancel_all` / `dm_tc_resize` / 按下 / 抬起几处里的回城分支与相关注释。
- iOS 应用侧：`DmTouchOverlay.m` 去掉那个钮（绘制、标签、图标、`visual_owner`）、两张按枚举序排的字面量数组（`labels` 12 → 11、`names` 12 → 11）、诊断 JSON 里的回城请求字段；`front_ios.m` 去掉点钮发请求那一行、那套「修饰键发布」状态（`_modifierPublishEpoch` / `_modifierPublishEndNS`）、收据里的回城字段、弱符号兜底 `dm_tg_portal_mask` 与 `dm_front_navigation`（连 `g_nav_pub`）；`dm_gamepad.m` 去掉 ZR 空键接管那一段；`dm/host/app_mac.m` 去掉 Mac 宿主那侧的 `dm_front_navigation` 与它的说明。
- **收据协议**：回城钮原来有一套「请求 → 修饰键发布 → 原生绑定确认（ACK）」的两阶段协议（`dm/ios/tools/input_pair_check.py` 的 `validate_portal` 与分析器里的组合配对、`dm/ios/tests/test_input_pair_check.py` 的 35 条用例）。协议没了，校验器里那一整套连同 `PORTAL_FIELDS` 一起去掉（`SOURCES` 去掉 `portal_sequence`），用例从 67 条减到 32 条，本机复跑 `test_input_pair_check.py` **32/32 通过**。
- **顺带恢复的一处**：手柄的「重新绑定技能」框原本只留 1–5 列（第 6 列 ZR 被定成回城快捷键），`touch_layout.py` 里那段 `_bind_modal_5col` 的改写一起去掉 → 恢复原版六列。
- UI 回归台：`tp` 局（回城门）删掉 —— 它开门那一步点的是我们自己的回城钮；原版的回城门要用回城书 / 卷轴（需要专用存档，仓库里没有）。`usage.md` 里那几处 `tp` 的说明同步。`uireg/affected.tsv` 里 `dm/host/dm_freetp*` 那一行删掉。
- 白名单：`ios/Sources/DmTouchOverlay.m` 的「=回城」那一行删掉（那个标签没了），「主技能」那行的理由同步收口。
- 底栏布局的两句说明（`gen_hud_v4.py` / `hud_v4_design.py`）：「回城不在底栏（改为右侧技能钮上方的圆钮）」→「回城格已去掉」。
- **本批踩了两个坑，靠 iOS 触控层单测的 `-Werror` 编译检查抓出来**（Android 构建不带 `-Werror`，只当警告放过）：
  1. 删「回城钮不在底栏」那行注释时，把**底栏那段注释的收尾 `*/` 一起删掉了** → 后面整段被当成注释吞掉。改回：把收尾 `*/` 补回那行。
  2. 删 `dm_tc_resize` 里那四行时，**把函数体里的 `dm_tc_cancel_all(s)` 与 `dm_tc_layout_make(...)` 一起删掉了** → 改尺寸时不再重排布局。改回：函数体保留那两行。
  3. （同类的还有一处）删 `t_skill_aim.c` 里那段回城用例时，把后面的 `dm_tc_resize(&s,667,375)` 一起删掉了 → 主钮拖动那条断言红。改回：补上那行 resize。
  教训：**Android 构建不带 `-Werror`，被改坏的头文件 / 注释 / 未用参数它只当警告**；iOS 触控层那套 C 单测带 `-std=c11 -Wall -Wextra -Werror`，本机用 MinGW 的 `cc` 就能编 → 改触控层之后一定要用 `-Werror` 编一遍 `dm/ios/tests/t_*.c`。
- **iOS 触控层单测本机复跑**（MinGW `cc -std=c11 -Wall -Wextra -Werror`，产物在临时目录、不进仓库）：`t_touch_controls` 编译并通过；`t_skill_aim` 76/76 通过（原先 82 项，少掉的是回城那几条）；`t_binding_freshness` 8/8 通过；`t_joy_travel` 48 项通过；`t_native_binding` 编译通过、运行需要两份夹具（公开仓库不带）故只验编译。
- 宽口径复核 `git grep -n -i -e DM_TC_PORTAL -e dm_tc_portal -e dm_tc_set_portal -e dm_tc_cancel_portal -e dm_tp_request -e dm_freetp -e portal_pending -e portal_phase -e portal_binding -e portal_scene -e gesture_epoch -e portal_sequence -e dm_front_navigation -- dm/`：`dm/` 下 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b21`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
- **本机 NOT RUN 的部分**：`dm/ios` 侧的编译与打包（Objective-C 的三个 `.m` 与布局的改动未经 Xcode 构建验证 —— 但触控层的 `.c` 与五个 C 单测本机用 MinGW `-Werror` 编过并跑过，见上）；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了。

## 2026-10-20 02:00 Asia/Shanghai — [TOTK] NA-022 裁剪批 7p（免费回城）进行中

[BEGIN] na-022-freetp-trim

- 命令：`git rm dm/host/dm_freetp.c dm/ios/tests/t_portal_sequence.c dm/ios/tests/test_portal_receipt.py`，并连带清掉宿主侧（`diag.c` 的每拍、`dm_actions.c` 的客户端步、`Makefile` 的 `SRC`、两个 README）、触控层（`dm_touch_controls.h` 的 `DM_TC_PORTAL` 枚举项与 `DM_TC_COUNT` 12 → 11、四个 `portal_*` 状态字段、四个 `dm_tc_*_portal*` 函数、`dm_touch_controls.c` 里布局摆放 / 按键映射 / 取消手指 / resize / 按下抬起那几处）、iOS 应用侧（`DmTouchOverlay.m` 的那个钮与两张按枚举序排的数组、`front_ios.m` 的回城请求与那套「修饰键发布」状态、`dm_gamepad.m` 的 ZR 空键接管、`app_mac.m` 的 `dm_front_navigation`）、收据协议（`dm/ios/tools/input_pair_check.py` 的 `validate_portal` 与分析器里的组合配对、`dm/ios/tests/test_input_pair_check.py` 的 35 条回城用例、`dm/ios/tests/test_touch_receipt.py` 的 `portal_sequence` 源）、单测（`t_touch_controls.c` / `t_skill_aim.c` / `t_binding_freshness.c` / `t_native_binding.c` 里的回城段）、UI 回归台（`tp` 局）、白名单两行、`uireg/affected.tsv`，然后 `ci_checks.py` + `build.py --game-run --version trim-b21` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉免费回城后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`54dd9ea16e8ff78d70346eed60e5d7b20c49cc6b`

## 2026-10-20 01:05 Asia/Shanghai — [TOTK] NA-021 裁剪批 7o（首领连战 + 刷怪积分牌）进行中

[BEGIN] na-021-bossrush-killboard-trim

- 命令：`git rm dm/host/dm_bossrush.c dm/host/dm_bossrush.h dm/host/dm_kills.c`，并连带清掉宿主侧（`diag.c` 的每拍 / 收包 / UI 消息与那行 include、`dm_actions.c` 的积分牌面板泵、`hle_time.c` 的强制恐怖地带、`hle_hid.c` 的「显示物品」键按下次数、`dm_padmode.c` 两处注释、`dm_bossrush.h` 里 `dm_game_notice` 与 `dm_door_label` 两条声明与它们的实现）、iOS 侧（`touch_layout.py` 的积分牌那一族 `KB_*` / `_kb_*` 与编年史页签条那一段 `_chronicle_killboard`；页签条因此回到原版三个）、中英表 30 行（`dmBr*` / `dmKb*` / `dmPadLegDiff`）并重出 `dm/host/dm_i18n_tab.h`、`uireg/uireg.py` 里测积分牌的两局（`kba` / `kbb`）、`uireg/affected.tsv` 两行、白名单两行、`native_write_scan.py` 的可见位守卫名单、`mode_scan.py` 的登记表、`dm/host/Makefile` 的 `SRC` 两项、两个 README 的表行与说明，然后 `ci_checks.py` + `build.py --game-run --version trim-b20` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉首领连战与刷怪积分牌后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`8947e25ee6695704924ec90d3c5a4ef94c1b45a0`
- 备注：这一批的 `[BEGIN]` 是在动手之后才补记的（当时先把活干完了才想起写）——命令与回滚点按实际做的事写，不美化。

[END] na-021-bossrush-killboard-trim

- 退出码：`build.py --game-run --version trim-b20` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，17,988,047 字节（2026-10-20 01:10:40；比 trim-b19 小 163,840 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除三个文件：`dm/host/dm_bossrush.c`（首领连战，440 行：哈洛加斯那扇门、十二关推进、强制恐怖地带）、`dm/host/dm_bossrush.h`、`dm/host/dm_kills.c`（刷怪积分牌，325 行：五幕的首领名单、三个难度勾选、排序、侧文件 `.sw_kills`）。
- 宿主调用点：`dm/host/diag.c` 的 `#include "dm_bossrush.h"`、每拍 `dm_bossrush_tick` / `dm_kills_tick`、收包 `dm_bossrush_c2s`、UI 消息 `dm_kills_on_uimsg`；`dm/host/dm_actions.c` 的 `dm_kills_ui_pump`。
- **只服务这两族的两样东西一起摘掉**：`dm_game_notice`（原版系统提示：聊天栏一行 + 系统提示框）与 `dm_door_label`（我们自己建的门的名牌：把门那一类物件的串键换成我们的键）—— 摘掉之后它们没有别的用户了，连 `dm_bossrush.h` 里那两条声明一起没了。
- 两处「只给这一族用」的旁路机制：`dm/host/hle_time.c` 的强制恐怖地带（`g_dm_tz_time` / `g_dm_tz_live_ns` / `tz_site()` 那套「只有恐怖地带那几处取时钟拿到它」的判断，以及 `h_time_now` 里那一支）—— 由连战每拍续 1 秒，连战没了就没有人续；`dm/host/hle_hid.c` 的「显示物品」键（L）交给游戏的按下次数（`g_dm_l_presses`，只给连战的首领掉落读数用）。
- iOS 布局：`dm/ios/tools/touch_layout.py` 摘掉积分牌那一族（`KB_ROW_H` / `KB_ICON` / `_kb_keys` / `_kb_text` / `_kb_check` / `_KB_SPACER` / `_kb_row` / `_kb_board` / `_kb_page`）与编年史页签条那一段（`_chronicle_killboard`：页签宽 266 → 320、页签数 3 → 4、帧数组、第四项「首领」、`ToggleChildPanel:TouchKillBoard`、把积分牌那一块插进面板）。**页签条因此回到原版的三个**（`tabCount` 3、宽 266、`@Unique` / `@Sets` / `@Runewords`），布局字典里那一项也回到 `_chronicle_touch` 本身。注意 `_kb_keys()` 是**从 `dm/host/dm_kills.c` 用正则读名单**的 —— 源文件删了它会直接报错，所以两处必须一起走。
- 中英表：删 30 行（`dmBr*` 13 行 + `dmKb*` 16 行 + `dmPadLegDiff`，后者是积分牌手柄提示条上那个「难度」），删前逐个查过使用者、确认没有别人在用；重出 `dm/host/dm_i18n_tab.h`（250 → 220 条），`dm/ios/tools/dm_i18n.py --check` exit 0。
- 闸门与文档：`dm/i18n/literal_whitelist.tsv` 删两行（`host/dm_bossrush.c` / `host/dm_kills.c`）；`dm/ios/tools/uireg/affected.tsv` 删两行（`dm/host/dm_kills*` / `dm/host/dm_bossrush*`）；UI 回归台里测积分牌的两局（`kba` 逐控件点、`kbb` 击杀局）随这一族一起删掉（那一段连同它自带的 `TABS` 与 `chron()` 辅助）；`dm/host/tests/native_write_scan.py` 的可见位守卫名单（`kb_show` 那一项与两行说明）；`dm/host/tests/mode_scan.py` 的登记表（`dm_kills.c` 那一项）；`dm/host/Makefile` 的 `SRC` 两项；`dm/host/README*.md` 的表行与说明。
- 宽口径复核 `git grep -n -i -e dm_bossrush -e dm_kills -e dmBr -e dmKb -e TouchKB -e dm_door_label -e dm_game_notice -- dm/`：`dm/` 下 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b20`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
- **本机 NOT RUN 的部分**：`dm/ios` 侧的编译与打包（`touch_layout.py` 的编年史页签条改动未经 Xcode 构建验证）；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了，涉及 `dm_cursor` / `dm_actions` / `diag` 的宿主单测未经本机执行验证；`dm/ios/tools/uireg/uireg.py` 未经 Mac 冒烟验证。

## 2026-10-20 01:00 Asia/Shanghai — [TOTK] NA-020 裁剪批 7n（大秘境 / 佣兵族）进行中

[BEGIN] na-020-rift-trim

- 命令：`git rm dm/host/dm_rift.c dm/host/dm_rift.h dm/host/dm_rift_ui.c dm/ios/Sources/dm_rift_hud.m dm/host/dm_doorspot.h dm/host/tests/t_doorspot.c dm/host/tests/t_rift_clock.c dm/ios/tools/merc_slots.py`，并连带清掉宿主侧（`diag.c` 的每拍与 UI 消息、观测门 15 那道「拦原版难度提示」、`dm_actions.c` 的面板泵与「打通秘境解锁技能硬点上限」、`dm_cursor.c` 的佣兵装备位提示、`dm_world.c` 的客户端泵、`dm_kills.c` 的秘境统计行、`hle.h` 的四道分支门登记、`hle_fs.c` 的提交前钩子、`dm.h` 的观测门枚举、`dm_bossrush.c` 的 `dm_game_notice` 搬到 `dm_actions.c`）、iOS 侧（`front_ios.m` 的秘境 HUD、`touch_layout.py` 的 `_rift_panel`、`gen_romfs_overlay.py` 的秘境段）、中英表约 90 行并重出 `dm/host/dm_i18n_tab.h`（含 `dm_i18n.py` 的英文长度闸）、`dm/tools/patch_nso.py` 的三道观测门与四道分支门（两侧同收）、白名单、`uireg/affected.tsv` 与 UI 回归台里测秘境的几局、四个 README，然后 `ci_checks.py` + `build.py --game-run --version trim-b19` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉大秘境与佣兵后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`fdfe9ce274b9af573457b6ca0fe6dad3102a8f5e`

[END] na-020-rift-trim

- 退出码：`build.py --game-run --version trim-b19` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,151,887 字节（2026-10-20 00:56:58；比 trim-b18 小 393,216 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除九个文件：`dm/host/dm_rift.c`（秘境爬塔、佣兵面板与装备位、秘境门与回城门，1139 行）、`dm/host/dm_rift.h`、`dm/host/dm_rift_ui.c`（秘境面板的界面，223 行）、`dm/ios/Sources/dm_rift_hud.m`（iOS 那层 HUD，87 行）、`dm/host/dm_doorspot.h`（秘境结算处两扇门的落点）与 `dm/host/tests/t_doorspot.c`、`dm/host/tests/t_rift_clock.c`、`dm/ios/tools/merc_slots.py`（佣兵装备位的布局）、`dm/ios/tools/gen_merc_art.py`（那块底图的生成脚本）。
- **四道分支门（两侧同收）**：`0x89`（秘境出口改道）、`0x8c`（秘境里存档的当前幕）、`0x8d` / `0x8e`（佣兵加装备位与它的客户端校验）。宿主侧：`dm/host/hle.h` 的登记（中英各四条）与 `SVC_HOST_RIFT_EXIT` / `SAVE_ACT` / `MERC_SLOT` / `MERC_SLOT_CL` 四个枚举值、`dm/host/hle_hostcall.c` 的四处分派。改写器侧：`dm/tools/patch_nso.py` 里对应的四段门块（注释 + 门块 + `cuts` 登记，110 行）。
- **三道观测门（两侧同收）**：`15`（客户端事件包，秘境局里拦原版「游戏难度设为 N」）、`16`（服务端按关卡号换关，秘境出口改道）、`17`（服务端任务事件，秘境首领只打不派任务）。宿主侧：`dm/host/dm.h` 的枚举、`dm/host/diag.c` 的 `event_msg_obs` 与 `dm_quiet_difficulty_msg`（连 `g_quiet_diff` 与那段说明一并摘掉）。改写器侧：`patch_nso.py` 里那三行 `obs.append`。
- **顺手修了一个编号越界**：观测门编号 18（`OBS_NOTICE_INPUT`）一直在用，而 `OBS_MAX` 在 NA-013 摘掉 14 号门时被压成了 18 —— 宿主 `gate_register` 判 `id >= OBS_MAX` 就 die，于是带 18 号门的产物一装载就报「观测门编号越界 18」。本批把 `OBS_MAX` 修回 19（18 号门照常用，19 是上界）。
- **「打通秘境解锁技能硬点上限」整条跟着没了**：上限 20 → 40 这套机制的解锁条件就是 `dm_rift_cleared_any()`（`dm/host/dm_actions.c` 的 `dm_skill_cap` / `skill_cap_pump` / 数据表改写 / 「卡在上限」的判定与提示）。秘境摘掉后它永远解锁不了，所以整套机制连同 `dmSkillCapLocked` 那句提示一起去掉。
- **积分牌的「秘境」页跟着没了**：`dm/host/dm_kills.c` 的第六项（act = 5）本来就是秘境成绩页（`dm_rift_stats` / `dm_rift_swept`），摘掉后页签与页数由六项变五项（`act` 上界 5 → 4、两处页签循环 6 → 5、难度与排序两个下拉不再需要为它隐藏）。
- 宿主其余调用点：`dm/host/diag.c` 的每拍 `dm_rift_tick`、收包 `dm_rift_c2s`、UI 消息 `dm_rift_ui_on_uimsg`；`dm/host/dm_actions.c` 的 `dm_rift_ui_pump`；`dm/host/dm_world.c` 的 `dm_rift_client_pump`；`dm/host/dm_cursor.c` 的佣兵装备位提示（`merc_lock_hit` 与「点空格不挪光标」那一段）、只服务秘境的 `dm_ui_send` 与「别的模块请求一键重开」那条通道（`g_rs_ext` / `dm_restart_request`）。
- **共享函数不用搬**：原以为 `dm_game_notice` 得搬到 `dm_actions.c`（那里有个用它的提示），实际那个提示属于技能硬点上限、随机制一起去掉了；剩下只有首领连战与刷怪积分牌两个用户，函数仍住在 `dm_bossrush.c`、声明仍在 `dm_bossrush.h`。
- iOS 与布局：`dm/ios/tools/touch_layout.py` 摘掉编年史页签那一族的秘境内容（`_rf_*` 辅助与常量、`_rift_board`、`_rift_panel`）、积分牌的秘境页（`_kb_rift_row` / `_kb_rift_page`）与第六个页签（页签文字那一行原本是 `('@dmKbAct%d' % (i + 1)) if i < 5 else '@dmKbRift'`）；`dm/ios/tools/gen_romfs_overlay.py` 去掉大秘境面板那一段（借「消息记录」面板外壳做的那份）；`dm/ios/Sources/front_ios.m` 去掉秘境 HUD 那一画与信息层说明里的那半句；`dm/ios/tools/gen_assets.py` 去掉「佣兵面板底图」那一步；`dm/host/dm_widget.h` 那条说明里的例子（`TouchRF_M1`）换成泛指。
- 中英表：删 105 行（`dmRift*` 92 行 + `dmKbRift*` 9 行 + `dmMercSlotLocked` + `dmSkillCapLocked` + `dmKbRift`），删前逐个查过使用者、确认没有别人在用；重出 `dm/host/dm_i18n_tab.h`（355 → 250 条），`dm/ios/tools/dm_i18n.py --check` exit 0；`dm_i18n.py` 里那组秘境英文长度闸（`EN_LIMITS` 的 `dmRift*` / `dmKbRift*` 十几行）与它的说明一并摘掉。
- 闸门与文档：`dm/i18n/literal_whitelist.tsv` 删 7 行（`host/dm_rift.c` 六行 + `host/dm_rift_ui.c` 一行）；`dm/ios/tools/uireg/affected.tsv` 删三行（`dm/host/dm_rift*` / `merc_slots.py` / `gen_merc_art.py`）与说明里「秘境要真机专项」那半句；`dm/host/README*.md` 与 `dm/README*.md` 的表行与说明；`dm/host/Makefile` 的 `SRC` 两项；`dm/host/tests/Makefile` 的 `t_doorspot` / `t_rift_clock` 规则与 `run:` 列表里那两项；`dm/host/tests/t_touch_mac.c` 与 `t_touch_tick_stub.c` 各三个替身桩；`dm/host/tests/mode_scan.py` 的登记表（`dm_rift_ui.c` 两项去掉，`dm_cursor.c` 的「替玩家按键 / 发消息」38 → 36：摘掉 `dm_ui_send` 时连它里面的 `fe_send` 一起少了两处）。
- UI 回归台：测秘境的几局（`kba` / `kbb` / `dc` / `tp`）本身与秘境无关，**保留**（`kba` 点的是五个幕的页签，本来就没点第六项）；`dc` 局那两句说明里提到「秘境图上点继续会崩」的地方改成「秘境已随裁剪批 7n 摘掉，这一局作为普通野外的基线保留」。
- 宽口径复核 `git grep -n -i -e dm_rift -e dmRift -e dmMerc -e gen_merc -e TouchRF -e dmKbRift -e dmSkillCap -- dm/`：`dm/` 下 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b19`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
- **本机 NOT RUN 的部分**：`dm/ios` 侧的编译与打包（`touch_layout.py` / `gen_romfs_overlay.py` / `gen_assets.py` / `front_ios.m` 的改动未经 Xcode 构建验证；`dm/ios/project.yml` 的 `sources: - Sources` 是整目录，删掉 `dm_rift_hud.m` 不需要改工程描述）；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了，涉及 `dm_cursor` / `dm_actions` / `dm_kills` 的宿主单测未经本机执行验证；`dm/ios/tools/uireg/uireg.py` 的几局未经 Mac 冒烟验证。

## 2026-10-20 00:45 Asia/Shanghai — [TOTK] NA-019 裁剪批 7m（iCloud 存档同步）进行中

[BEGIN] na-019-icloud-trim

- 命令：`git rm dm/host/dm_cloudsync.c dm/ios/Sources/cloud_ios.m dm/ios/tools/cloud_guard.sh dm/host/tests/t_cloudsync.c`，并连带清掉宿主侧（`diag.c` 的冲突提示、`hle_fs.c` 的 `g_dm_save_commit_hook`、`dm_uiscreen.c` 的 `g_dm_ingame_hook`、`dm_custom.c` 的 `icloud` 开关、`Makefile` 的 `SRC`、两个 README、单测的 `t_cloudsync` 规则）与 iOS 侧（`main.m` 的 `dm_cloud_boot`、`front_ios.m` 的 `dm_cloud_flush` / `dm_cloud_foreground`、`project.yml` 的三行 iCloud 权限、`project_free.py` 的免费账号那组权限清单、`run.sh` / `local.env.example` / `smoke_mac.sh` / `touch_e2e_mac.sh` / 两个 README 的说明）、中英表两行（并重出 `dm/host/dm_i18n_tab.h`）、白名单两行、UI 回归台的 `rf3` 局与 `affected.tsv` 里指向它的局名，然后 `ci_checks.py` + `build.py --game-run --version trim-b18` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉 iCloud 存档同步后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`7b1454e266d8e4f7498150d36dbdb988947739f3`

[END] na-019-icloud-trim

- 退出码：`build.py --game-run --version trim-b18` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,545,103 字节（2026-10-20 00:22:04；比 trim-b17 小 49,152 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除四个文件：`dm/host/dm_cloudsync.c`（同步核心：本地存档目录 ↔ 一个云端目录的文件对比与搬运）、`dm/ios/Sources/cloud_ios.m`（iOS 侧：ubiquity 容器、`dm_cloud_boot` / `dm_cloud_flush` / `dm_cloud_foreground`）、`dm/ios/tools/cloud_guard.sh`（本机测试时把云端指到一次性本地目录的总闸）、`dm/host/tests/t_cloudsync.c`（同步核心的单测）。
- 宿主侧连带清掉：`diag.c` 的 `dm_cloud_conflict_take`（共享仓库冲突时弹系统提示）与 `g_dm_charsel_hook` 的调用（只有 `cloud_ios.m` 设它，摘掉后无人设 → 声明与调用一起去）；`hle_fs.c` 的 `g_dm_save_commit_hook`（同样只有 iCloud 那一侧设它）与调用点；`dm_uiscreen.c` 的 `g_dm_ingame_hook`（只有 `cloud_ios.m` 设它）；`dm/host/Makefile` 的 `SRC` 一项；`dm/host/README*.md` 的表行；`dm/host/tests/Makefile` 的 `t_cloudsync` 编译规则与 `run:` 列表里那一项。
- 自定义开关 `icloud` 两侧同收（`dm_custom.c` 的 `k_keys` / `k_def` / 读盘日志、`dm_custom.h` 的键说明、`touch_layout.py` 的 `_CUSTOM_KEYS`），**行序核对**：`k_keys` = `lang_en` + `_CUSTOM_KEYS` 两侧逐项相同（11 项对 11 项），`k_def` 长度也是 11（`eco_fps` 缺省关、其余开）。
- iOS 应用侧：`main.m` 去掉 `dm_cloud_boot()` 与「全新存档 = 新设备」那段里清 `.cloudstate` / `.cloudbak` 的两行；`front_ios.m` 去掉 `dm_cloud_flush(1)` 与 `dm_cloud_foreground()`；`project.yml` 去掉三行 iCloud 权限（`icloud-container-identifiers` / `icloud-services` / `ubiquity-container-identifiers`；**App 组那一行留着**——它服务的是苹果托管资源包 `BAAppGroupID`，与同步无关）；`project_free.py` 的免费账号那组权限清单从六行收到三行（正则与计数 `6 → 3` 一起改，数目对不上会报错不出文件）；`run.sh` / `local.env.example` / `dm/ios/README*.md` 的说明同步收口。
- 本机测试脚本：`smoke_mac.sh` 去掉 `cloud_guard.sh` 依赖、source、总闸那一段与收尾的 `cloud_guard_check`（`$CGA` 那个空环境变量在六处 `open` 上一起去掉）；`touch_e2e_mac.sh` 去掉 source、总闸那一段与收尾检查；`uireg/run_mac.sh` 去掉总闸与收尾那道「真实 iCloud 闸」。三处脚本里的中英注释对都成对删（`smoke_mac.sh` 里有一段中英交错，删的时候把英文那行补回来了，已复核）。
- 中英表：删 `dmCustomIcloud` 与 `dmCloudConflict` 两行，重出 `dm/host/dm_i18n_tab.h`（357 → 355 条），`dm/ios/tools/dm_i18n.py --check` exit 0；`dm/i18n/literal_whitelist.tsv` 删 `host/dm_cloudsync.c` 与 `ios/Sources/cloud_ios.m` 两行。
- UI 回归台：删掉测同步上传的 `rf3` 局，`dm/ios/tools/uireg/affected.tsv` 里 `dm/host/dm_cloudsync*` 那一行整个删掉、`dm/host/hle_fs.c` 那一行里的 `rf3` 也去掉。
- 宽口径复核 `git grep -n -i -e dm_cloud -e cloud_ios -e cloud_guard -e icloud -e iCloud -e dmCloud -- dm/`：`dm/host` / `dm/ios` / `dm/i18n` / `dm/android` 的代码与文案里 0 命中。`dm/ios/Sources/asset_dl.m` 里那两处提到 iCloud 的说明也一并改口了（直装包没有托管资源包、4 GB 资源不进**设备**备份 —— 那是 `NSURLIsExcludedFromBackupKey`，本来就不是同步功能）。
- `dm\android\tools\build.py --game-run --version trim-b18`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
- **本机 NOT RUN 的部分**（iOS 侧本机编不了）：`dm/ios/project.yml` / `project_free.py` / `main.m` / `front_ios.m` 的改动未经 Xcode 构建验证；`smoke_mac.sh` / `touch_e2e_mac.sh` / `uireg/run_mac.sh` 是 shell 脚本，本机没有可用的 bash（WSL 启动器已坏），未经 `bash -n` 语法检查；`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）跑不了。

## 2026-10-20 00:05 Asia/Shanghai — [TOTK] NA-018 裁剪批 7l（百宝囊）进行中

[BEGIN] na-018-pouch-trim

- 命令：`git rm dm/host/dm_pouch.c dm/ios/tools/pouch_layout.py dm/ios/tools/gen_pouch_art.py`，并连带清掉 `dm_world.c`（每拍 `dm_pouch_step`）、`diag.c`（`dm_pouch_srv_tick` / `dm_pouch_c2s` / `dm_pouch_on_uimsg`）、`dm_cursor.c`（`dm_pouch_tip_gate` 两处）、`hle_fs.c`（提交前钩子再收一格）、`dm_rift.c` 与 `t_rift_clock.c`（钩子槽号）、`dm.h`（`dm_blob`）、`dm_custom.c` / `dm_custom.h` 与 `touch_layout.py`（`gem_pick` / `store_btn` 两个开关，行序两侧同收）、`gen_romfs_overlay.py` 与 `gen_assets.py`（百宝囊那一段）、`dm/i18n/ui_text.tsv`（`dmPouch*` / `dmStore*` / 自定义页那两行）并重出 `dm/host/dm_i18n_tab.h`、`uireg/uireg.py`（sa 局）与 `uireg/affected.tsv`、两个 README 表行、`dm/host/Makefile` 的 `SRC`，然后 `ci_checks.py` + `build.py --game-run --version trim-b17` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉百宝囊后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`cc24c702a7a497884fd2b1ea8ddf5396762e3775`

[END] na-018-pouch-trim

- 退出码：`build.py --game-run --version trim-b17` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,594,255 字节（2026-10-20 00:03:38；比 trim-b16 小 114,688 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除三个文件：`dm/host/dm_pouch.c`（符文 / 宝石自动拾取进囊、囊里清单、背包「存放」按钮、囊的侧文件）、`dm/ios/tools/pouch_layout.py`（物品栏底部那块百宝囊框与「存放」按钮的布局）、`dm/ios/tools/gen_pouch_art.py`（百宝囊框贴图的生成脚本）。
- 调用点：`dm/host/dm_world.c` 每拍的 `dm_pouch_step`；`dm/host/diag.c` 的 `dm_pouch_srv_tick` / `dm_pouch_c2s` / `dm_pouch_on_uimsg`；`dm/host/dm_cursor.c` 的 `dm_pouch_tip_gate` 两处；`dm/host/dm.h` 的 `dm_blob` 类型（只剩百宝囊在用）；`dm/host/Makefile` 的 `SRC` 一项。
- 提交前钩子再收一格：`dm/host/hle_fs.c` 的 `g_dm_pre_commit_hook[2]` 缩成 `[1]`（秘境进度 `[0]`），`dm_rift.c` 与 `dm/host/tests/t_rift_clock.c` 同步，没有悬空槽位。
- 自定义开关两侧同收：`gem_pick`（符文宝石自动拾取）与 `store_btn`（背包「存放」按钮）从 `dm/host/dm_custom.c` 的 `k_keys[]` / `k_def[]` / 读盘那行日志里摘掉，从 `dm/host/dm_custom.h` 的键说明里摘掉，从 `dm/ios/tools/touch_layout.py` 的 `_CUSTOM_KEYS` 里摘掉。**行序核对**：`k_keys` = `lang_en` + `_CUSTOM_KEYS` 两侧逐项相同（12 项对 12 项），`k_def` 长度也是 12（`eco_fps` 缺省关、其余开）。
- 中英表：删 11 行（`dmPouchTitle` / `dmPouchEmpty` / `dmStoreHead` / `dmStoreStash` / `dmStorePouch` / `dmStoreSep` / `dmStoreNone` / `dmStoreLeft` / `dmStoreFull` / `dmCustomGemPick` / `dmCustomStoreBtn`；删前逐个查过：这些键只被百宝囊那族用），重出 `dm/host/dm_i18n_tab.h`（368 → 357 条），`dm/ios/tools/dm_i18n.py --check` exit 0，`dm/i18n/scan_literals.py` exit 0（347 条中文字面量全在白名单）。
- iOS 资产管线：`dm/ios/tools/gen_romfs_overlay.py` 去掉 `pouch_layout` 的 import 与两处 build；`dm/ios/tools/gen_assets.py` 去掉「百宝囊框」那一步与说明里的 `pouch` 目录；`dm/ios/run.sh` 与 `dm/ios/tools/check_hud_gen.sh` 的注释 / 路径清单同步；`dm/i18n/scan_literals.py` 的扫描清单里去掉已删的 `pouch_layout.py`。
- UI 回归台（`dm/ios/tools/uireg/`）：删掉「sa 局」（它测的正是百宝囊的自动存入）；s 局里那几步的判据跟着改（拖进个人页的符文现在留在个人页，珍宝匣那一格是空的，取件时那一叠是 1 个）；sb 局的页签序列去掉第六页。
- **补上 NA-017 漏掉的一处**：NA-017 摘掉编年史仓库与个人仓库多页时，UI 回归台里测这两个模块的五局（`pg1` / `pg2` / `vt1` / `vf1` / `vf2`）忘了删，脚本还在断言「个人仓库：第 1 → 2 页」「编年史仓库：进第六页」这些已经不会出现的日志。本批一并删掉，并把 `uireg/affected.tsv` 里指向这五局（外加已删的 `sa`）的 13 行局名清掉、把 `uireg/uireg_pick.py` 的核心局清单里的 `pg2` / `vt1` 去掉。
- 行为变化（要记清）：**珍宝匣那一页还在**（合页、页签、底图都在 `wide_stash.py` 与 `dm_cursor.c` 里），但「仓库页里新落下的符文 / 宝石 / 材料自动转进高级仓库」与「符文拖进共享页时收包处改道」这两条是写在 `dm_pouch.c` 里的，随本批一起没了。
- 宽口径复核 `git grep -n -i -e dm_pouch -e dmPouch -e TouchPouch -e TouchStore -e pouch -e gem_pick -e store_btn -- dm/`：`dm/host` / `dm/ios` / `dm/i18n` / `dm/android` 的代码与文案里 0 命中，只剩 `dm/ios/tools/uireg/uireg.py` 里那两行「百宝囊摘掉之后…」的判据说明（有意保留）。
- `dm\android\tools\build.py --game-run --version trim-b17`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。

## 2026-10-19 23:30 Asia/Shanghai — [TOTK] NA-017 裁剪批 7k（仓库族）进行中

[BEGIN] na-017-vault-trim

- 命令：`git rm dm/host/dm_vault.c dm/host/dm_vault_ui.c dm/host/dm_pages.c`，并连带清掉 `diag.c`（每拍调用与 UI 消息）、`dm_actions.c`（`dm_vault_ui_pump`）、`dm_cursor.c` / `dm_cursor.h`（编年史页命中 / 拖拽 / 提示框 / 存放判定、`DM_PS_VAULT` 枚举位、个人页页码与左右箭头）、`dm_pouch.c`（存放路径搬共享辅助函数过来并去掉编年史分支）、`hle_fs.c`（提交前钩子槽位重编号）、`dm_rift.c`（钩子槽号）、`wide_stash.py`（第六页与 TouchVault / TouchPgPage 控件）、`dm/i18n/ui_text.tsv`（`dmVault*` 等行）并重出 `dm/host/dm_i18n_tab.h`、`literal_whitelist.tsv`、`uireg/affected.tsv`、`dm/host/tests/` 的替身桩、`Makefile` 的 `SRC`、两个 README 表行，然后 `ci_checks.py` + `build.py --game-run --version trim-b16` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉编年史仓库与个人仓库多页后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`010ea306820006d132d5f29f6abfab6374f2816c`

[END] na-017-vault-trim

- 退出码：`build.py --game-run --version trim-b16` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,708,943 字节（2026-10-19 23:43:28；比 trim-b15 小 245,760 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除三个文件：`dm/host/dm_vault.c`（编年史仓库的服务端一半，45,148 字节）、`dm/host/dm_vault_ui.c`（储藏箱第六页「编年史」的整套 UI，66,804 字节）、`dm/host/dm_pages.c`（个人仓库 2–5 页，35,049 字节）。这族共享的辅助函数只在本族内用（`dm_item_write` / `dm_item_make` / `dm_memfind` 在 `dm_pages.c`，`dm_save_blobs` / `dm_blobs_have` / `dm_blobs_free` / `dm_stash_name` / `dm_item_quest` 在 `dm_vault.c`），所以整族一起摘。
- `dm/host/dm_cursor.c`（本批改动最多的文件）：摘掉编年史页的落点分类、说明框、拖拽、单击、界面双击存入，摘掉 `DM_PS_VAULT` 枚举位与 `dm_ui_bag_point`（只剩编年史用），摘掉个人仓库页码那一整套（`pages_text` / `ui_pages_pump` / `TouchPgPage` 控件）、左右箭头与外圈翻页（`pg_personal` / `pg_near` / `PG_REACH`）、落点查询里的 `g_vault_drop` / `dm_ui_vault_drop`、以及切换布局后记页签的 `g_bank_tab_keep`（它是为「停在第六页会被跳回个人页」引入的，编年史没了就不需要）。
- `dm/host/dm_cursor.h`：`DM_PS_*` 枚举去掉 `DM_PS_VAULT = 64`，其余位（BANK 1 / VENDOR 2 / DEAD 4 / TEXT 8 / IMBUE 16 / CUBE 32）取值不变，位掩码没有错位。
- `dm/host/dm_pouch.c`（百宝囊）：把 `dm_item_write` / `dm_item_make` / `dm_memfind`（原在 `dm_pages.c`）与 `dm_item_quest`（原在 `dm_vault.c`）搬过来并改成 `static`（剩下的唯一使用者就是百宝囊）；「存放」路径去掉编年史分支 —— 已鉴定的暗金 / 套装件不再有去处，只算「留在背包」，`dmStoreVault` 那句提示与 `g_sv` 计数一并去掉。
- 提交前钩子重编号：`dm/host/hle_fs.c` 的 `g_dm_pre_commit_hook[4]` 缩成 `[2]`（百宝囊 `[0]`、秘境进度 `[1]`），`dm_pouch.c` / `dm_rift.c` / `dm/host/tests/t_rift_clock.c` 三处同步，没有悬空槽位。
- 其余调用点：`diag.c` 的每拍 `dm_pages_tick` / `dm_vault_tick` 与 UI 消息 `dm_vault_on_uimsg`；`dm_actions.c` 的 `dm_vault_ui_pump`；`frontend_activity.c` 启动时的 `dm_vault_load()`（那张派生表连同它的替身归「派生表批」）；`dm/host/Makefile` 的 `SRC` 三项。
- iOS 布局 `dm/ios/tools/wide_stash.py`：去掉第六个页签（`tabCount` 回到 5、页签条的帧数组与文字串回到原版五个，第三个仍改成「珍宝匣」`@dmTroveTab`）、`TouchVault` 整套控件、`TouchPgPage` 页码控件、编年史盖板贴图的拷贝；`vault_tab()` 改名 `trove_tabs()`。
- `dm/host/dm_cursor.c` 的珍宝匣页签泵：原来会把第 5 个页签（编年史）左移两个页签宽，落在空页 3 / 4 时在「编年史 ↔ 珍宝匣」之间改选；现在去掉前一半，改选一律回珍宝匣。
- 中英表：删 29 行（24 行 `dmVault*` 含 `dmVaultPart0–10` / `dmVaultTierN/X/E`，加 `dmStoreVault`、`dmStashVaultTab`、`dmPadLegView/Prev/Next`；删前逐个查过：这些键只被编年史那一族用），重出 `dm/host/dm_i18n_tab.h`（397 → 368 条），`dm/ios/tools/dm_i18n.py --check` exit 0。
- 闸门与文档：`dm/i18n/literal_whitelist.tsv` 删 3 行（`host/dm_vault.c`、`host/dm_pages.c`、`host/dm_vault_ui.c`）、`dm/ios/tools/uireg/affected.tsv` 删 2 行、`dm/host/tests/t_touch_mac.c` 与 `t_touch_tick_stub.c` 各删 10 个替身桩、`t_rift_clock.c` 的钩子数组、`dm/host/tests/native_write_scan.py` 去掉对已删文件的那道静态扫（剩下覆盖整个宿主的可见位 / 矩形两道）、`dm/host/tests/mode_scan.py` 的登记表（`dm_cursor.c` 8 → 7，删 `dm_vault_ui.c` 一项）、四个 README、`dm/verify/shotgate_pages/stash.json` 里那块「第 n/5 页」页码的遮罩。
- 宽口径复核 `git grep -n -i -e dm_vault -e dmVault -e dm_pages -e dm_page -e DM_PS_VAULT -e TouchV_ -e PgPage -- dm/host dm/ios dm/i18n dm/android`：`dm/host` / `dm/ios/Sources` / `dm/ios/tools` / `dm/i18n` / `dm/android` 的代码与文案里 0 命中，只剩 `dm/host/dm_pouch.c` 开头那两行「这两个包装从 dm_pages.c / dm_vault.c 搬过来」的来历说明（有意保留）。
- 刻意保留（属「派生表批」与「资产管线批」，本批不碰，须在后续单独做）：`dm/host/dm_vault_tab.h` 替身与其生成器 `dm/ios/tools/gen_vault_table.py`、`dm/tools/shell_stubs.py`、`dm/host/Makefile` 的 `GENH`、`dm/android/tools/ci_checks.py` 的替身检查、`dm/android/tools/make_package.py`、`dm/tools/d2rm_pack.py`、`dm/ios/run.sh`、`dm/ios/tools/check_hud_gen.sh`、`dm/ios/tools/gen_vault_cover.py` 与 `gen_assets.py` 里的「编年史盖板」那一步。
- `dm\android\tools\build.py --game-run --version trim-b16`：exit 0，产物同上。**中间失败一次**：第一次构建挂在 `dm/host/dm_cursor.c:1425` 的 `!vb`（`vb` 那个「编年史页挡住指针事件」的变量随编年史块一起摘了，但还有第二处用它）→ 那一处改成恒真后重新构建通过。
- `dm\android\tools\ci_checks.py`：写本条目之前 9 项通过 / 1 项失败（失败的是「Agent 交接控制面」，因为 `[END]` 还没成对、HANDOFF 还没更新），收尾复跑 10 项通过 / 0 项失败。
## 2026-10-19 22:05 Asia/Shanghai — [TOTK] NA-016 裁剪批 7j（3D 画面加亮）进行中

[BEGIN] na-016-bright-trim

- 命令：`git rm dm/host/dm_bright.c`、清掉 `diag.c` 的每拍调用与 Android 前端的 `dm_bright_load()`、`Makefile` 的 `SRC`、`dm/host/README*.md` 的表行、`dm_derived_rt.h` 与 `nvn_mtl.m` 里提到它的注释，然后 `ci_checks.py` + `build.py --game-run --version trim-b15` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：宿主不再做 3D 画面加亮后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`af0ddc3a1bc4eb5187de796ec8506c0a2b3ea03c`

[END] na-016-bright-trim

- 退出码：`build.py --game-run --version trim-b15` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,954,703 字节（2026-10-19 23:08:50；比 trim-b14 小 32,768 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_bright.c` —— 「3D 画面加亮」的宿主侧动态曝光实现（按所在关卡的类型与原版自算的环境亮度算曝光 k = 1–4，每帧喂给图形层的 `dm_bright_k()`）。
- 调用点：`dm/host/diag.c` 拍入口那行 `dm_bright_server_tick(regs[0])`（顺带删掉测试开关 `DM_TEST_DAYTIME`）；`dm/android/native/frontend_activity.c` 的 `boot()` 里那行 `dm_bright_load()`（启动时从数据包 `derived.tsv` 填亮度表）；`dm/host/Makefile` 的 `SRC` 一项；两个 `dm/host/README*.md` 的表行。
- 图形层刻意不动：`dm/gfx/nvn/nvn_mtl.m` 的 `bright_lut` 整段保留，但宿主侧的强定义已随 `dm_bright.c` 摘除，只剩 `__attribute__((weak)) float dm_bright_k(void) { return 1.0f; }` 缺省；`bright_lut` 里 `if (!(k > 1.005f)) return;` 于是直接返回、不重写调色表 → 画面保持原版亮度，图形层零改动、也不会误加亮。
- 注释收口：`dm/host/dm_derived_rt.h`（说明亮度表的宿主消费方已摘除）与 `dm/gfx/nvn/nvn_mtl.m` 两处中英注释改成「宿主侧实现已摘除，只剩弱符号缺省 1.0」。
- 刻意保留（归到后面的「派生表批」一起摘）：`dm/host/dm_bright_levels.inc`（替身）与 `dm/tools/gen_bright_levels.py`（生成器）仍在仓库里，但宿主已无人消费它们；那一批要连带 `dm/tools/shell_stubs.py` 管线、`make_package.py`、`ci_checks.py` 等属控制面改动，按协议分两次提交。
- 宽口径复核 `git grep -n -i -e dm_bright -e bright_levels -e bright -- .`：`dm_bright.c`、`dm_bright_load`、`dm_bright_server_tick`、`DM_TEST_DAYTIME` 在代码里 0 命中（只剩 `docs/ANDROID_PORT_PROGRESS*` 的历史叙述与本日志）。文件名形态（`dm_bright.c`）与符号形态（`dm_bright_k` / `dm_bright_load` / `dm_bright_server_tick`）两种都查了。
- `dm\android\tools\build.py --game-run --version trim-b15`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：本机 PowerShell 控制台默认 GBK，`test_version` 一项会因打印 `✓` 抛 `UnicodeEncodeError`（不是代码问题）；设 `PYTHONIOENCODING=utf-8` 后该项通过。写本条目之前「Agent 交接控制面」一项必然失败（`[END]` 尚未成对 + HANDOFF 未更新），收尾复跑 10 项通过 / 0 项失败。
- 与原计划的偏差：原 NA-016 写的是「个人仓库 2–5 页」（`dm/host/dm_pages.c`）。本批改做 3D 画面加亮，个人仓库那部分并入 NA-017（仓库族：`dm_vault.c` / `dm_vault_ui.c` / `dm_pages.c` 一起摘，因为共享辅助函数只在这族内用）。偏差原因与新范围已写进 HANDOFF 的「下一步唯一动作」。

## 2026-10-19 23:20 Asia/Shanghai — [TOTK] NA-015 裁剪批 7i（起名页随机取名）进行中

[BEGIN] na-015-namegen-trim

- 命令：`git rm dm/host/dm_namegen.c dm/host/tests/t_namegen.c`、清掉 `dm_actions.h` 的 `dm_name_gen` 声明、`front_ios.m` 起名页自动填名那段与相关注释、`dm_cursor.c` 里随之失效的 `g_fe_name_no_accept` 机制、`dm/host/tests/Makefile` 的 `t_namegen` 目标与 `run:` 列表、`dm/host/Makefile` 的 `SRC`、两个 README 表行、`uireg/affected.tsv` 行，然后 `ci_checks.py` + `build.py --game-run --version trim-b14` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉起名页随机取名后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`d8e66a50d51288796f6d547bef4c736ae584f32b`
[END] na-015-namegen-trim

- 退出码：`build.py --game-run --version trim-b14` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，18,987,471 字节（2026-10-19 22:49:28；比 trim-b13 小 16,384 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_namegen.c`（起名页留空时按音节拼随机名、避开重名）与单测 `dm/host/tests/t_namegen.c`。
- 调用点：`dm/host/dm_actions.h` 的 `dm_name_gen` 声明；`dm/ios/Sources/front_ios.m` 起名页那段「名字留空点确定 = 随机取名」（含四行注释与那行调用）—— 摘掉后原版自带的「随机名字」键仍是玩家的实际入口，所以这是 D2R iOS 产品的一个**增强功能下线**，不是功能坏掉。
- 随之失效的机制：`dm/host/dm_cursor.c` 的 `g_fe_name_no_accept`（前端抽到随机名时用来抑制自动「接受」）—— 它只由上面那段前端代码置位，前端那段摘掉后它永远是 0，机制与那个标志一起摘掉，`dm_ui_text_entered` 回到「输入即接受」的常态。
- 其余：`dm/host/tests/Makefile` 的 `t_namegen` 编译规则与 `run:` 列表引用、`dm/host/Makefile` 的 `SRC` 一项、两个 `dm/host/README*.md` 的表行、`dm/ios/tools/uireg/affected.tsv` 的一行；`dm/i18n/literal_whitelist.tsv` 无相关行。
- 宽口径复核 `git grep -n -e dm_namegen -e dm_name_gen -e name_gen -e g_fe_name_no_accept -- .`：除 `docs/HANDOFF*` 外 0 命中（文件名与符号名的下划线写法不同，两种形态都查了）。
- `dm\android\tools\build.py --game-run --version trim-b14`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 23:10 Asia/Shanghai — [TOTK] NA-014 裁剪批 7h（极乐世界模式）进行中

[BEGIN] na-014-elysium-trim

- 命令：`git rm dm/host/dm_elysium.c dm/host/dm_elysium.h`、清掉 `diag.c`／`dm_actions.c` 的两处调用与两处 include、`dm_cursor.c` 的建角页勾选框（触屏路径的 TouchBliss 读取与那一行的命中挪动、手柄路径的读取与 Y 键翻勾、「返回」判定里排除那一行的条件）、`dm_cursor.h` 的 `dm_fe_bliss` 声明、`touch_layout.py` 的 `_BLISS` 布局块与 `pad_bliss` 里的插入、单测替身里的两个桩、README／白名单／uireg 行，然后 `ci_checks.py` + `build.py --game-run --version trim-b13` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉极乐世界模式后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`90e63b14da709505ce319a7f318c00adb349cb33`
[END] na-014-elysium-trim

- 退出码：`build.py --game-run --version trim-b13` exit 0（**中间失败过两次，见下**）
- 产物：`dm/android/build/D2R-Android-port.apk`，19,003,855 字节（2026-10-19 22:41:10；比 trim-b12 小 81,920 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_elysium.c` 与 `dm_host/dm_elysium.h`（「极乐世界」模式：D2R 特有的按角色开关，建角时勾选，该角色局内暗金掉率 ×5、套装 ×3）。
- 调用点：`dm/host/diag.c` 的 `#include` 与服务端 `dm_elysium_stash_step`、`dm/host/dm_actions.c` 的 `#include` 与每帧 `dm_elysium_pump`、`dm/host/dm_cursor.c` 的 `#include` 与建角页勾选框（触屏路径的 TouchBliss 读取与那一行的命中挪动、手柄路径的读取与 Y 键翻勾、「返回」判定里排除那一行的条件、`g_fe_bliss` 与 `dm_fe_bliss`）、`dm/host/dm_cursor.h` 的 `dm_fe_bliss` 声明。
- 布局与文案：`dm/ios/tools/touch_layout.py` 的 `_BLISS` 块与 `pad_bliss` 里的插入（函数随之改名 `pad_charopt`，它现在只做「去掉天梯行与提示条里的 X 经典版」，与极乐世界已无关）、`dm/ios/tools/gen_romfs_overlay.py` 的注释；`dm/i18n/ui_text.tsv` 的三行（`dmBlissTitle`／`dmBlissDesc`／`dmElyToaGround`）删掉后**重出** `dm/host/dm_i18n_tab.h`（`dm_i18n.py --header`），`dm_i18n.py --check` 复跑 exit 0（397 条）。
- 回归面：`dm/ios/tools/uireg/uireg.py` 的「e」局里两行勾选框断言与整个 v / v2 两局（都是为这个模式写的）删掉，`dm/ios/tools/uireg/affected.tsv` 五行的 `v` 标记去掉；`dm/host/tests/t_touch_mac.c` 与 `t_touch_tick_stub.c` 里的两个桩删掉；两个 `dm/host/README*.md` 的表行、`dm/i18n/literal_whitelist.tsv` 的行、`dm/host/Makefile` 的 `SRC` 一项；`dm_bossrush.c`／`dm_rift.c` 里提到这个模式的注释收口。
- **两次构建失败（都是我的编辑失误，已修）**：① 第一次把 `dm_cursor.c` 里那行「`uint64_t pl = …, pd = …` 声明 + 注释」整行替换成了注释，删掉了 `pl`／`pd` 的声明 → 编译报 `use of undeclared identifier 'pd'`；② 摘掉手柄路径的 Y 键翻勾时少留了一个右括号（那个 `}` 原本同时闭着「建角模式页」与外层两个块）→ 报 `function definition is not allowed here` / `expected '}'`。两次都按编译器的定位逐处修回（声明行从 HEAD 逐字取回，只去掉注释里对已删模块的指称；括号补回），第三次构建 exit 0。
- 宽口径复核 `git grep -n -i -e dm_elysium -e dm_fe_bliss -e bliss -e elysium -e '极乐世界' -- .`：除 `docs/HANDOFF*`、`docs/UPSTREAM_README*`（上游 D2R 产品说明，历史文档）与 `docs/TOTK_PORT_SCAFFOLD*`（计划表里「秘境/仓库/符文之语/极乐世界…与 TotK 无关，删除」那一行）外 0 命中。三个 Python 脚本用 `ast.parse` 验过语法。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 23:40 Asia/Shanghai — [TOTK] NA-013 裁剪批 7g（文字框注释颜色码）进行中

[BEGIN] na-013-textbox-trim

- 命令：`git rm dm/host/dm_textbox.c dm/host/dm_textbox_core.c dm/host/dm_textbox_core.h`、收掉观测门 14（`dm/host/dm.h` 的枚举 + `dm/tools/patch_nso.py` 的 OBS 表条目）、清掉 `diag.c` 的安装调用、`dm_runeword.c` 的对照表调用、单测 `t_textbox.c` 与 Makefile、`Makefile` 的 `SRC`、两个 README 表行、`uireg` 行，然后 `ci_checks.py` + `build.py --game-run --version trim-b12` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉文字框颜色码一族后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`31188dcf69cb7de62f8c45b985afa06fdbe0f197`
[END] na-013-textbox-trim

- 退出码：`build.py --game-run --version trim-b12` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,085,775 字节（2026-10-19 22:13:40；比 trim-b11 小 32,768 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_textbox.c`（挂观测门 14，在文字框「文字变了」入口按对照表改写颜色码）、`dm/host/dm_textbox_core.c` 与 `dm_textbox_core.h`（对照表的纯逻辑，`dm_runeword.c` 借它改写本地化串）。
- **观测门 14 两侧同收**：`dm/host/dm.h` 的枚举去掉 `OBS_TEXTBOX = 14` 且 `OBS_MAX` 19 → 18；`dm/tools/patch_nso.py` 的 OBS 表里 14 = `0xadc434` 那条一并去掉。只改一侧的话，宿主会撞 `gate_obs_set` 的「观测门编号越界」die（NA-007 摘 `dm_turnsmooth` 时已踩过一次）。
- 调用点：`dm/host/diag.c` 的 `dm_textbox_install` 安装行；`dm/host/dm_runeword.c` 去掉 `#include "dm_textbox_core.h"` 与对照表改写（`loc_tb` 改成原样透传 —— 符文之语清单的名字本来就不在表里，行为不变）。
- 生成器侧：`dm/ios/tools/annot_strings.py` 不再出那张对照表（`TEXTBOX_TABLE`／`apply_textbox`／`textbox_table`／`write_textbox_table` 与相关注释一起摘掉），`dm/ios/tools/gen_romfs_overlay.py` 里写表的调用也去掉；注释版串仍照旧写进字符串表。改后用 `ast.parse` 验过两个脚本的语法。
- 单测与清单：`dm/host/tests/t_textbox.c` 删除，`dm/host/tests/Makefile` 里它的编译规则与 `run:` 列表引用去掉；`dm/host/Makefile` 的 `SRC` 两项、两个 `dm/host/README*.md` 的表行、`dm/ios/tools/uireg/affected.tsv` 一行。**本机 NOT RUN**：`dm/host/tests/Makefile` 的 `run:` 目标（macOS clang + Cocoa）本机跑不了，被删的 `t_textbox` 未经本机执行验证；`ci_checks.py` 不覆盖该目录。
- 宽口径复核 `git grep -n -i -e dm_textbox -e OBS_TEXTBOX -e DM_TEXTBOX -- .`：除 `docs/HANDOFF*` 外 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b12`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 23:15 Asia/Shanghai — [TOTK] NA-012 裁剪批 7f（高价值掉落：光柱 / 落地音 / 震动）进行中

[BEGIN] na-012-dropoverlay-trim

- 命令：`git rm dm/host/dm_dropfilter.c dm/host/dm_drophaptic.c`、摘掉宿主调用 0x87/0x88 的登记行（中英各两条）、枚举两项与尾注、`hle_hostcall.c` 的两个 case、`patch_nso.py` 的两个剪口条目与六行注释、`front_ios.m` 的四行震动块、`drop_light.py`／`gen_romfs_overlay.py` 的注释、`dm_custom.h` 的键注释、`Makefile` 的 `SRC`、两个 README 表行、白名单行、`uireg` 两行，然后 `ci_checks.py` + `build.py --game-run --version trim-b11` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉高价值掉落一族后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`2043fb3e57d82382e0ae83bc35675db561830807`
[END] na-012-dropoverlay-trim

- 退出码：`build.py --game-run --version trim-b11` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,118,543 字节（2026-10-19 21:59:02；比 trim-b10 小 16,384 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_dropfilter.c`（掉落光柱 = 宿主调用 0x87，落地音 = 0x88）、`dm/host/dm_drophaptic.c`（高价值掉落震动）—— 这族是 29 个剩余模块里唯一不牵连 iOS 应用源码、中英表与单测的。
- 宿主调用四处收口：`dm/host/hle.h` 的 0x87/0x88 登记行（中英各两条）与枚举 `SVC_HOST_GROUND_ASSET`／`SVC_HOST_DROP_SOUND` 及枚举尾注；`dm/host/hle_hostcall.c` 的两个 case；`dm/tools/patch_nso.py` 的两个剪口条目（`0x468f2c`／`0x8fa590`）与六行注释。
- iOS 端：`dm/ios/Sources/front_ios.m` 第 408–411 行那四行震动块**必须**同批删 —— 它每帧调 `dm_drop_haptic_take`，留着 iOS 构建会链接不上。**本机 NOT RUN**：iOS 构建是 macOS 专用，本机编不了也测不了，这四行的删除只做了逐行检查。
- 其余引用点：`dm/ios/tools/drop_light.py`（两行注释：宿主侧改指规则已摘除，这些带光变体现在没人指向）、`dm/ios/tools/gen_romfs_overlay.py`（第 54 行注释）、`dm/host/dm_custom.h`（第 7／10 行键注释里的 `drop_light`／`drop_haptic` 条目；两个键本身仍留在 `dm_custom.c` 的 `k_keys` 位置数组里，与 `loot_filter`／`auto_buff`／`pot_pick` 同一处理）、`dm/host/Makefile` 的 `SRC` 两项、`dm/host/README.md` 与 `README.zh-CN.md` 的表行两行、`dm/i18n/literal_whitelist.tsv` 的 `host/dm_drophaptic.c` 行、`dm/ios/tools/uireg/affected.tsv` 两行。
- 宽口径复核 `git grep -n -i -e dm_dropfilter -e dm_drophaptic -e dm_drop_haptic -e DM_DROP_LIGHT -e DM_DROPF_LOG -- .`：除 `docs/HANDOFF*` 外 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b11`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

## 2026-10-19 22:55 Asia/Shanghai — [TOTK] NA-011 裁剪批 7e（进局落在城镇小站旁）进行中

[BEGIN] na-011-townwp-trim

- 命令：`git rm dm/host/dm_townwp.c`、摘掉宿主调用 0x8a/0x8b 的登记行（中英各两条）、枚举两项、`hle_hostcall.c` 的 case、`patch_nso.py` 的两个剪口条目与注释、`diag.c` 的调用行、`Makefile` 的 `SRC`、两个 README 表行、`uireg/affected.tsv` 的行、`uireg.py` 的说明块与 `OLD_SPAWN` 免跑表、`touchcases/no_move_taps/script.txt` 的注释，然后 `ci_checks.py` + `build.py --game-run --version trim-b10` + `agent_handoff_check.py --verify`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：摘掉进局落点规则后 `ci_checks` 10/0、完整构建仍产出 APK
- 日志路径：本文件对应 [END] 记录
- 回滚点：`dec728845774b611daf53f638f28ecf5b369049d`
[END] na-011-townwp-trim

- 退出码：`build.py --game-run --version trim-b10` exit 0
- 产物：`dm/android/build/D2R-Android-port.apk`，19,134,927 字节（2026-10-19 21:48:56；比 trim-b9 小 16,384 字节）
- 结果：SUCCESS
- 备注：`ci_checks.py` 与 `agent_handoff_check.py --verify` 的结果见本条目下方的证据行

证据（本条目对应的命令与退出码）：

- 删除：`dm/host/dm_townwp.c`（进局落在城镇小站旁，宿主调用 0x8a/0x8b）。
- 宿主调用四处同步收口：`dm/host/hle.h` 的 0x8a/0x8b 登记行（中英各两条）与枚举 `SVC_HOST_JOIN_SPAWN`／`SVC_HOST_JOIN_CORPSE`；`dm/host/hle_hostcall.c` 的 case；`dm/tools/patch_nso.py` 的两个剪口条目（`0x5d8040`／`0x5d8400`）与四行注释。
- 其余调用点：`dm/host/diag.c` 的 `dm_townwp_tick` 调用行、`dm/host/Makefile` 的 `SRC` 一项、`dm/host/README.md` 与 `README.zh-CN.md` 的表行、`dm/ios/tools/uireg/affected.tsv` 的 `dm/host/dm_townwp*` 行。
- **环境变量名不含模块名**：按模块名 grep 抓不到 `DM_TOWNWP_OFF`，宽口径复核（`git grep -n -i -e townwp`）又抓到三处并清掉：`dm/ios/tools/uireg/uireg.py` 的说明块与 `OLD_SPAWN` 免跑表（那批局靠 `DM_TOWNWP_OFF=1` 免掉产品落点，特性摘除后这个开关无人消费，删掉行为等价）、专门验该特性的 "wp" 回归局、`dm/verify/shotgate_pages/automap.json` 与 `warlock_camp.json` 里那个只剩这一项的 `env` 块（两个 JSON 改后用 `json.load` 验过合法，`uireg.py` 用 `ast.parse` 验过语法）。
- `dm/verify/touchcases/no_move_taps/script.txt` 第 3 行的坐标位移（8 下右移 600 / 上移 450）是为「进局落在小站上」做的 D2R 产品测量；出生点规则摘除后落点回到原版，这两处位移是否要撤属 D2R 产品侧判断，本机（无 macOS / 无 D2R 真机）无法验证，故**只改注释写明现状**，坐标数字保持不动，待 TotK 侧重做用例时重新量。
- 宽口径复核 `git grep -n -i -e townwp -- .`：除 `docs/HANDOFF*` 与上述那条写明现状的注释外 0 命中。
- `dm\android\tools\build.py --game-run --version trim-b10`：exit 0，产物同上。
- `dm\android\tools\ci_checks.py`：提交后在干净树上复跑 exit 0，10 项通过 / 0 项失败。

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