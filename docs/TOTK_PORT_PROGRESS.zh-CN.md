# TotK 移植进度

更新日期：2026-10-20。此文件随工作更新，是中断后继续移植的入口。

路线图与分阶段验收门见 [TotK 移植脚手架计划](TOTK_PORT_SCAFFOLD.zh-CN.md)（下称「计划」）。

交接入口见 [TotK 移植交接文档（HANDOFF）](HANDOFF.zh-CN.md)。

- 目标设备：一加 12（Snapdragon 8 Gen 3 / **Adreno 750** / Android）
- 起点：fork 自 `sydeEvans/d2r-android`（HEAD `5d8e322`），上游是 `jhaizhou-ops/d2r-mobile`
- 分支：`totk/scaffold`（`main` 保持 D2R 可构建，不混入 TotK 工作）

## 当前状态（继续开发先看这里）

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