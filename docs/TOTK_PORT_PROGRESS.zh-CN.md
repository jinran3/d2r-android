# TotK 移植进度

更新日期：2026-10-20。此文件随工作更新，是中断后继续移植的入口。

路线图与分阶段验收门见 [TotK 移植脚手架计划](TOTK_PORT_SCAFFOLD.zh-CN.md)（下称「计划」）。

交接入口见 [TotK 移植交接文档（HANDOFF）](HANDOFF.zh-CN.md)。

- 目标设备：一加 12（Snapdragon 8 Gen 3 / **Adreno 750** / Android）
- 起点：fork 自 `sydeEvans/d2r-android`（HEAD `5d8e322`），上游是 `jhaizhou-ops/d2r-mobile`
- 分支：`totk/scaffold`（`main` 保持 D2R 可构建，不混入 TotK 工作）

## 当前状态（继续开发先看这里）

**2026-10-22 07:06（Asia/Shanghai）—— 交接点：更新包（本体 + v1.4.2 补丁）已产出，设备前的 7 条闸门在它上面全绿 → 可以推机。**
- **NA-050**：overlay 合进宿主包完成 → 更新包 `D:\Switch\totk-work\package-totk\totk-package-updated.zip`
  （**17,825,708,024 字节 / 328,788 条目** = game 9 / romfs 304,243 / shaders 24,535；替换 14,397、删除 727）。
- **NA-051**：完整预检 **exit 0，7 条全绿**，结论行是「全绿 → 可以推机」。
- **代码与数据现在是同一次构建**（此前不是）：包里 `game/` 的模块改自**更新**（v1.4.2）的 `main` NSO，
  数据侧也是 v1.4.2 → 「v1.4.2 代码 + 本体数据」的错配已消除。
- 细节见下面「9.5 NA-050/NA-051」一节；**下一件事只有一个**：NA-052 把「推包→导入→开机→读日志」一键化并写 runbook，
  手机回来后立刻做 NA-044 真机推包开机。
下一次接手先读 [交接文档（HANDOFF）](HANDOFF.zh-CN.md) 的「当前快照」与「下一步唯一动作」。


**2026-10-21 04:30（Asia/Shanghai）—— 交接点：设备前的静态闸门全绿，可以推机；真机验证全部待做。**
下述 NA-037 ~ NA-043 的条目是本会话完成的（接口面对齐、接口覆盖清零、歧义控制键的解法、预排布贴图、包重建、
M4 核对、预检脚本）；**下一件事只有一个**：手机接上后按交接文档 NA-044 的步骤推包开机。
下一次接手先读 [交接文档（HANDOFF）](HANDOFF.zh-CN.md) 的「当前快照」与「下一步唯一动作」。


**2026-10-21（最新）：NA-042 / NA-043 —— 真机预检脚本（「可以推机」的带证据结论）；把变体挑选的运行期假设写清。**

- **预检脚本**：`dm/android/tools/totk_preflight.py` 一条命令跑完 7 条设备前的闸门
  （APK、数据包清单、着色器包、变体键链、NVN 接口覆盖、`ci_checks`、交接校验），
  每条打印**命令 + 退出码 + 证据行**，最后给出结论：`没有红项、有 1 项黄 → 可以推机`。
  变体键链那条要重解析归档（约 5 分钟），`--quick` 可跳过（跳过时记黄项 ✓）。
- **变体挑选的运行期假设（静态推断，未真机确认）**：游戏的着色器表是 `{程序地址, …, 控制段地址, …}`，
  调 NVN 时传 `{data = 程序地址 + 固定偏移, control = 控制段地址}`；NVN 的 `data` 就是「着色器数据（程序）」。
  ⇒ 程序最可能在 **`data`** 或 **`data - 程序偏移`**（代码区头在程序前面）这两处 —— 宿主按这个顺序先试，
  另有三个兜底位置（`data + 偏移`、`控制段 + 0x880`、`控制段 + 0x880 + 偏移`）。
  宿主还会**统计命中与退回的次数**并打日志：第一次真机跑就能知道这条路通不通、通的是哪一处。
- **本批 NOT RUN**：真机（手机断开）。

**2026-10-21（最新）：NA-041 —— 真机前的准备做完：包重建（16.62 GiB）、M4 的「TotK 专属部分」核对结果是「本来就是通用的」。**

- **数据包重建**：`totk-package.zip` = **16.62 GiB**（game 9 / romfs 304,207 / shaders **24,535**，着色器部分 646 MB），
  含 5,534 个控制段键 + 5,913 个变体完整键 + 1,640 份变体名单。旧的包留成 `totk-package-old.zip`。
- **M4 的「TotK 专属部分」核对结果**：读代码后发现大部分**本来就是通用的**，不需要为 TotK 重写：
  ① **触控**：布局是**虚拟手柄**（左摇杆 / 右四键 / 左肩 / 右肩 / 方向键 / 功能键），不是 D2R 的 HUD 坐标；
     按键语义（A/B/X/Y、ZL/ZR）与 Switch 一致 → TotK 直接可用，**只需真机校准手感**。
  ② **存档**：`DM_SAVE` 指向一个通用目录，档名由游戏自己定 → **不用改**（D2R 与 TotK 的存档文件自然不同名）。
  ③ **音频**：AAudio 路径是通用的（采样率/声道由游戏的请求决定）→ **只需核对**。
  ④ **手柄映射**：`hle_hid.c` 的轴/扳机映射是通用的（D2R 与 TotK 都是 Switch 系）→ **只需核对**。
- **绑定容量的静态核对**：TotK 着色器每个阶段的绑定数最多 —— UBO 9、SSBO 8、贴图 21、图像 0，
  都在宿主的容量之内（UBO/SSBO 每阶段 16、贴图 128、c[2] 合并表 32 槽）✓。
- **本批 NOT RUN**：真机（手机断开）。

**2026-10-21（最新）：NA-039 / NA-040 —— 补齐最后 5 个空实现；把「1,640 个歧义控制键」查清并做成运行期可解；接上预排布贴图数据。**

- **NA-039：5 个空实现补成真实现**（此前是 `g_nops`，TotK 调它们）：
  ① `nvnCommandBufferWaitSync`（**98 次调用，最要紧**）：录下同步对象的栅栏值，回放时在 Vulkan 侧等到该栅栏
     （D2R 保留原来的空实现 —— 它已在真机上跑过，不改它的行为；切换用启动设置本来就写的 `DM_GAME_PROFILE`）。
  ② `nvnCommandBufferDispatchComputeIndirect`（3 次）：新增录制 op，回放时读客体内存里的计数并做一次直接派发
     （同一提交内刚写好的计数读不到 → 记进待真机确认项）。
  ③ `nvnCommandBufferSetDepthBounds`（15 次）：宿主没开深度夹取 → 按不夹取执行，报一次红而不是静默吞掉。
  ④ `nvnCommandBufferSetShaderScratchMemory`（2 次）：宿主没有着色器局部内存 → 报一次红。
  ⑤ `nvnWindowFinalize`（2 次）：交换链与计数清零、对象作废。
  → **覆盖率：TotK 调用的 213 个接口，缺实现 0、空实现 0**（`dm/gfx/tools/nvn_coverage.py --check` exit 0，已接进 `ci_checks`）。
- **NA-040：把「1,640 个歧义控制键」查清并解决**（这是 M3 最大的一个坑）：
  - **量化**：1,640 个控制键覆盖 5,913 个着色器出现次数；按「多数派选一个变体」→ **4,273 次（43.6%）会用错 SPIR-V**。
    也就是说：控制段本身分不出变体，光靠「控制段哈希」这一个键，**近一半的着色器拿到的都是别人的机器码**。
  - **关键代数（已静态证明）**：流水线键 = `sha256(控制段 + 机器码 + c1)`；宿主运行期算
    `sha256(控制段前 0x880 字节 + 机器码 + c1)` —— 控制段恰好就是 0x880 字节，机器码与 c1 在代码区里首尾相接，
    **两边哈希的字节完全一样**。新工具 `dm/gfx/tools/totk_variant_keys.py` 重解析归档里 47,260 个着色器，
    逐个核对：键不一致 0 个、c1 不一致 0 个、控制段长度不一致 0 个 ✓。
  - **包里现在同时存两套键**：控制段键（5,534 个，兼容原来的宿主）+ 变体完整键（5,913 个），
    外加每个歧义控制键一份 `<控制键>.variants` 名单。
  - **宿主运行期挑变体**：读控制段里的代码描述字段（c1 偏移 +0x700、指令区总长 +0x704、程序偏移 +0x708），
    在四个「机器码可能在哪」的位置各试一次（客体的 data 地址、data 减程序偏移、控制段后面、控制段+0x880+偏移），
    算出完整键去名单里找；命中就用那个变体，挑不到就退回控制段键（多数派变体）并在日志里说明
    —— **第一次真机跑就能从日志看出运行期的实际布局**。
  - D2R 不受影响：它的包里没有 `.variants` 文件，这条路根本不会进。
- **预排布贴图数据接上了**：`nvnTextureBuilderSetPackagedTextureData` 之前被忽略（只报红），
  游戏用这条路建的贴图会没有内容。现在 builder 记住指针、`nvnTextureInitialize` 用它当贴图来源，
  走的是宿主已有的「读内存 → 解排布 → 上传」那条路（D2R 不调这个接口，行为不变）。
- **本批 NOT RUN**：真机（手机断开）。变体挑选是否命中、预排布贴图是否正确，都只有静态依据。

**2026-10-21（最新）：NA-038 —— 把 TotK 真正调用、而宿主还接报红桩的 NVN 接口全部补齐（缺口 103 → 0）。**

- **补齐范围**：按 `dm/gfx/tools/nvn_coverage.py` 的清单逐个实现（分 a/b/c 三批），每批都过完整构建：
  ① **缓冲族**（`nvnBuffer*`，16 个）：缓冲 = 内存池里的一段，宿主直接用游戏给的真实内存 →
     映射返回池首地址 + 偏移，刷新 / 失效是空操作（写已经落到真实内存）。
  ② **绘制**：`nvnCommandBufferDrawElements` / `DrawElementsBaseVertex`（走已有的 `OP_DRAW_IDX`）、
     `DrawArraysInstanced`（`p_draw` 载荷加上实例数与首实例，Vulkan 侧 `vkCmdDraw` 带上；Metal 侧忽略，D2R 不用）。
  ③ **句柄与绑定**：`nvnDeviceGetTexelFetchHandle`、`nvnCommandBufferBindImage` / `BindSeparateTexture` / `BindVertexBuffer`。
  ④ **整数清除**：`nvnCommandBufferClearColori` 的原始位进清除载荷，Vulkan 侧按目标格式取用（原来只有浮点清除）。
  ⑤ **各类查询**：贴图构建器 / 贴图 / 贴图视图 / 采样器 / 状态对象的 getter，内存池的 getter，调试标签，
     以及命令缓冲上剩余的开关（保守光栅、tiled cache、viewport swizzle、ZCull 数据、transform feedback 等）。
- **返回值是「不透明结构体按值返回」的接口**（`NVNmemoryPool`、`NVNmemoryPoolFlags`）改成不做签名检查、按 64 位返回：
  头文件把它们建模成 96 / 256 字节结构体（按值返回会走间接返回约定），而游戏那边拿到的是寄存器里的普通值。
- **明确留着「不做处理」的**（代码里都写了理由）：虚拟内存池映射（宿主没有虚拟地址空间 → 明确失败）、
  CPU 写贴图（宿主还没有这条上传路径 → 报红）、预排布贴图上传、条件渲染（一律渲染）、
  保守光栅、tiled cache、transform feedback。
- **闸门**：`dm/gfx/tools/nvn_coverage.py --check` exit 0（取址缺口 **0**、缺实现 **0**、空实现 5），
  并接进 `ci_checks.py` 作为常设闸门；`build.py --game-run --version trim-b33` exit 0。
- **本批 NOT RUN**：真机（手机断开）。合并句柄拆分、整数清除、实例绘制都只有静态依据，要等真机出图确认。

**2026-10-21（最新）：NA-037 —— TotK 的 NVN 接口面对齐：查出会直接崩的取址缺口、补 13 个新接口、给出 103 个实现缺口清单。**

- **★ 查出一个会直接崩的坑**：TotK 的 main 取址 **534 个** NVN 接口名（`dm/gfx/nvn/nvn_names_totk.txt`），
  其中 **13 个宿主的名字表里没有** → `nvn_lookup` 返回 NULL → 客体拿到空函数指针 → 开机即崩。
  这 13 个是 D2R 那一代 NVN 里没有的新接口（延迟绑定、子块尺寸、视图偏移、provoking vertex、自动检查点掩码等）。
- **名字表补齐**：`dm/gfx/nvn/names.txt` 变成 536（D2R 的 523 个顺序不动、槽索引不变；TotK 独有的 13 个追加在末尾），
  `nvn_thunks.S` / `nvn_count.h` / `nvn_protos.h` 重新生成。新增 `dm/gfx/tools/nvn_table.py`：
  **只靠名字表就能重建跳板与计数表**（原来的 `gen_protos.py` 需要仓外的 Nintendo `nvn.h`）；
  先验证它能把改动前的三个文件逐字节复现，再扩表。
- **自动定位取址函数**：新增 `dm/gfx/tools/nvn_slots_auto.py`（不写死地址，认得 D2R 与 TotK 两种加载函数形态）→
  出「名字 / 槽 / 调用点」表；TotK 的取址函数在 `upd_main.img` 的 `0xbbfac0`。
- **13 个新接口落地**（`dm/gfx/nvn/hle_nvn.c`）：6 个延迟绑定直接转调对应的普通绑定；其余是 no-op 或返回 0
  （视图偏移 / 子块尺寸这两个查询**不写出参**，免得写错地址）。
- **合并贴图绑定**：`nvnCommandBufferBindTextures` 此前是报红桩（D2R 不调，TotK 调 **260 次**）→
  按合并句柄（纹理 ID 低 20 位 + 采样器 ID 第 20..31 位）拆成贴图 / 采样器两条绑定记录，
  与后端「合并档位」的重打包对上（D2R 不调用这个函数，D2R 行为不变）。
- **缺口清单**：静态扫描 TotK main 的 .text（`adrp 槽页; ldr [xN,#off]; ldr [xN]; blr xN` 这种间接调用）
  → TotK 真正调用 **213 个**接口（`dm/gfx/nvn/nvn_calls_totk.tsv`），宿主已实现 **110** 个，**还缺 103 个**
  （`dm/gfx/tools/nvn_coverage.py` 可复查）。缺口最大的：`nvnBufferFlushMappedRange`(132)、
  `nvnCommandBufferDrawElementsBaseVertex`(103)、`nvnDeviceGetTexelFetchHandle`(103)、`nvnCommandBufferWaitSync`(98)、
  `nvnCommandBufferSetRenderEnableConditional`(60)、`nvnMemoryPoolInvalidateMappedRange`(55)、
  `nvnCommandBufferClearColori`(39)、`nvnCommandBufferBindImage`(29)。
- **本批 NOT RUN**：真机（手机断开）；合并句柄拆分的正确性目前只有静态依据，要等真机出图才能确认。

**2026-10-20（最新）：NA-034 收口 —— c[2] 布局按档位可选并在真机验证；驱动选型真机实测收口；查出着色器键口径的新拦路虎。**

- **c[2] 句柄表布局按游戏档位可选**：TotK 的贴图句柄在 `c[2][0x20 + 8r]`（合并句柄，32 槽），D2R 在 `0x168 + 8r`（分离贴图）。
  宿主此前只认 D2R 那三段 → **TotK 上一个贴图都绑不上**。现由 `dm/android/native/nvn_c2_layout.h` 按 `DM_GAME_PROFILE` 选，
  启动设置的 `game_profile=d2r|totk` 写入该变量；**D2R 路径逐字节不变**。
- **真机验证**：一加 12 上 `vulkan-test` **全绿 exit 0**（含新增的 c[2] 双布局用例），`launch-settings-test` PASS（58 cases）。
- **驱动选型收口**：实测系统 Vulkan = **Adreno 750 硬件驱动**（Vulkan 1.3.128、driver 0.762.41、**subgroup 64**）；
  内置 Turnip 是 T30/830 构建且 `.so` 里**没有 `vk*` 导出**，装不上 → **走系统驱动**。新增工具
  `dm/android/tools/vulkan_probe.c` + `run_vulkan_probe.py`（以后驱动问题一律实测，不再猜）。
- **顺带修好三处既有的真机测试缺陷**（用 stash 对比确认是既有问题，与本批无关）：三处都断言了精确的内部计数器增量，
  而那些量随构建与 GPU 变；同批的像素断言全过。现改成断言真正要保的契约。
- **★ 新拦路虎**：宿主按 `sha256(控制段)` 找 SPIR-V，而 **TotK 的控制段不唯一**（1,640 个控制键对应多种机器码，
  最多的一个 47 种）→ 同一控制键的变体会共用一个 SPIR-V，**渲染必错**。下一步 NA-035：宿主键改成
  `sha256(控制段+机器码+c1)`，与流水线口径逐字节一致。

**2026-10-20（最新）：NA-033 —— SPH 解析完，§4.4 收口；顺带查出真机渲染的头号拦路虎是 c[2] 布局。**

- **SPH 解析完**：图形着色器的 SPH 是 **0x50 字节**（在 0x30 字节 NVN 头之后；此前「前 0x30 字节是 SPH」的说法有误）。
  字段按仓内 vendored Ryujinx 的 `Translation/ShaderHeader.cs` 逐位解出；**9,807 个着色器全部解析成功，
  stage 字段与归档里的 kind 100% 一致**（vs 4,232 / ps 5,557 / cs 18）。
- **SPH 里没有贴图维度类型、也没有图像格式**；NVN 着色器控制头里也没有按槽的描述符表
  （9,807 个控制头只有 86 种固定布局）。
- **但贴图维度多半本来就不需要事实表**：Ryujinx 自己的翻译器就是从机器码的贴图指令取维度
  （TEX/TLD/TLD4/TMML/TXD 用第 28..30 位 `Dim`，TEXS/TLDS 用第 53..56 位 `Target`）；
  `QuerySamplerType`（我们用事实表作答的那个）**只在 TXQ 纹理查询、buffer 贴图判定、bindless 三处被调用**。
  实测 TotK **只有 26 个着色器用 TXQ**，且没有 1D / buffer 贴图 → **按缺省（2D）译出来的着色器库，维度本来就是对的**。
- **从 SPH 真正拿到的新事实是顶点属性的分量类型**（`ImapTypes`：Constant = 整数属性）：
  **4,206 个顶点着色器有属性事实，1,204 个属性槽是整数属性**（D2R 侧 PC 反射的比例是 7.8%，量级一致）。
  新增工具 `dm/gfx/tools/totk_facts.py` 出表（表落仓库外：`D:\Switch\totk-work\xlate-full\shader_facts_totk_v2.tsv`）。
- **★ 头号拦路虎（比事实表要紧）**：**TotK 与 D2R 的 c[2] 布局不同**，宿主把 D2R 的写死了 ——
  D2R 用分离贴图 `c[2][0x168 + 8r]` + 分离采样器 `0x568 + 8r`；**TotK 用合并句柄，落在 `c[2][0x20 + 8r]`（32 槽）**。
  宿主的 `nvn_vulkan_handles.inc` 只认 0x168/0x568/0x120 三段 → **TotK 的贴图句柄全读成 0，一个贴图都绑不上，画面必然是黑的**；
  翻译器 `dmsh_xlate/Program.cs` 的 `TexSlot()` 也用死值 `TexBase = 0x168`，事实表槽号也算不对。

**2026-10-20（最新）：§4.4 的最后一块补上了 —— 9,807 个 TotK 着色器全部翻成 SPIR-V，0 失败。**

- **根因**：之前那 3 个 `IndexOutOfRangeException` 不是翻译器的 bug，是**喂进去的机器码漏了图形着色器开头 0x30 字节的 SPH（描述符头）**。同一个作业只换 `code` 字段：去掉 SPH → `0 成功 / 3 失败`；带上 SPH → `3 成功 / 0 失败`。D2R 侧早就写着同一条规则（`dmsh_build.py`：`code = code[0x30:]` 是「丢掉记录头、留下 SPH + 指令」）。**教训**：TotK 的作业必须直接指向 `totk_shaders.py` 产出的 `code/<键>.bin`。
- **结果**：新增仓库工具 `dm/gfx/tools/totk_xlate.py`（索引 → 事实 → 作业 → SPIR-V → 统计一条命令），6 分片并行约 55 分钟跑完，**9,807/9,807 成功**（SPIR-V 539,816,056 字节，`res.json` 9,807 个，逐个校验魔数 `0x07230203` 全部合法）。
- **事实表（方案 A）**：18 个计算着色器的线程组与共享内存来自控制头 0x748；其余 9,789 个键按缺省作答（2D / R8G8B8A8Unorm / float）。**事实表留在仓库外**（仓库纪律：游戏内容与由它生成的表不进仓库），仓库里只留工具。
- **新的线索（下一步 NA-033）**：**SPH 从来没被解析过**。已抓到 4 个样本的头 12 个 u32（`02060461` / `06060461` / `00065462` 三种 word0，word6/word7 疑似描述符计数，`0x80000000` 疑似「无描述符」标志）—— 里面有没有**贴图槽 → 维度类型 / 图像槽 → 格式 / 属性与输出 → 分量类型**，就是 NA-033 要查的；查不到就按方案 A 收口。
- **真机**：一加 12 已接（`3b864e51` / PJD110 / Android 16 / Adreno 750），APK 装好、启动器界面能渲染、驱动能切「内置 Turnip」。**但内置 Turnip 在 750 上能不能用还没定**：它是 T30/Adreno 830 构建，而本机解析该 `.so` **没有任何 `vk*` 导出符号**，宿主却是 `dlsym(driver, "vkGetInstanceProcAddr")` 取入口 —— 加载方式要查清（计划 §4.5）。
- 另：本体 RomFS 全量解包本会话**主动暂停**（让出磁盘 I/O 给翻译与构建），`switch_nca.py romfs-extract` 可断点续跑。


**2026-10-20（再晚）：§4.4 的着色器事实表来源有解了；宿主的 HLE 面几乎不用改。**

顺着用户指出的 `catoncat/d2r-port-radar` 雷达，找到了一个**已经能读档游玩的 TotK 移植**（`OJZen/totk-mobile`，Mac/iOS，v1.4.3，Apache-2.0，内核基于 d2r-mobile 的 MIT 部分）。只读它的做法（代码自己写，许可不兼容不能搬），两件事落地：

1. **§4.4 风险基本解除**：任天堂的 zstd 字典**就在游戏自己里** —— `/Pack/ZsDic.pack.zs` 是个 SARC，装着 3 份 128 KB 字典（id 1/2/3），着色器包的 zstd 帧头写明自己要 id=1。之前「Dictionary mismatch」的死结由此解开：全部 13 个着色器包都解开了（`ApplicationPackage...sarc.zs` → SARC 19 个条目；12 个 `*.bfsha.zs` → FSHA 容器），条目里带 `cTexSrc` / `gl_InstanceID` 这类**反射元数据**。所以 D2R 那条「从 PC 版反射冻结事实表」的路对 TotK 不成立，而**从游戏自带归档取**成立（方案 D 可行）。下一步是把 FSHA / BNSH 的结构摸清、产出事实表、接进翻译链。
2. **HLE 面几乎不用改**：TotK 三模块的未定义导入 1,266 个，宿主已有的 HLE 表（173 条）覆盖 66 个，**真正缺的只有 8 个 `glslc*`**（NVIDIA 运行时 GLSL 编译器 API，D2R 没有）；宿主的未实现桩是良性的（记日志、返回 0，不中止），所以符号层不动宿主。58 个 svc 号里宿主有 case 的 34 个，缺的 24 个多是 Horizon IPC（ConnectToNamedPort / SendSyncRequest / CreateSession / CreatePort …），而 D2R 宿主是直接接管服务客户端函数、不走 IPC，所以真机上的实际缺口预计远小于 24 个。

3. **着色器事实表的边界摸清了**：能直接拿到的是「键 / 阶段 / 机器码 / C1 / 计算着色器的线程组与共享内存」；**贴图维度 / 图像格式 / 属性分量类型不在着色器里**（控制头无描述符表），要靠游戏数据或运行期观测。翻译链我们自己已有（`dm/gfx/tools/dmsh_xlate` + 仓内 Ryujinx C#，MIT），缺项按缺省、输出 SPIR-V(Vulkan)，本机正装 .NET 10 SDK 准备编出来。
4. **着色器事实表的第一半已拿到**：归档结构摸清了（每个着色器 = 控制头 0x98761234 + 机器码 + C1；键 = `sha256(control+program+c1)[:16]`；阶段在控制头 kind 字段）。`/Shader` 归档里 **9,807 个唯一着色器键**（cs 18 / ps 5,557 / vs 4,232），**计算着色器的线程组与共享内存直接从控制头 0x748 读出**，不需要 PC 反射；贴图维度 / 图像格式 / 属性分量类型的位置还在找。

5. **着色器路线在本机跑通了**（§4.4 风险解除）：本机装 .NET 10 SDK 后把仓内的翻译器（`dm/gfx/tools/dmsh_xlate` + 仓内 Ryujinx C#，都是 MIT）编出来，TotK 的 Maxwell 机器码 → SPIR-V（Vulkan 口径）实测成功（200 个作业 190 成功 / 10 失败，去重后 126 个唯一键只 3 个失败）；事实表为空时按缺省即可，不需要 PC 版反射。翻译器补了三处**作业驱动**的 TotK 适配（深度 -1..1、宿主不支持 fp64 与深度裁剪控制、顶点-像素联编），D2R 行为未变。

另外：模块来源已接到规则域上（`make_package.py --ruleset totk-run-v1 --exefs <目录> --modules-only` exit 0，产物形态与数据包一致），宿主的同款解析读出 33,855 符号 / 36,745 重定位 / 1,353 导入。


**2026-10-20（再晚）：TotK 的三个模块能打成宿主可装载的 ELF 库，宿主解析读数一致。**

`dm/android/tools/totk_modules.py` 把「改写（`DM_RULESET=totk-run-v1` + `DM_TARGET=android`）→ `guest_elf.py` 打包 → 照 `dm/android/native/game_modules.c` 复刻宿主解析」串成一条命令。实测：main / sdk / subsdk0 三个库 61.8 / 13.0 / 6.8 MB，宿主解析读出 33,855 符号 / 36,745 重定位 / 1,353 导入（与离线统计对得上）。

**M1 的第一个缺口已经具体化**：跨模块未解析的导入只剩 9 个符号，全是 NVIDIA 的 `glslc*`（运行时 GLSL 编译器 API）。D2R 没有这个需求；宿主的未实现桩能兜住，不挡装载，但真机上要用 `DM_HLECOUNT` 盯它有没有被调用——它同时是「TotK 存在运行时 GLSL 编译路径痕迹」的旁证（主流程仍用预编译的 `*.bfsha.zs` 着色器包）。

真机装载与进 `nnMain` 仍 NOT RUN（一加 12 未接）。


**2026-10-20（晚）：规则域接上 TotK，宿主门面清单拿到；上游同步机制落地。**

NA-028 把 `dm/tools/patch_nso.py` 的 `DM_RULESET=totk-run-v1` 钉到实测的四个构建号，CUTS / OBS / PARAMS 给 TotK 登记空表；改写器对 TotK 四个模块全部 exit 0，产出第一份 TotK 改写映像与门清单：

| 模块 | 改写结果 | 门 |
| --- | --- | --- |
| main | 814 处 TLS 读 | 0（TLS 走槽，不进门） |
| sdk | 2 TLS 读 / 124 TLS 区读 / 3 TLS 写 / 43 计时器 / **58 个 svc** | 101（58 svc + 42 cntpct） |
| subsdk0 | 无 | 0 |
| rtld | 6 个 svc | 6（与 sdk 重叠） |

**宿主服务面**：58 个不同 svc 号（1–29、31、33–35、37–42、44、45、47、50–54、64、65、67–69、75、80–82、112、114），比 D2R 的 264 处强制接管小一个量级 —— 这张表就是 M1 要补的 HLE 缺口清单。

**一个必须记住的前提修正**：TotK 的 main 把 **x18 当普通寄存器**用（24,204 条指令提到 x18、18,572 条提到 w18），D2R 改写器「x18 = TLS 指针」的语义前提对它不成立。好在上游那套机制实质是「每线程把客体 x18 存进线程槽」，对普通寄存器一样成立；而 Android 宿主本来就保全 x18（`dm/android/native/probe.c` 每次宿主调用前后都比对），所以 **TotK 规则域不做 x18 改写、宿主侧不用改**。

NA-029 按用户要求同步了上游 `jhaizhou-ops/d2r-mobile`：其 `main` 的 `patch_nso.py` 已比本 fork 新（283 行差异），差异分三类（D2R 玩法剪口 / 我们的 Android 改造 / 可用的上游改进），只采纳了第三类里的 **#55 寄存器字段预筛**，并用「TotK main 上按上游口径复核：漏 0、多 0」+ 仓库自带 `dm/android/tests/test_rewriter.py`（unicorn 等价性，exit 0）双重验证。规则已写进 `AGENTS.md` 第 11 条。


**2026-10-20：TotK 文件已备好，M0 勘察表填完（计划 §8 第 2 步完成）。**

用户提供了 TotK v1.4.2 的合并 XCI（本体+更新，`0100F2C0115B6000`，17,677,626,368 字节）与 `prod.keys`。本机原先没有 `hactool`，从上游发布版取了 1.4.0 win-x64；但**它解不开更新包的 NCA3 BKTR 补丁段**（`Invalid BKTR layout!`），所以按它的算法重写了一套纯 Python 的读法：

- `dm/tools/switch_nca.py` —— 读 NCA3 头（`header_key` 的 AES-XTS）、段（KAK 的 AES-CTR）、PFS0 / ExeFS、RomFS（IVFC + 目录树），可列 / 可取文件。只依赖 pycryptodome + numpy。本体 ExeFS 与 hactool 的输出逐字节一致。
- `dm/tools/nso_stats.py` —— NSO 段布局、构建号、MOD0 动态表、动态符号 / 重定位 / 导入 / NEEDED 统计。

实测结果（计划 §3 的表已按此填好）：

| 项 | TotK v1.4.2 实测 |
| --- | --- |
| 模块 | main 45.77MB / sdk 6.69MB / subsdk0 3.50MB / rtld 9.5KB（text） |
| 构建号 | main `5cb42b1cf25469fb0635fd046453d843`、sdk `5cf080e800530a7f25bd528ec875c27b`、subsdk0 `3308c1d216f788397d1451c8345a16cd`、rtld `82a3cf78789f9d9858c52379d8d2d129` |
| 动态符号 / 重定位 / 导入 | 33,858 / 36,747 / 1,356 |
| NVN 取址函数 | 534（加载函数 main 0xbbfa90–0xbc3510，槽是间接指针表） |
| RomFS | 304,207 个文件 / 15.87 GB |
| 着色器包 | 13 个 / 14.3 MB，`*.bfsha.zs` + `ApplicationPackage...sarc.zs`，zstd + 任天堂字典的编译包（字典本机没有） |

**§4.4 的结论（到目前为止）**：D2R 那条「从 PC 版着色器反射冻结事实表」的路对 TotK **确定不可用**（没有 PC 版）；TotK 自带的着色器包是**编译后的** BFSHA / SARC，不是反射表 —— 能不能从里面反推维度 / 格式，要等能解码（任天堂 zstd 字典）才知道。走方案 A（全默认 + 统计补齐）+ 方案 B（运行期在 `hle_nvn.c` 里观测 `nvnTextureBuilderSetDims` / `SetFormat` / `DispatchCompute` 反填）仍是主线。

**下一步**：NA-028 —— 裁剪批 6 + §4.3 接 TotK（`patch_nso.py` 的规则域按上面四个真实构建号取表 + 摘 D2R 的 CUTS/OBS 表 / `casc_overlay.py` / iOS 资产管线）。仍卡在用户材料：一加 12 真机。


**2026-10-19：纯 Windows 工具链端到端打通，APK 真实构建成功。**

用户明确要求不使用 Ubuntu/WSL、纯 Windows 开发。上游 README 的「构建脚本当前面向 Linux x86_64」
经实测只是集中式硬编码，不是硬限制。三项验收全部达成：

| 命令 | 结果 |
| --- | --- |
| `bootstrap.py` | 5 个工具包全部下载并通过 SHA-1 校验，exit 0 |
| `build.py --game-run` | **`dm/android/build/D2R-Android-port.apk`，18.6 MB，77 条目，zip 完整性 OK，9 个 ARM64 原生库（含 5.7 MB 的 `libdmandroid.so` 宿主本体）**，exit 0 |
| `ci_checks.py` | **8 项通过 / 0 项失败**（改动前 5/0，且两个 Java 闸门被误判为环境缺失而跳过） |

164 个 Python 文件语法 0 错误。新增 `dm/android/tools/host_env.py` 收敛全部宿主平台差异。

**这轮真实抓到的 bug（全部是跑起来才暴露，不是推测）：**

1. **`os.O_BINARY` 缺失静默损坏所有工具链二进制** —— Windows 的 `os.open` 默认文本模式，
   CRT 把 `0x0A` 翻成 `0x0D0A`。实测 200000 → 200452 字节，多出的 452 个 CR 恰等于 LF 数；
   换不含 `0x0A` 的数据或用 `open('wb')` 就完好 —— 所以只在含换行的文件上失败，极难定位。
   前两次 `bootstrap.py` 报的 "checksum mismatch" 其实是自己写坏的。修 `bootstrap.py`、
   `extract_packages.py` 的 `os.open`；另补 `_pwrite`（Windows 无 `pwrite`，而 `lseek+write`
   不是原子一对，GIL 只序列化单个调用，并发分段下载会互相覆盖写偏移，需持锁）。
2. **文本编码（中文 Windows locale = GBK）** —— `read_text`/`write_text`/`.open()`/
   `subprocess(text=True)` 不指定编码时按 locale 解码，仓库文件却是 UTF-8。分别撞到
   counter_timestamp 头文件、`strings.py` 读中英表、clang 输出解码失败导致 `r.stdout=None`
   的连锁 `TypeError`、`javac` 报 576 个「不可映射的字符」。共修 63 处 + 11 处 + 11 处 +
   2 处 `javac -encoding UTF-8`（`ci_checks.py` 原本就带，`build.py` 漏了）。
3. **`fcntl` 不存在** —— 两个 GPU 构建脚本用 `flock(LOCK_EX)` 防重叠构建。新增跨平台
   `file_lock()`：POSIX 分支保持 `fcntl.flock` 语义，Windows 分支用 `msvcrt.locking`
   自己循环重试（`LK_LOCK` 只重试 10 秒，构建可能等更久）。已用跨进程子进程实测互斥生效。
4. **`WinError 193`（%1 不是有效的 Win32 应用程序）** —— 直接执行 NDK 里无扩展名的 clang
   shell 脚本。涉及 `make_probe.py`、`build_gpu_driver.py` 的条件表达式
   `BIN / ("clang++" if cpp else "clang")`、以及 4 处 `compiler`/`CLANG` 定义。
5. **`ci_checks` 误判「没有项目 JDK」** —— `JAVAC` 不带扩展名使 `exists()` 为假，
   `SaveArchiveTest` / `PackageArchiveTest` 两个真实闸门被当成环境缺失跳过。
   走 `tool()` 后恢复，闸门从 6 项变 8 项。

**不变性**：Linux/CI 行为逐字节不变。`HOST_TAG` 在 POSIX 仍是 `linux-x86_64`；`tool()` 与
`file_lock()` 的 POSIX 分支走原路径；`getattr(os,"O_BINARY",0)` 在 POSIX 为 0；
`ci_checks` 仅在 `os.name != "posix"` 或 Python < 3.12 时如实标跳过，Linux/CI 照常真跑。

**前两轮已完成**（详见 git log）：
1. `6d0b04e` 检查工具在 Windows 上的诚实性修复（路径分隔符 / GBK 控制台 / POSIX 测试如实跳过）。
2. `954d402` 计划与续跑入口文档纳入版本管理。

**尚未开始**：§8 第 2 步（拿到 TotK 游戏文件后填计划 §3 的表）、第 3 步（着色器事实表来源，
计划 §4.4，M2 的 go/no-go 检查点）、以及 D2R 专属资产的裁剪提交。

## 本机环境与已知限制（均已实测）

- **纯 Windows 开发可用，无需 WSL/Ubuntu。** WSL2 的 Ubuntu 包已卸载（注册项指向不存在的
  目录），本机也没有 Linux 容器 —— 这不是阻碍，构建已在 Windows 上端到端跑通。
- **Python：系统默认 3.9.2 不够用。** 构建用
  `D:\Switch\.tools\venv\Scripts\python.exe`（**3.12.14**，与 CI 的 3.12 同代）。
  理由有两条：`bootstrap.py` 用 `hashlib.file_digest`（需 3.11+）；`ci_checks` 的
  字面量扫描白名单按 3.12 的 PEP 701 分词行为生成，3.9 上结构上跑不绿。
  注意 `py -0` 里的 3.14 注册项指向不存在的 `C:\Python314`，别用。
- **Android 工具链**：`D:\Switch\.tools\android`（NDK r28c / build-tools 35 /
  platform-35 / platform-tools / JDK 17，全部为 Windows 版）。跑任何构建脚本都要带
  `DM_ANDROID_TOOLS=D:\Switch\.tools\android`。
- **Python 依赖**：`lz4 capstone unicorn numpy pillow zstandard nsz` 已装进上面的 venv。
- **未接真机**：`adb` 已就位但没有设备；`--install` 未验证。
- **`gh` 默认仓库会解析到 upstream**（`sydeEvans/d2r-android`）：所有 `gh` 命令必须显式
  `--repo jinran3/d2r-android`，否则会打到别人仓库上。
- **fork 的 GitHub Actions 未注册**（`actions/workflows` 返回 0，PR 上无 checks），
  所以本地构建是目前唯一的验证手段。

## 下一步

按计划 §8 顺序：

1. ~~`totk/scaffold` 分支 + 可验证基线~~ —— 完成。
2. ~~纯 Windows 工具链 + APK 构建~~ —— 完成（`622c473`）。
3. **裁剪提交**：删计划 §2 清单里的 D2R 专属资产（36 个 `dm_*.c`、D2R 派生表、i18n 表、
   TACT 相关），重跑 `ci_checks.py` 与 `build.py --game-run` 确认仍绿。
   ⚠️ 计划里写的「纯删除、可回滚」低估了工作量：核心文件里有 **79 处对 `dm_*` 的调用**
   （`diag.c` 49 处、`hle_hid.c` 14 处、`touch_mac.c` 10 处），25 个头文件，
   `ci_checks` 还强制要求三张派生表存在，且 `host/Makefile` 的 `SRC` 是显式列举、
   `host_link.py` 用 `glob("*.c")` —— 两处行为不同，删文件必须同时核对。
   另注意 `ci_checks` **不链接宿主**，删坏符号它抓不到，所以要以 `build.py --game-run`
   为准（它会真的走 `host_link.py --activity` 链接）。
4. **拿到自己的 TotK 本体+更新与 `prod.keys` 后**，填计划 §3 的表、读出 NSO 构建号
   （计划里 `extract_packages.py` 硬编码了 D2R 的 Title ID `0100726014352000`，必须改）。
5. **解决计划 §4.4 的着色器事实表来源** —— M2 的 go/no-go 检查点，唯一可能推翻整条路线的点。

## 必须遵守的边界（每轮复述）

- 不提交任何游戏内容：程序、美术、着色器、存档，以及由它们生成的图 / 表 / 代码。仓库的 `.gitignore` 已挡 `*.nsp/nsz/xci/nca/keys` 与 `/ExeFS/` `/romfs/` `/save/`，游戏文件另放仓库外。
- 密钥不回显：日志与错误信息里不出现 `prod.keys` 内容（`extract_packages.py` 已按此设计）。
- 许可边界：Ryujinx 着色器翻译与 Eden 胶水是 GPL-3.0，本仓库是 MIT，**可参考思路不可拷代码**。
- 结论要带证据：性能与正确性结论必须写明机型、场景、热机状态；没跑的直接写「没跑」。
## 首次开机预演清单（2026-10-21 离线准备）

> 目的：手机一回来就能对照着读日志，而不是重新猜「卡在哪一步」。
> 本文所有日志字符串都来自**当前源码**（`dm/host/main.c`、`dm/host/loader.c`、`dm/host/diag.c`、
> `dm/gfx/nvn/hle_nvn.c`、`dm/android/native/nvn_vulkan_*.inc`、`dm/android/native/gpu_driver.c`、
> `dm/android/java/org/d2r/android/port/*.java`），不是凭印象写的。
> 级别标注：**文件格式对**（静态可验）/ **运行口径对**（需要真机）/ **真机跑过**（目前一项都没有）。

### 0. 先说清楚日志在哪（最容易踩的一脚）

- 客体的日志行（`[dm] ...`、`【红】...`、`[vulkan-...]`、`[nvn] ...`）走 `dm/host/dm.h` 的
  `LOG()` → `fprintf(stderr)`；Android 前端把 stderr / stdout 重定向到**内部存储的 game.log**
  （`dm/android/native/frontend_activity.c:205`：`open(..., O_WRONLY|O_CREAT|O_TRUNC)` + 两次 `dup2`）。
  → **这些行不在 logcat 里**。logcat 只有 tag `D2RAndroid` 的行（`dm/android/native/vulkan_front.c`
  的 `LOG` 宏是 `__android_log_print`）以及崩溃时的 tombstone。
- 取日志的命令（`run-as` 需要 debug 版 APK，本仓库出的就是）：
  ```
  adb shell run-as org.d2r.android.port cat files/game.log > D:\Switch\totk-work\device\game.log
  ```
  game.log **每次开机都被 O_TRUNC 截断** → 重启就丢，务必先拉下来再重启。
- `die()`（`dm/host/dm.h`）会打一行 `[dm] FATAL ...` 然后 `abort()` → logcat 里会出现
  `Fatal signal 6 (SIGABRT)`，栈顶在 `abort` → 对照 game.log 最后一行即可定位。

### 0.5 开机后会看到的红字里，有一条**不是故障**

| 日志行 | 出处 | 对 TotK 是不是故障 |
| --- | --- | --- |
| `[android] 【红】数据包没有 derived.tsv：编年史仓库 / 经验条 / 动态亮度的表将是空的（用新版打包器重新生成数据包）` | `dm/android/native/frontend_activity.c:247` | **不是**。这三张派生表（EXP 经验表 / TAROW 技能图标索引 / 关联亮度）是 **D2R 专属**的游戏系统，TotK 没有；包里的 `derived.tsv` 本来就没有（`build_package.py` 的 `assemble()` 只在 `derived` 不为 None 时才写它）。宿主只在**调试浮层**里用这三张表（`dm/host/dm_hud_exp.h`），游戏本体不读。→ 看到这行**直接忽略**，别去重新出包。 |
| `[android] 数据包带 derived.tsv：三张派生表在运行时从它读` | 同上第 246 行 | TotK 不会出现（包里没有这个文件）；D2R 包才出现。 |

其它两条开机时就会打出来的信息：

- **游戏的消息文本在包里**：`romfs/Mals/<语言>.Product.100.sarc.zs`（14 个语言，每个 1,510 条，
  `CNzh/EUde/EUen/EUes/EUfr/EUit/EUnl/EUru/JPja/KRko/TWzh/USen/USes/USfr`）——
  已实测这 14 个文件都在数据包里（`romfs/` 下），宿主把 `DM_ROMFS` 指到
  `<外部存储>/d2r-package/romfs`，所以游戏按相对路径就能开到。
  ⚠️ **别只在 `Pack/` 里找文本** —— 那里没有消息归档。

### 1. 开机前的静态核对（一条命令：`python dm/android/tools/totk_device_check.py`）

> 本轮新增的工具：设备一接上，先跑它。退出码 **0 = 全绿（可以开机）/ 1 = 有红项（先修）/ 2 = 手机没接上**。
> 它把下面这张表逐条查完，并在末尾把 `files/game.log` 拉下来（可选 `--pull-log <路径>`）。
> （本轮实测：手机没接上时它 exit 2 并说明原因 —— 其余检查要设备在场才能做。）

| 查什么 | 命令 | 期望 |

| --- | --- | --- |
| 游戏档位 | `adb shell run-as org.d2r.android.port cat files/temp/launch-settings.conf` | 里有 `game_profile=totk` |
| 驱动档位 | `adb shell run-as org.d2r.android.port cat files/temp/gpu-driver.conf` | 用内置 Turnip 时有 `subgroup_size=64` |
| 模块齐不齐 | `adb shell run-as org.d2r.android.port ls files/d2r-package/game` | 3 个 `.so` + 6 个 `.tsv`（`main/sdk/subsdk0` × `fixups/gates`） |
| 外部数据 | `adb shell ls /sdcard/Android/data/org.d2r.android.port/files/d2r-package/` | `manifest.json` + `romfs/` + `shaders/` |
| 完成标记 | `adb shell cat /sdcard/Android/data/org.d2r.android.port/files/d2r-package/manifest.json` | `format=1`、`counts.romfs=304207`（`run-as` 只对内部存储有效，外部存储要用 `adb shell cat`） |

> ⚠️ **启动界面会覆盖 `game_profile`**：`LauncherActivity.startGame()` 用界面里选中的那一行重写
> `game_profile`（`LauncherActivity.java:639`），`deploy_totk.py` 写进去的值会被覆盖。
> → **必须在启动界面的「游戏」那一行切到「王国之泪」**，否则宿主按 D2R 的**分离**句柄表读 c[2]
> （`dm/android/native/nvn_c2_layout.h`），画面必然不对。这是本清单里第一号陷阱。

### 2. 阶段 A：模块装载 → nnMain 之前

| 顺序 | 预期 game.log 行 | 出处 |
| --- | --- | --- |
| 1 | `[dm] ⓪ 进程创建 → 宿主 main（dyld）` | `dm/host/main.c`（`dm_prof_mark`） |
| 2 | `[dm] ① 宿主装载（读 NSO / 重定位 / 强制接管）` | 同上 |
| 3 | `[dm] main: base 0x… size 0x…`（三个模块各一行） | `dm/host/loader.c:422` |
| 4 | `[dm] main: gates N patch_off 0x… keys …` | `dm/host/loader.c:227` |
| 5 | `[dm] main: reloc relative=N abs/glob=N jump=N` | `dm/host/loader.c:253` |
| 6 | `[dm] force: N 条全部命中` | `dm/host/loader.c:169` |
| 7 | `[dm] ② SDK 初始化（nnosInitialize → nninitStartup）` + `>>> nnosInitialize` / `>>> nninitInitializeSdkModule` / `>>> nninitStartup` | `dm/host/main.c` |
| 8 | `[dm] ③ 各模块 init_array` | `dm/host/main.c` |
| 9 | `[dm] >>> nnMain` | `dm/host/main.c:82` |
| 10 | `[dm] ④ nnMain → ToFrontEnd` | `dm/host/diag.c:299` |
| 11 | `[dm] ⑤ 装载面板开→关` / `⑥ →MainMenuButtonRibbon` | `dm/host/diag.c:254` 的分段打点 |

- **硬失败**（出现即 abort）：
  `FATAL 缺符号 <名字>`（`dm/host/main.c` 的 `req()`）、
  `FATAL dlopen: …`（模块没解出来，或落在外部存储 —— 外部存储是 noexec，dlopen 必失败）、
  `FATAL Invalid module layout` / `FATAL Invalid dynamic metadata: main|sdk|subsdk0`、
  `FATAL [android] launch settings: …`（`launch-settings.conf` 解析失败，例如 `game_profile` 写了别的值）。
- **画面**：这一段还没出图 → **全黑**。日志停在哪一行就定位到哪一步。
- **注意**：Android 侧的模块来自**内部**存储的 `d2r-package/game/`（`DM_GUEST_LIBDIR`），
  名字约定是 `libdmguest_<name>.so` + `<name>.fixups.tsv` + `<name>.gates.tsv`
  （`dm/host/loader.c:316-318`）—— 与包里 `game/` 的 9 个文件一一对应（**文件格式对**）。

### 3. 阶段 B：NVN 接管（第一次 GPU 调用）

| 预期行 | 出处 | 含义 |
| --- | --- | --- |
| `requested=Turnip library=…; identity pending` 或 `requested=system selected=system` | `dm/android/native/gpu_driver.c` | 驱动选哪个 |
| `subgroup policy requested=64 physical_default=… support=… range=…..… required_stages=0x…` | 同上 | 子组尺寸策略 |
| `[vulkan] shader subgroup profile=64 matches selected shader execution 64` | `dm/android/native/nvn_vulkan_shader.inc:61` | **这一行必须出现** |

- **硬失败**：
  - `FATAL Vulkan shader subgroup profile 64 differs from selected shader execution N; rebuild for the actual policy`
    —— 包里写死 64（`manifest.subgroup_size` 与 `shaders/host-subgroup-size.txt`），驱动实际子组尺寸不同就作废整批 SPIR-V。
  - `FATAL actual GPU cannot explicitly select subgroup64 for every supported NVN shader stage`
    —— 系统驱动（高通）不支持 `VK_EXT_subgroup_size_control` 覆盖全部着色器阶段 → **换内置 Turnip**。
  - `FATAL Custom game driver requires DM_VK_SHADERS and its subgroup profile` / `FATAL Set DM_VK_SHADERS to Vulkan shader cache`
    —— 着色器目录没指到数据包（`DM_VK_SHADERS` = 外部存储的 `d2r-package/shaders`）。
  - `【红】NVN 未实现被调用：<名字> (x0=… x1=… x2=…)` —— `dm/gfx/nvn/hle_nvn.c:71`，每个接口只打一次。
- **画面**：仍黑，但只要没有 FATAL，进程是活的。

### 4. 阶段 C：描述符集 / 着色器装载（出图前最后一道）

| 预期行 | 出处 |
| --- | --- |
| `[vulkan] shader <key> stage=N bindings=N dynamic_uniforms=N` | `nvn_vulkan_shader.inc`（每个新着色器一行） |
| `[vulkan-create-slow] frame=… kind=shader_load wall_ms=… shader=…` | 只打慢的（>2 ms） |
| `[vulkan] dynamic uniform fallback: shader=… guest=… driver=… limit=…` | 动态 uniform 超限时退回静态 |

- **硬失败**（这一组最可能真的发生）：
  - `FATAL Missing Vulkan shader <目录>/<key>.spv` ← **头号嫌疑**：包里没有这个键的 SPIR-V。
    （键口径在**文件格式对**这一级已经核过：归档 47,260 个着色器的完整键与流水线键一致，**运行口径对**要等真机。）
  - `FATAL Invalid Vulkan reflection <key>` —— `.meta` 与 `.spv` 不同源。
  - `FATAL Vulkan descriptor array capacity` / `FATAL Vulkan descriptor allocation: N` / `FATAL Vulkan descriptor buffers allocation`
  - `FATAL Vulkan dynamic uniform placement: shader=… placed=… expected=…`
  - `FATAL Vulkan storage buffer mapping pending: shader=… cb=… offset=0x…`
  - `FATAL Vulkan dependency storage mapping: shader=… cb=… offset=0x…`
  - `FATAL Vulkan render pass create failed: N` / `FATAL Vulkan has no coherent host-visible buffer memory`
    —— 后者是 Adreno 750 上的真风险：驱动可能不给 host-visible 的内存。

### 5. 阶段 D：合并句柄拆分（TotK 专属，最容易「静默地错」）

- TotK 的贴图句柄是**合并句柄**：c[2][0x20 + 8r]（32 槽），低 20 位纹理 id、第 20..31 位采样器 id；
  D2R 是**分离表**（贴图 c[2][0x168…]、采样器 c[2][0x568…]、图像 c[2][0x120…]）。
  档位由 `DM_GAME_PROFILE`（= `launch-settings.conf` 的 `game_profile`）决定，见 `dm/android/native/nvn_c2_layout.h`。
- 拆分与写回在 `dm/android/native/nvn_vulkan_handles.inc:16-20` 与 `nvn_vulkan_shader.inc:317`。
- **这一处没有专门的日志行** → 只能靠**画面**判断：几何正常但贴图全花/全黑 → 先怀疑这里。
- **硬失败**：`FATAL Vulkan texture handle type %u is unsupported` / `FATAL Vulkan texture-handle bank %u is unsupported`
  / `FATAL Vulkan texture-handle stage %u` → 句柄表布局猜错（多半就是 `game_profile` 没切成 totk）。

### 6. 阶段 E：变体挑选（43.6% 风险那一处，日志能直接给答案）

| 行 | 出处 |
| --- | --- |
| `[vulkan-shader] 控制键 <key> 命中变体 <vkey>（机器码来自 0x…）` | `nvn_vulkan_shader.inc:233`（前 8 次 + 每 64 次） |
| `[vulkan-shader] 控制键 <key> 的变体没挑中，退回多数派变体（累计退回 N 次）` | `nvn_vulkan_shader.inc:241`（前 64 次 + 每 64 次） |

- **命中行里的「机器码来自 0x…」就是程序在运行期的地址** —— 这一行直接回答了
  「变体挑选的机器码位置在哪」这个一直悬着的问题（**运行口径对**的第一条证据）。
- 读法：累计退回 N ≈ 0 → 变体挑选正确；退回很多 → 五个候选位置
  （`data` / `data-of` / `data+of` / `control+0x880` / `control+0x880+of`）全不命中，
  要改 `nvn_vulkan_shader.inc` 的 `starts[]`。
- **画面**：挑中但挑错 → 花屏 / 几何炸；退回多数派 → 43.6% 的着色器可能拿错 SPIR-V → 花屏或黑屏。

### 7. 阶段 F：预排布贴图

| 行 | 出处 |
| --- | --- |
| `[nvn] 预排布贴图 <W>x<H>x<D> 级<L> 格式0x… 目标<T> 布局字节 … → 块高 log2=… 尺寸 0x…` | `dm/gfx/nvn/hle_nvn.c:251`（前 16 条） |
| `[nvn] 预排布贴图 首传 N 张、池内容变化重传 N 次；写保护缺页 N 次、宿主写前解保护 N 页；漏检 N（累计）` | `hle_nvn.c:1477`（每帧末尾） |

- **报错（不是硬失败，进程继续跑，但贴图是空的）**：`【红】TextureBuilderGetStorageSize 未知格式 0x…` —— 格式不认识（`hle_nvn.c:257`）。
- **画面**：贴图黑 / 紫（缺贴图）但几何正常 → 与着色器问题是两类，要分开看。
- 「首传 N 张」里 N 为 0 → 上传路径没被触发，贴图全是空的。

### 8. 怀疑清单（我怀疑对、但静态验不了的）

> 规矩：**不靠猜改代码**。每条都写清「在哪」「为什么可疑」「真机上怎么确认」。

| # | 位置 | 为什么可疑 | 真机上怎么确认 |
| --- | --- | --- | --- |
| 1 | 合并句柄拆分 `nvn_vulkan_handles.inc:16-20`、`nvn_vulkan_shader.inc:317` | 布局是从 9,807 个着色器的贴图立即数反推的（「0x20 起 8 字节步进，一个都不越界」），**没有一条真机证据** | 画面：几何正常、贴图全花 → 先查这里；再核对 `DM_GAME_PROFILE=totk` 是否生效 |
| 2 | 变体挑选的机器码位置 `nvn_vulkan_shader.inc` 的 `starts[]` | 纯静态推断（注释里已写明），五个候选里哪个对**未知** | 看命中行的「机器码来自 0x…」；地址应落在程序区且与 `data` 有固定关系 |
| 3 | 预排布贴图的块高 `dm/gfx/nvn/nvn_tex.c` | 布局参数第 0 字节 = 块高 log2 只见过 16 例对照 | `[nvn] 预排布贴图 … 块高 log2=…` 与画面是否一致；「首传 N 张」N 是否非 0 |
| 4 | c[2] 里 0x120 起的图像句柄表（TotK 与 D2R 同源的假设） | 图像（render target）表位置是按 D2R 侧推的 | 画面：渲染目标（阴影 / HDR 中间纹理）不对，但贴图正常 |
| 5 | 子组尺寸 64 | 包里写死 64；**Adreno 750 的实际子组尺寸未验**（8 Gen 3 的 warp 宽度本机无法确认） | 日志里 `[vulkan] shader subgroup profile=…` 与 `subgroup policy … physical_default=…` 两行 |
| 6 | `DM_GAME_PROFILE` 是否真的传下去 | 启动界面重写 `launch-settings.conf`；`deploy_totk.py` 写的值会被覆盖 | 开机后第一行的 `[android] 环境核对 …` 里有没有 `DM_GAME_PROFILE` |
| 7 | 更新包补丁缺失 | **模块与数据不是同一次构建**（实测：本体 main 的 NSO 头构建号 `cef09201…`、36,549,681 字节；更新 `076db101…`、35,621,994 字节；包里发的模块带构建号 `5cb42b1c…`）→ 跑的是「v1.4.2 的代码 + 本体的数据」，补丁要替换 **2,658 个文件** | 开机后有没有「数据版本不匹配」类的错误；进游戏后文本/事件是不是本体那版（旧内容） |
| 8 | `DM_ROMFS` / `DM_VK_SHADERS` 指向外部存储 | 外部存储是 FUSE，且游戏要按名字开文件 | `[android] 数据包带 derived.tsv：…` 这一行在不在（说明包路径找对了） |

### 9. 手机端导入流程的离线核对（2026-10-21 实测）

**包的真实结构**（用 `zipfile` 逐条读 `D:\Switch\totk-work\package-totk\totk-package-updated.zip`，2026-10-22；
下面是**基座包** `totk-package.zip` 的旧数据，条目数差在 overlay 上）：

| 类别 | 条目数（基座 → 更新包） | 压缩后（更新包） | 解压后 |
| --- | --- | --- | --- |
| `game/` | 9 → 9 | 81,598,218 | 81,598,218 |
| `romfs/` | 304,207 → **304,243** | 17,026,724,605 | 17,026,724,605 |
| `shaders/` | 24,535 → 24,535 | 646,871,659 | 646,871,659 |
| 合计 | 328,752 → **328,788** | **17,825,708,024（16.60 GiB）** | **同左** |

> **真机要推的是更新包** `totk-package-updated.zip`（本体 v1.4.2 + v1.4.2 补丁的 overlay）；
> 基座包 `totk-package.zip` 只是「只有本体数据」的旧包，**别再推它**。

- **全部条目是 stored（压缩方法 0）**，也就是**包里没有压缩** → 解开后还是 16.55 GiB。
  → HANDOFF 里「zip 17 GiB + 解开 ~34 GiB」是按「解压会变小」估的，**偏大**。
- **真实容量**：外部存储 = zip 16.62 GiB + 解出 16.47 GiB ≈ **33.1 GiB**；内部存储再加 `game/` 的 81.6 MB。
  → **/data 至少留 35 GiB，建议 40 GiB**。导入完删掉 zip（`adb shell rm /sdcard/Android/data/org.d2r.android.port/files/totk-package.zip`）
  之后只要 ~17 GiB。
- **上限核对**（`dm/android/java/org/d2r/android/port/PackageArchive.java`）：

  | 上限 | 代码里的值 | 本包 | 结论 |
  | --- | --- | --- | --- |
  | `MAX_ENTRIES` | 600,000 | 328,752 | 过（余量 45%） |
  | `MAX_TOTAL_BYTES` | 24 GiB | 16.55 GiB | 过（余量 31%） |
  | `MAX_ENTRY_BYTES` | 12 GiB | 196,302,345（最大文件 `romfs/Event/Movie/Dm_ZN_0033_PreRender.webm`） | 过 |
  | `MAX_MANIFEST_BYTES` | 1 MiB | 314 | 过 |
  | 清单自报数 | game 9 / romfs 304,207 / shaders 24,535 | 与实测逐项一致 | `requireCount` 不会拒 |

- **路径长度**：最长 165 字符，最长单段 114 字符 → ext4 与 FUSE 都放得下。
- **耗时风险（NOT RUN，手机上没有实测过）**：包里**一个目录条目都没有**（328,752 条全是文件），
  导入时每个文件都要 `mkdirs()` 建父目录 → 约 30 万次目录创建 + 30 万次文件创建，
  写在 FUSE 支撑的外部存储上。保守估计**十几分钟到一小时**，请预留时间、别中途切后台。
  进度条按写入字节数每 1% 报一次。
- **一个容易踩的点**：启动界面用 SAF（`ACTION_OPEN_DOCUMENT`）选包，而 `deploy_totk.py` 把 zip 推到了
  `/sdcard/Android/data/org.d2r.android.port/files/`。Android/data 对别的应用不可见，
  DocumentsUI 作为系统应用通常能列出，但**授予的 URI 未必读得到**。
  → **备选：把 zip 放到 `/sdcard/Download/` 再在启动界面里选**：
  ```
  adb push D:\Switch\totk-work\package-totk\totk-package-updated.zip /sdcard/Download/
  ```
  选不中或报「无法读取所选文件」就走这条。

### 9.5 NA-050/NA-051：overlay 合进宿主包（2026-10-22）

- **合包工具**：`dm/tools/totk_merge_package.py`（本仓库 MIT，自己写的）。读基座包 zip，
  逐条**原样复制**（STORED，不重新压缩）未被替换的条目，用 NA-049 导出的正文替换对应路径、
  跳过 727 个 `removed` 路径，并重写 `manifest.json`。
  **只读基座包、只写新文件**：输出路径不能等于基座包，也不能落在仓库内（工具自己拒绝）。
- **产物**：`D:\Switch\totk-work\package-totk\totk-package-updated.zip`
  = **17,825,708,024 字节（16.60 GiB）**，**328,788** 条目 = game 9 / romfs 304,243 / shaders 24,535 /
  `manifest.json` 1；替换 **14,397**、删除 **727**。
  条目数自洽：基座 328,752 + 新增 763 − 删除 727 = 328,788 ✓。
- **交叉印证**：更新包 `manifest.json` 的 `bytes.romfs` = 17,026,724,605，
  与 BKTR 更新映像文件表的总字节**逐字节相等**（两条独立路径算出同一个数）。
- **独立抽样核对**（本会话，sha256 逐字节比）：
  随机 240 个 `added`/`changed` + 强制包含两个「同大小但内容被替换」的老样本
  （`TerrainArc/StartIsland.tscb`、`UI/Map/MainField/U_06-03_04.bntx.zs`）→ **全部与导出目录一致**；
  随机 40 个 `unchanged` → **与基座包逐字节相同**；727 个 `removed` 路径在包里 **0 残留**。
- **代码与数据现在是同一次构建**（此前不是，NA-050 修好的）：
  包里 `game/` 的模块是从**更新**（v1.4.2）的 `main` NSO 改出来的
  （`patched-android/main.patched.bin` 头 0x20 的 build id 与 `nso/upd_main.img` **逐字节相同**：
  `f40300aa001440f9f30301aa616301d0`；本体的 `base_main.img` 不是这个）；
  数据侧现在也是 v1.4.2 → **「v1.4.2 的代码 + 本体的数据」这个错配已经不存在**。
- **变体键链那条闸门**：2026-10-22 06:23 那次完整预检里它是**唯一红项**（「超时 1800 秒」），
  但**同一命令单独跑是 exit 0**（本机实测 5~6 分钟，47,260 个着色器，键/c1/控制段长度不匹配均为 0）
  → 判定为**执行环境**（机器负载/休眠）而不是数据缺陷。
  已把闸门超时上限从 1800 秒放宽到 3600 秒（`totk_preflight.py --gate-timeout`，可调）。
- **两条会自我误报的坑，已修**：
  1. 一条正在跑的长操作会在日志里留 `[BEGIN]`，而它内部又调 `agent_handoff_check.py --verify`
     → 校验器看到「自己留下的 BEGIN 没闭合」就报红。现在可以用环境变量点名豁免：
     `DM_HANDOFF_PENDING_OPS=na-051-preflight`（默认行为不变，负向测试仍过）。
  2. 预检的 `ci_checks` 闸门不继承 `DM_ANDROID_TOOLS` 时会跳过 JDK 闸门 →
     跑预检**必须**带上 `DM_ANDROID_TOOLS=D:\Switch\.tools\android`。
- **不在 Android 关键路径上的一件事**（省下别人去 Mac 的时间）：
  `dm/gfx/nvn/dmsh_chain.h` 的翻译链锁 `15cf7ca29eaf` 与本机算出的 `84d7e6048895` 不一致，
  以前记成「Mac 侧必须重建」。**实测 `DMSH_CHAIN` 只被 `nvn_mtl.m`（iOS/macOS 的 Metal 路径）引用，
  `dm/host` 与 `dm/android` 里一次都没有** → 它是 **iOS 侧**的事，**不影响 Android 首次开机**。
  Android 的着色器是出包时翻好的 SPIR-V，随包走（`shaders/*.spv`），运行期直接读包。

### 10. 更新包 BKTR 补丁：2026-10-21 的进展（实测）

本轮的结论分三级写清楚：

- **已排除**（此前会话）：明文 Brotli / 同段 CTR / XTS+头密钥。
- **本轮新查到（有命令有退出码）**：
  1. **更新包的 RomFS 段虽然标着 `crypt: bktr`，它的数据其实是普通 AES-CTR**
     （content key + 段 CTR，与其它段同一套）。证据：这样解出来的 232 字节元数据块
     是一个**合法**的 IVFC 头（magic `IVFC`、id `0x20000`、master_hash_size `0x20`），
     随机密钥不可能凑巧；同一个位置在错误密钥下是乱码。
  2. **BKTR 的两个头在 NCA 头的 fs_header 里**（`fs_header+0x100` 起），不是段数据里 ——
     整段 456 MiB 扫过一遍，`BKTR` 魔数一个都没有。
  3. **段内物理布局已经定死**（见下表）。
  4. **元数据块的自校验通过**：它的 sha256 与 NCA 头里存的那个哈希**逐字节相等**。
  5. 新增工具 `dm/tools/totk_bktr.py`（本仓库 MIT，自己写的）：一条命令读出并核对上面全部事实。

  ```
  python dm/tools/totk_bktr.py <更新包的 .nca> --keys <prod.keys>
  → 退出码 0，末行「布局自洽：True」
  ```

  段内物理布局（段长 478,557,696 字节）：

  | 区间 | 长度 | 内容 |
  | --- | --- | --- |
  | `0x00000000`–`0x1C843400` | 478,426,112 | 补丁数据（被下一段覆盖） |
  | `0x1C843400`–`0x1C857400` | 81,920 | 重定位 / 校验表 |
  | `0x1C857400`–`0x1C85F400` | 32,768 | hash 层 1 |
  | `0x1C85F400`–`0x1C863400` | 16,384 | hash 层 0（主哈希） |
  | `0x1C863400`–`0x1C8634E8` | 232 | 元数据块（`layer_offset` + IVFC 头，3 层） |

- **载荷解开了（2026-10-21 续）**：载荷里是 **zstd 帧，用的是游戏自己的字典**，
  解出来是 **SARC 归档** —— 也就是游戏的一批 pack 归档。

  ```
  python dm/tools/totk_bktr.py <更新包的 .nca> --keys <prod.keys> --romfs <本体 RomFS 目录>
  → 载荷里的 zstd 帧：16 个
    0x147d5cd0  字典 id=1 内容 12,373,528 → SARC，1,511 条
                （例：LayoutMsg/TreasureFullShortCut_00.msbt、EventFlowMsg/Npc_TripMaster_13.msbt、…）
  ```

  - 字典来自本体 RomFS 的 `/Pack/ZsDic.pack.zs`（**游戏自己带的**，SARC 里装着 `zs.zsdic` id=1、
    `bcett.byml.zsdic` id=2、`pack.zsdic` id=3），解字典的代码仓库里已有
    （`dm/tools/switch_shaders.py` 的 `load_dictionaries` / `decode`）。
  - **本体的 pack 也是同一套结构，但用字典 id=3**：
    `romfs/Pack/*.pack.zs` → zstd(dict 3) → SARC（例如 `AI.Global.Product.100.pack.zs` = 2,061 条，
    `AIScheduleParam.pack.zs` = 1,917 条，`/Pack/Actor/` 下还有 15,049 个按角色分的 pack）。
  - 所以**补丁载荷 = 一批更新过的 pack 归档**（消息归档 `EventFlowMsg/*.msbt` 等就在里面）。
  - 载荷整体熵 7.996 bit/byte（近乎随机），但 12 字节以上可打印串有 138,330 处（随机字节的期望约 3,263）
    → 结构确实在里面，只是被压缩了。
- **载荷里那 14 个消息归档的本体对应物找到了**：把本体 RomFS 里全部 203,031 个 `.zs`
  （15,062 个 `Pack/` 之外的）按 SARC 解开，找出条目里带 `Msg/` 的 —— **正好 14 个**：
  `romfs/Mals/<语言>.Product.100.sarc.zs`（CNzh / EUde / EUen / EUes / EUfr / EUit / EUnl / EUru /
  JPja / KRko / TWzh / USen / USes / USfr），每个 **1,510 条**。
  载荷里对应的 14 个 zstd 帧每个 **1,511 条**（**多了一条** —— 更新加了一个消息），
  压缩后的大小与本体逐个对得上（本体 1,477,675 / 1,521,719 / 1,703,504 / 1,735,670 / … /
  1,888,200；载荷 1,478,628 / 1,526,774 / 1,705,262 / 1,738,928 / … / 1,891,213，都只大几百到几 KB）。
  → **「载荷 = 更新过的文件内容」这个模型成立**，而且这些文件正是游戏的消息归档。

  一条命令就能复核（工具自己会逐个对照）：

  ```
  python dm/tools/totk_bktr.py <更新包的 .nca> --keys <prod.keys> \
      --romfs <本体 RomFS 目录> --compare-base <数据包 zip>
  → 载荷里的消息归档与本体 romfs/Mals/ 的对照：
       0x147d5cd0  条目 1511  压缩 1891213  ->  本体 Mals/EUde.Product.100.sarc.zs（1888200 字节）
       0x149a3860  条目 1511  压缩 1797265  ->  本体 Mals/USfr.Product.100.sarc.zs（1795473 字节）
       …（14 行，逐个对得上）
  ```
  → 顺带一个对移植有用的结论：**本体的消息数据放在 `romfs/Mals/` 下**（每个语言一个
  `.sarc.zs`），不是放在 `Pack/` 里 —— 找游戏文本时别只看 `Pack/`。
- **重定位表的结构（部分解开）**：那 81,920 字节分成 **5 页 × 16 KB**，
  每页头部第 4 个 u32 是该页的条目数：**`[4, 818, 818, 818, 204]`**。
  首页那 4 条是页头（不是记录），所以真正的条目数 = 818+818+818+204 = **2,658** ——
  而 fs_header 里那个「块总长」正好是 `0xA62` = **2,658** ⇒ 两边交叉印证，
  **这条补丁要替换 2,658 个文件**（平均每个约 180 KB）。
  `dm/tools/totk_bktr.py` 现在会把每页计数与这个交叉核对一起打出来。
- **重定位表：查到这里了（记录下来，免得下一轮重走）**
  - 区域是 `[0x1C843400, 0x1C85F400)` = 114,688 字节 = **7 页 × 16 KB**
    （头里那个「块总长」只覆盖前 5 页 = 81,920 字节）；
    前 5 页的头部计数是 `[4, 818, 818, 818, 204]` → 条目 **2,658**，
    与 fs_header 的 `0xA62` = 2,658 一致。
  - 页里能看到**两条交错的单调 u64 序列**（步长 40 字节）：一条从小值（44,192 → 98,160 → 33,308,720 …）
    一条从大值（85,015,632 → 278,155,696 → 478,354,784 …），两者都能跨页连续，最大到 ~17 GB。
  - ⚠️ **纠正一个先前的错误说法**：曾以为「约 55% 的 u64 值正好是本体某个文件的数据起点」——
    那是**把值为 0 的项也算进去了**（本体第一个文件的数据起点就是 0）。
    去掉 0 之后，整个 81,920 字节里**只有 15 处**能命中本体文件的数据起点
    （且间隔不规则：300 / 720 / 820 / 880 / 2312 / 4232 / 4608 字节），基本可当巧合看待。
    → **这张表里没有本体文件的偏移**。
  - 因此更像是**哈希树**而不是「文件对照表」：114,688 字节 = **3,584 × 32 字节**，
    而 3,584 × 32 = 114,688 正好等于元数据块里 `level[1].hash_data_size`（0x1C000）——
    也就是说这 114,688 字节很可能就是**第 1 层的 IVFC 哈希树**
    （每个哈希覆盖下面一层的 16 KB 块）。那么「哪个载荷块替换哪个本体文件」也许**根本不是靠这张表**，
    而是靠内容哈希 —— 载荷里的新内容带着自己的哈希，哈希树把哈希落到本体数据区的位置上。
    这条还没验证（需要能把载荷按块切开才能算哈希）。
  - 试过并且**不成立**的解释（下一轮别再试）：
    ① 定长记录：起点 0–63 × 步长 8/12/16/20/24/28/32/36/40 共 160 种组合，
       没有一种能让「长度之和 = 载荷长度 478,426,112」成立；
    ② 记录里的 u64 是载荷偏移：载荷里 14 个消息归档的偏移（0x147d5cd0 等）在表里**找不到**；
    ③ 记录里的 u64 是本体文件偏移：本体 `Mals/*` 的 14 个文件偏移（映像 3.56–3.58 GB 那一段，
       以及减去数据区起点的两种口径）在表里都**找不到**；
    ④ u32 字段是新的长度：这些值加起来只有几千，离载荷的 478 MB 差着两个数量级；
  ⑤ 「按内容哈希映射」这条路**已经排除**（2026-10-21 查清，见下）。
- **本体 RomFS 的「file_hash_table」到底是什么（查清了）**
  - 它**不存哈希**。本体那张表（偏移 0x3F7FE8138，1,216,828 字节）的真实结构是
    **28 字节头 + 304,200 个 4 字节项**，每项要么是 `0xFFFFFFFF`（空桶），
    要么是一个**文件元数据表（file_meta_table）里的偏移** ——
    拿着这些偏移去读元数据表，条目的父/兄/数据偏移/大小/名字**全都对得上**
    （例：`DmT_GO_MeetAgain_Text_008_b.bwav`、`Mrg_H-5_MrgD100_B8-BE-AY-FEB1B5F5.bcett`…），
    条目数 304,200 与本体的 304,207 个文件一致。
  - 也就是说：哈希只体现在**桶的顺序**里，表里并不存哈希值。
    → **「用内容哈希把补丁块映射到本体文件」这条路不成立**（本体里根本没有内容哈希）。
  - 顺带查过：把文件内容算 sha256 / sha1 / md5 / blake2b / blake2s、
    或零填充到 0x200/0x400/0x1000/0x2000/0x4000/0x10000 再哈希，
    **在本体那张表里一个都找不到** —— 与上面的结论一致。
  - 顺带也查过：路径哈希（java*31 / djb2 / sdbm / fnv1 / fnv1a / crc32 等 14 个底数 ×
    正反序 × 带不带结尾 NUL × 全路径或只文件名 ≈ 100 多种口径）**与表里的值都对不上** ——
    因为表里压根没有哈希值可比。
- **BKTR 的结构解开了**（2026-10-21；用本机 venv 里已装的 `nsz` 5.0.0 作**格式参考**
  —— 只读结构事实，代码自己写）：NCA 头的 fs_header 里有两个 BKTR 头（各 32 字节：
  `u64 偏移, u64 长度, 'BKTR', u32 版本, u32 条目数, u32 保留`）：

  | 头 | 偏移 | 长度 | 条目数 | 内容 |
  | --- | --- | --- | --- | --- |
  | A | `0x1C843400` | `0x14000` | **2,658** | 重定位桶 |
  | B | `0x1C857400` | `0x8000` | 646 | 子段桶 |

  - **重定位区**（头 A）：开头是 `{u32 填充, u32 桶数=4, u64 补丁映像总长=17,086,048,256}`，
    接着 2,034 个 `u64`（桶边界），然后**每个桶正好占一个 16 KB 页**，页头是
    `{u32 填充, u32 条目数, u64 结束偏移}`，其后是若干条
    **`{u64 虚拟偏移, u64 物理偏移, u32 isPatch}`（20 字节）**。
    实测四个桶的条目数 818 / 818 / 818 / 204（合计 2,658 ✓），
    结束偏移 0x6C8BD840 / 0xFD701C70 / 0x278F0DCF0 / 0x3FA686800（最后一个 = 补丁映像总长 ✓）。
  - **虚拟偏移 = 这一段在「补丁后的映像」里的位置；物理偏移 = 它的内容在本次段载荷里的位置**
    （载荷 = 段里 `0x1C843400` 之前的那 478,426,112 字节）。
    虚拟偏移从 0 单调到 17,062,338,768（= 虚拟映像的数据区大小 ✓）。
  - 于是**映射是「区域」级的，不是「文件」级的**：第 0 条就是
    「虚拟 [0, 26,752) ← 载荷 [85,015,632, …)」。
  - 虚拟偏移**不是**本体文件的数据起点（只有 6/2,658 撞上）：更新后的文件大小变了，
    虚拟映像的数据区布局与本体不同 —— 本体数据区起点 0x1FE8000，更新的是 0x1FE0000
    （哈希树小了 32,768 字节）→ 整体错位。
  - **子段桶**（头 B）：头里写的是**桶数 = 1**；桶 0 有 **646** 条，条目是 **16 字节**
    `{u64 载荷物理偏移, u32 填充, u32 ctr}`（没有大小字段 —— 大小是拿「下一条减这一条」算出来的），
    桶 0 的结束偏移 = 载荷长度（478,426,112 ✓）。
    **关键纠错**：这 646 个 offset 是**载荷物理偏移**，不是虚拟偏移；读补丁时必须按源物理偏移换 CTR。
  - **区域里的内容还不像「文件内容」**：第 0 区（虚拟 [0, 26,752) ← 载荷 [85,015,632, …)）
    在载荷里是 **32 字节随机数据 + 全零**；载荷开头 0 处也是高熵数据。
  - **「虚拟偏移」的坐标系：已确认是相对整张补丁映像** ——
    理由：虚拟映像的 IVFC 哈希区在最前面，而**本体那张哈希区恰好也是「若干个 32 字节哈希 + 全零」**
    （本体层 0 = 224 字节 = 7 个哈希，其后全零；更新的层 0 = 16 KB）。
    第 0 区在载荷里是「1 个 32 字节哈希 + 全零」⇒ 它就是**虚拟映像新的哈希区**，
    虚拟 0 = 映像开头 ✓。
    由此：虚拟映像的数据区起点 = 0x1FE0000（本体是 0x1FE8000，哈希树小了 32,768 字节），
    所以**未被修改的部分整体要平移 32,768 字节**；子段桶的 `ctr` 是按源物理偏移切换的
    AES-CTR 计数器，不是「本体块序号」。
  - **先前待验项的当前结论**：① 第 0 区确实是更新映像的哈希/头部区域，不能把它当文件正文；
    ② 子段 `ctr` 的语义已由更新头跨边界读取验证；③ 更新文件表已能直接读出（见下）。
- **运行口径已经解开（2026-10-21 NA-047；有命令、退出码和产物）**：
  - 重定位条目按 `isPatch` 选源：`isPatch=1` 从更新 NCA 的载荷物理偏移读，`isPatch=0` 从本体 NCA 的
    RomFS 段物理偏移读；虚拟偏移是补丁映像坐标，末桶边界取重定位区自己的总长
    `17,086,048,256`，不能拿 `fs_header` 里的重定位区长度 `0x14000` 当总长。
  - 子段表按**源物理偏移**查找；每个子段把自己的 `ctr` 写进 AES-CTR 的低 32 位，
    读跨子段的区间必须拆开。更新头最后 16 字节正好跨在物理 `0x52d4e70` 的 CTR 边界，
    用错 CTR 会把 `file_meta_table_size` / `data_offset` 读成乱码。
  - 用已验证的读法解析更新映像的 RomFS 头（数据区 `0x1FE0000`）与目录/文件元数据表：
    **更新 304,243 个文件 / 本体 304,207 个**；新增 763、删除 727、同名大小改变 6,978；
    样本 `Mals/USen.Product.142.sarc.zs` 为 1,798,330 字节，读出的前 4 字节是 zstd 帧头
    `28 b5 2f fd`，用字典 id=1 解出 SARC **1,511 条**。
  - 工具与产物（只读、不写游戏数据）：
    ```
    python dm/tools/totk_bktr.py <更新包的 .nca> --keys <prod.keys> --base <本体 Program NCA> --json
    ```
    → exit 0；`D:\Switch\totk-work\bktr-updated.json`；`layout.updated_romfs` 含上述计数。
  - **NA-049 导出与口径修正（有命令、退出码、产物）**：
    - **口径修正（重要）**：NA-048 的 `changed` 是**按大小**判定的，会漏掉"大小相同但内容被替换"的文件。
      用重定位表 `isPatch=1` 区间相交重新判定后：**同大小但被替换的 6,656 个**（例
      `TerrainArc/StartIsland.tscb`、`UI/Map/MainField/U_06-03_04.bntx.zs`）被找回；
      反向无误报（大小不同的 6,978 个全部被触及）。新口径：
      added 763 / changed 13,634 / unchanged 289,846 / removed 727。
    - 导出：`totk_bktr.py --export-overlay D:\Switch\totk-work\overlay\export\` → exit 0，
      **14,397 个文件、474,841,307 字节**（added+changed），全部在仓库外。
    - 核对：`build_package.py overlay <清单> --romfs <导出目录> --statuses added,changed` → exit 0，
      `checked_against_romfs=14397`（每个文件路径与大小都对得上）。
    - 样本：`Mals/USen.Product.142.sarc.zs` 1,798,330 字节、头 `28 b5 2f fd`、字典 id=1 → SARC 1,511 条；
      `Pack/ZsDic.pack.zs` 是 unchanged（108,344 字节），**不在导出集内**。
    - 可复现：用修复后的工具再导一次 added 子集，与首轮导出**763/763 逐字节相同**。
    - 级别边界：这是"补丁文件清单与正文"证据；**宿主包尚未合并，真机未跑**。
  - **NA-048 清单入口（有命令、退出码、产物）**：
    ```
    python dm/tools/totk_bktr.py <更新 NCA> --keys <prod.keys> --base <本体 NCA> \
        --overlay-manifest D:\\Switch\\totk-work\\overlay\\totk-overlay.tsv --json
    ```
    → exit 0；TSV 26,549,605 字节 / 304,970 条状态行：
    added 763、removed 727、changed 6,978、unchanged 296,502；
    样本 `Mals/USen.Product.142.sarc.zs` = added / 1,798,330，
    `Pack/ZsDic.pack.zs` = unchanged / 108,344。
    `python dm/android/tools/build_package.py overlay <TSV>` → exit 0，只校验清单 counts/路径安全，
    可选 `--romfs` 再核对非 removed 文件大小；不读虚拟偏移正文、不生成 zip。
    合成测试 `dm/android/tests/test_overlay_manifest.py` → exit 0；
    CI 新增 `BKTR overlay 清单（t_overlay）` 后为 **15 项通过 / 0 失败**；
    `build.py --game-run --version trim-b48` → exit 0（APK 17,873,359 字节）。
    **级别边界**：这是“文件格式/清单口径”证据，不是“覆盖包已生成”，更不是“真机跑过”。
  - 参考实现只用于读格式事实：`SciresM/hactool`（git clone 到仓库外
    `D:\Switch\totk-work\ref-hactool`），本仓库代码仍由 `dm/tools/totk_bktr.py` 自己实现。
- **仍未解决**：
  1. **把每个更新文件落到宿主包里**：文件表已经能列出，但还要按更新后的路径/大小重打包；
     这是数据管线的下一步，不影响当前“先用本体数据 + v1.4.2 模块”开机。
  2. **载荷的分帧边界**：16 个 zstd 帧已知，其余区域仍是未压缩/其它容器；这不阻塞文件表读取。
  3. IVFC 各层哈希的完整校验尚未逐块重算；当前结论是运行读取口径，不是“哈希树已全验”。
- **这一层对主线的影响**：本体数据已经完整可用（15.87 GiB / 304,207 个文件，逐字节抽样验过），
  所以**先按「本体数据 + v1.4.2 的模块」开机**，补丁是第二优先级。

### 11. Mac 侧翻译链重建：要在 Mac 上跑的命令与前置（备着，这轮做不了）

**现状**（本机可验）：`dmsh_chain.py` 算出的链版本是 `84d7e6048895`，
而 `dm/gfx/nvn/dmsh_chain.h` 里写的是 `15cf7ca29eaf` → **头是旧的**。
链版本只由**仓内源文件**决定，所以 `--header` 在哪台机器上都能重算；
但**工具锁** `dm/gfx/tools/dmsh_chain.lock` 记的是实际工具的指纹（Ryujinx 着色器 dll、spirv-cross、
**macOS/iOS 的 metal 编译器版本**），换机器就变 → 锁必须在 Mac 上重生成。

在 Mac 上的顺序（前置：Xcode 命令行工具、`spirv-cross`、.NET SDK、仓内 `dm/gfx/tools/dmsh_xlate/`）：

```bash
cd <仓库>/dm/gfx/tools/dmsh_xlate
dotnet build dmsh_xlate.csproj -c Release          # 翻译器要先用仓内 Program.cs 编出来
cd ..
python3 dmsh_chain.py --check-tools                 # 看实际工具与锁是否一致（不一致会列出来）
python3 dmsh_chain.py --update-lock                 # 按 Mac 上的实际工具重写锁（要随提交入仓）
python3 dmsh_chain.py --header                      # 重写 dm/gfx/nvn/dmsh_chain.h
python3 dmsh_chain.py                               # 打印新的链版本 V
```

- 锁和头改完 → **链版本 V 变了** → 宿主要找的 `b-<V>/` 目录也变了 → **必须重出一次着色器库**
  （`dmsh_build.py`，或 TotK 侧走 `dm/gfx/tools/totk_xlate.py`），否则宿主加载不到旧目录。
- 本轮 NOT RUN（没有 Mac）。本轮也没有改 `dmsh_chain.h`：改了会在 Mac 侧 `--update-lock` 时再变一次，
  徒增一次无谓的差异。

### 12. 开机操作手册：推包 → 导入 → 开机 → 读日志（NA-052，2026-10-22）

> 一条命令 + 一页纸。命令是 `dm/android/tools/deploy_totk.py`，本文是它的 runbook。
> **结论分级**：脚本逻辑本机已验（干跑 exit 0、21/24 条 adb 命令原样打印、字节校验与 counts
> 比对都真跑过判断分支）；**真机行为 NOT RUN**（手机没接上，`adb devices` 空）。
> 目标包 = **`D:\Switch\totk-work\package-totk\totk-package-updated.zip`**（17,825,708,024 字节，
> 328,788 条目；NA-051 的 7 条闸门在它上面全绿）。**基座包 `totk-package.zip`
> （17,842,231,302 字节，v1.4.2 本体）是回退点，不要拿它首发。**

#### 12.0 先干跑（手机不在也能做，改完脚本必跑）

```powershell
$vpy = 'D:\Switch\.tools\venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
$env:DM_ANDROID_TOOLS = 'D:\Switch\.tools\android'   # 注意是 .tools（点号路径不存在，JDK 闸门会被跳过 → 假绿）
& $vpy dm\android\tools\deploy_totk.py --dry-run --package D:\Switch\totk-work\package-totk\totk-package-updated.zip
```

- 期望：**exit 0**，每条都以 `[dry-run] <adb 命令行>` 原样打印（能直接复制到终端跑），
  结尾 `== 完成：共执行 21 条 adb 命令 ==`；干跑与真跑是**同一个 `main()`**，
  只有 adb 传输层把「执行」换成「打印」，设备侧返回值由假 Adb 给占位。
- 回归：`dm/android/tests/test_deploy_totk.py`（已接进 `ci_checks` 的 `t_deploy`），
  覆盖干跑两条 dest、行匹配的「▸  」前缀、df 解析、字节不一致 / 空间不足 / 没设备三条负路。
- 退出码：`0` 走完；`2` 没有 adb / 没有设备 / 包不存在；`3` 空间不够或空间查不出来；
  `4` 推送或字节校验失败；`5` 导入问题（超时或清单对不上）；`6` 没等到日志。

#### 12.1 第 1 步：推包

```powershell
# 首选：推到应用外部目录的固定名，启动界面可一键导入（不用手指翻文件选择器）
& $vpy dm\android\tools\deploy_totk.py --package <更新包> --dest fixed --log-out D:\Switch\totk-work\device\game.log
# 备选：推到 /sdcard/Download/（SAF 一定能读到；导入时自己在选择器里选这个文件）
& $vpy dm\android\tools\deploy_totk.py --package <更新包> --log-out D:\Switch\totk-work\device\game.log
```

- **adb 解析顺序**：`--adb` 显式指定 > `DM_ANDROID_TOOLS/platform-tools` > 仓内/工作区约定路径
  （`<仓库>\.tools\android`、`D:\Switch\.tools\android`）> PATH 上的 adb。
- **推之前的空间闸门**（外部 `/sdcard` 与 `/data` 都查）：导入要 ~33.1 GiB
  （zip 16.60 GiB + 解出 16.47 GiB，包内 328,752 个条目全是 stored）→ **< 35 GiB 拦住（exit 3），
  < 40 GiB 警告**。`df -k` 解析不出数字时也 exit 3，但消息说「不要当成空间满」——那是 shell 的问题。
- **推完的字节校验**：`stat -c %s`（不支持则退 `wc -c`）与本地字节数逐字节比对，
  不一致 exit 4。16.6 GiB 的 push 在 USB 2.0 上可能要几十分钟，正常。
- **该看到什么**：每条 adb 命令以 `$ ` 打印；`字节校验通过：本机与手机都是 17825708024 字节`。

#### 12.2 第 2 步：导入

- `--dest fixed`：脚本自动点「从推送的包导入」那一行（按 uiautomator dump 的后缀匹配，
  容忍「▸  」前缀）；`--dest download`：包在 `/sdcard/Download/`，**SAF 选择器自己选**
  （脚本只等完成标记，不代点——选文件是系统的选择器，adb 点不了）。
- **完成标记**：`/sdcard/Android/data/org.d2r.android.port/files/d2r-package/manifest.json`
  （**外部**包目录，2026-10-22 真机首跑实测；内部 `files/d2r-package/` 只有 `game/`）。它在解包**最后**才写。
  脚本轮询它（默认 180 分钟超时），出现后把手机上的清单与本地包对一遍
  （`format` / `subgroup_size` / `counts`），对不上 exit 5——那说明推错包了。
  **已导入过就跳过重导**：脚本先查这个标记，存在就只核对 counts（重导一次十几分钟到一小时）。
- **屏幕上该看到什么**：状态行先 `正在导入 0%` → `100%`，再变成 `已导入：…`。
  包里没有目录条目（每条都要 mkdirs），**导入要十几分钟到一小时**，别以为卡死。
- **导入中断了怎么办**：`PackageArchive` 先把旧 manifest 撤掉、新的最后才落盘 →
  中断只会留下一个**没有 manifest 的目录**，游戏判「不可用」，**重跑导入即可**，不用清数据。

#### 12.3 第 3 步：开机

- **第一号陷阱（脚本已设两道闸）**：`LauncherActivity.startGame()` 会用界面里选中的那一行
  重写 `game_profile`，写别的值 → 宿主按 D2R 的**分离**句柄表读 c[2]，画面必然不对。
  脚本在推包后写 `files/launcher-state.conf`（界面自己的状态，`game=totk`）
  和 `files/temp/launch-settings.conf`（native 严格解析的那份，`game_profile=totk`）两道；
  真机上仍要**扫一眼**界面「游戏」那一行显示的是「王国之泪」。
- 脚本点「启动游戏」（`▸  启动游戏` 行），然后等 `files/game.log` 出现（默认 300 秒）。
- **该看到什么日志**：对照「首次开机预演清单」阶段 A–F（模块装载 → NVN 接管 →
  描述符集/着色器 → 合并句柄拆分 → 变体挑选 → 预排布贴图），每段的预期行、
  硬失败行与画面状态都在那一节；`【红】数据包没有 derived.tsv` 对 TotK **不是故障**（见 0.5 节）。
- **没等到日志（exit 6）**：客体日志**不在 logcat**（见 12.4）；先
  `adb logcat -d -s D2RAndroid` 看前端自己的行，再看有没有 tombstone
  （`Fatal signal 6 (SIGABRT)` = 宿主 `die()`，栈顶在 `abort` → 对照 game.log 最后一行；
  game.log 每次开机 O_TRUNC 截断，崩了的话最后一行就是崩因）。

#### 12.4 第 4 步：读 files/game.log

- 位置：**内部存储** `files/game.log`（`run-as` 才读得到），**不在 logcat 里**；
  logcat 只有 tag `D2RAndroid` 与 tombstone。脚本用 `--log-out` 自动拉回本机；
  手动等价命令：`adb shell run-as org.d2r.android.port cat files/game.log > game.log`。
- **先拉下来再重启**——每次开机 O_TRUNC，重启就丢。
- 关键确认行：`DM_GAME_PROFILE=totk`（档位）、
  `[vulkan] shader subgroup profile=64 matches selected shader execution 64`（子组口径）、
  `[dm] >>> nnMain`（进主函数）、`[nvn]`/`[vulkan] shader <key> ... bindings=...`（着色器装载）。
  脚本会检查第一行，没有就提示对照「首次开机预演清单」第 6 条怀疑项。

#### 12.5 第 5 步：失败回退（回退到基座包）

| 情形 | 动作 |
| --- | --- |
| 更新包导入后开不了机，怀疑是数据侧 | 停游戏 → `adb shell run-as org.d2r.android.port rm -rf files/d2r-package` → `adb shell rm -f /sdcard/Download/totk-package-updated.zip /sdcard/Android/data/org.d2r.android.port/files/totk-package.zip` → 推**基座包** `totk-package.zip` 重走 12.1–12.3（`--dest fixed` 时脚本会把它落到固定名，界面一键导入） |
| 脚本或档位写坏了 | 脚本只写两个 conf 与 `/data/local/tmp` 临时文件，`rm -f` 掉即可，不用重装 |
| 代码要回退单个文件 | `git checkout eeb1c1f -- <文件>`（**不用 `git reset --hard`**）；APK 回 `trim-b50` |
| 只是日志里出现红字 | 先对照 0.5 节与「首次开机预演清单」的怀疑清单，**别急着回退**——已查清 `derived.tsv` 那条是正常的 |

- 回退判据写在证据里：更新包与基座包的 manifest counts 不同（romfs 304,243 vs 304,207），
  脚本第 4 步的 counts 比对就是抓「推成基座包了」这类错误的。

#### 12.6 2026-10-22 真机首跑实录（一加 12 / PJD110 / Android 16）

| 步骤 | 实际结果 |
| --- | --- |
| 装 APK | 原机是 trim-b46（早于 NA-046），先换 trim-b51；加载器修复后换 trim-b52 |
| 推包 | 16.60 GiB → `stat -c %s` = 17,825,708,024，与本机一致 |
| 导入 | 约 13 分钟；外部 manifest counts 与本地包**逐项一致**（romfs 304,243 / shaders 24,535 / romfs 字节 17,026,724,605）；内部 `game/` 9 个文件 78 MB |
| 开机 | `main` 装载（gates 0 / size 0x3aecb80）、`sdk` 装载（gates 101 / size 0xc63cc0）→ **`FATAL Invalid image bounds`（subsdk0）** |

- **根因**：subsdk0 没有补丁点（`sites.tsv` 为空），重写器只追加 16 KiB 键页 → `patched.bin` 长度 = `PATCH_OFF` = 0x670000；
  `dm/android/native/runtime.c` 的边界检查用 `>=` 把「没有补丁区」误判成越界（`guest_elf.py` 自己的校验允许 `<=`）。
  修复：改 `>`（键页仍由 layout 校验保证在镜像内）。
- **首跑还暴露并修掉的部署脚本问题**：① `adb devices` 的守护进程横幅被当成设备；② `get-state` 走了 `adb shell`（exit 127）；
  ③ 完成标记轮询了内部路径；④ 启动行「▸  」前缀 + 3168×1440 横屏列表被截断 → 后缀匹配 + 滚动查找。
- **教训**：真机 `uiautomator dump` 前先确认 `mCurrentFocus` 是本应用（首跑时被一个 RDP 浮窗挡住，dump 到的是别的应用）。

