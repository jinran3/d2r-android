---
status: PLAN
created_at: 2026-10-23T08:10:00+08:00
owner: agent
supersedes: 无（旧宿主继续留在 dm/ 作为对照基线，不删除）
---

# TotK Android App 重写方案（从零）

## 0. 一句话

新工程 `totk-app/`，**自己的 Android 前端 + 自己的宿主核心 + 自己的 NVN 接管**，不继承 `dm/` 下任何 C 代码与 Java 前端；
`dm/` 保留为**对照基线**（机内 `trim-b62`，commit `a2273ba`），直到新 App 自己跑到 `>>> nnMain` 才允许讨论下线。

## 1. 为什么保留基线（硬性）

从零重写最难的不是写代码，是**判断"这一步到底对不对"**。旧路径的价值不是它的代码，而是它已经证明过的事实与日志形态：

- 三模块重定位计数基线：`main relr=499074 abs/glob=1421 jump=649`、`sdk relr=15007 …`、`subsdk0 relr=3424 …`
- DT_INIT 规模：main 10,717 项 / sdk 83 项 / subsdk0 45 项
- 已确认可达的日志序列：`nninitStartup → DT_INIT → >>> nnMain → romfs 挂载 → oe 初始化 → vi vsync`
- 已知崩溃签名（新工程若出现同样的 pc/lr 模式，说明犯了同一个错，见 §4）

**规则**：新工程任何阶段的输出，都要能与上面这些数字/行**逐项比对**；对不上就是新工程的 bug，不是"游戏变了"。

## 2. 边界：从哪里开始算"从零"

| 部分 | 处置 |
| --- | --- |
| Java/Kotlin 前端（Activity、启动器、设置、输入法、SAF 选包） | **重写**（旧：2,390 行，8 文件） |
| native 前端（JNI 桥、Surface、生命周期、日志重定向） | **重写**（旧：3,793 行，17 文件） |
| 宿主核心（装载器、重定位、HLE、SVC、线程/同步、fs/vi/am/oe） | **重写**（旧：12,709 行，43 文件） |
| NVN→Vulkan 接管 | **重写**（旧：2,257 行，3 文件） |
| 数据包与导入流程（zip 布局、manifest、counts 校验） | **复用事实，不抄代码**：格式已定案，按规范重写导入器 |
| 外部项目（totk-mobile / MacNativeGames / rhythm-heaven-android） | **只读思路与格式事实**（Apache-2.0 与本仓 MIT 不兼容，代码不搬） |

## 3. 分层（新工程）

```text
totk-app/
  android/            新 Android 工程（package org.totk.android.port）
    app/              Activity / Surface 生命周期 / 设置 / 文件选择
    jni/              JNI 桥（只做转发，不做逻辑）
  core/
    image/            模块读取：MOD0、动态段、symtab/strtab、RELA/JMPREL/RELR
    loader/           mmap、封页（R-X）、跨模块符号解析、强制接管表
    kshim/            SVC 分派：线程 / 锁 / 事件 / 定时 / 堆 / 内存权限
    service/          HLE 服务面：os fs vi am oe sf hid aoc …（按符号差集生成清单）
    gfx/              NVN→Vulkan：设备/队列/交换链/描述符/着色器
    diag/             日志、崩溃现场（pc 原文 + 栈扫描 + 槽位对拍）
  tools/              打包器、导入器、部署脚本（重写，不抄 dm/tools）
  tests/              每个阶段一个可离线跑的判据
```

## 4. 已定案的事实（带过去的是知识，不是代码）

1. **DT_RELR 语义**：偶数项 = 新游标槽；奇数为位图，覆盖随后 63 槽；**位图后无条件推进 63 槽**；`*槽 += base`，**值为 0 的槽不跳过**（0 表示指向模块基址）。
2. **模块偏移与 `.so` 布局**：镜像起点 = `.so` 里 `0x4000` 处的可执行段；模块内偏移 = 打印偏移，**不要**再加 0x4000。
3. **陷阱 A：写死 D2R 偏移**。宿主曾把 `sdk+0x2f9974` 当作 `StandardAllocator::Allocate` 原版入口；TotK 的该符号在 `0x1375f0`，`0x2f9974` 落在 `nn::codec::pcmDmx_ApplyFrame` 中间。
   **新工程规则：任何函数地址都必须由符号解析得到，源码里禁止出现裸模块偏移。**（可用常量只允许是"符号名 + 期望值断言"）
4. **陷阱 B：mangled 名精确匹配**。`nn::fs::ReadFile` 在 TotK 有 3 个重载（5 参 / 6 参带 `ReadOption` / 4 参无 out），旧表只覆盖 1 个。
   **新工程规则：接管表由"模块未定义符号集合"自动生成缺口报告，CI 里当闸门跑。**
5. **服务缺一格的典型崩法**：`blr` 到 0（`addr=0 pc==lr`）或把句柄当对象指针解引用（`ldr w8,[x0,#imm]`，x0 是小整数）。
   新工程的崩溃诊断必须默认打印：`x0..x30`、pc 前后四字原文、`sp..sp+0x400` 栈扫描、模块表。

## 5. 阶段与判据（每阶段一个 READY 动作，不许并行）

| 阶段 | 内容 | 通过判据（必须有命令 / 退出码 / 日志行） |
| --- | --- | --- |
| **R0 骨架** | 新工程能编、能装、能起，Surface + 日志落到应用私有目录 | `install` exit 0；启动后 `files/app.log` 出现版本行与 Surface 尺寸 |
| **R1 装载** | 读三模块、MOD0/动态段、RELR+RELA+JMPREL、封页、符号解析 | 打印三模块 relr/abs/jump 计数，**与 §1 基线逐项相等** |
| **R2 内核垫片** | SVC 分派（线程/锁/事件/定时/堆/SetMemoryPermission） | SDK 初始化到 `SetHeapSize` 成功；`nninitStartup` 无崩 |
| **R3 服务面** | os/fs/vi/am/oe/sf 最小集（按符号差集驱动） | 三模块 DT_INIT 全走完（10717/83/45）+ `>>> nnMain` |
| **R4 图形** | NVN→Vulkan：设备挑选、subgroup、交换链、着色器装载 | `subgroup profile=64 matches…` + 首帧清屏色 |
| **R5 出图** | 描述符/句柄拆分/变体挑选/预排布贴图 | 进到可交互画面（截帧证据） |

工作量量级（按本仓历史节奏，一批 ≈ 一个原子任务）：R0 1 批；R1 2–3 批；R2 3–5 批；R3 4–6 批；R4 3–5 批；R5 视情况。
**期间旧路径不动**：任何时刻都可以回到 `trim-b62` 用同一台手机复现对照。

## 6. 第一批 READY（R0）

- 目标：`totk-app/` 能编出可安装 APK，启动后写一行日志 + 显示一块纯色 Surface。
- 不做：不加载游戏、不碰 NVN、不读数据包。
- 判据：`install` exit 0、`files/app.log` 有 `totk-app R0 <version> 1.0`、Surface 尺寸行与真机 3168×1440 一致。
- 回滚：`totk-app/` 整体删掉不影响任何既有功能。

## 7. 与旧路径的关系

- 旧路径冻结在 `trim-b62`（commit `a2273ba`），**继续可用**；不再往里加新功能（除非新工程卡在同一处、需要它做对照实验）。
- 新工程跑到 R3（`>>> nnMain`）之后，才评估是否下线旧路径。
- 数据包、导入流程、部署脚本：新工程自己重写，但**手机上的已导入数据不动**（NA-050/051/052 的成果仍然有效）。

## 8. 终点定义（Definition of Done）

> 用户要求：**app 开发出来之前不停这一轮**。因此把「开发出来」写成可判定的终点，并按阶段连续推进，
> 每阶段必须留下命令/退出码/日志/截帧；上下文或设备成为硬阻塞时才停，且停下前必须写交接。

**DoD（全部满足才算"开发出来"）**：

1. `totk-app` 在一加 12（`3b864e51`）上安装成功、从启动器点开能稳定进到**可交互画面**（R5）；
2. R1–R4 每阶段各有一条**真机证据**：R1 的三个 relr 计数与基线逐项相等；R2 的 `SetHeapSize` + `nninitStartup`；
   R3 的三模块 DT_INIT（10717/83/45）+ `>>> nnMain`；R4 的 `subgroup profile=64` + 首帧清屏色；
3. 全程**没有裸模块偏移**、接管表缺口由符号差集闸门覆盖；
4. 旧路径 `dm/`（`trim-b62`）保持可用，直到上面 1–3 全部达成为止。

**明确不在本轮终点内**：性能、存档/音频/手柄的完整校准（M4）、iOS/macOS 侧。

## 9. R0 结果（2026-10-23 08:20）

- 构建：`D://Switch//.tools//venv//Scripts//python.exe totk-app/tools/build.py` → exit 0，`totk-app/build/totk-app-R0.apk`（12,691 字节，apksigner verify 通过）。
- 安装/启动：`adb install -r` Success；`mCurrentFocus=org.totk.android.port/.MainActivity`。
- 日志（`files/app.log`，`run-as` 读取）：
  `totk-app R0-1.0 package=org.totk.android.port abi=arm64-v8a sdk=36 device=PJD110` / `resumed` / `surface 3008x1376`。
- 截帧：`D://Switch//totk-work//device//totk-app-R0.png`（深蓝底 + 版本字 + 尺寸）。
- **实测偏差（记下来，R4 前必须处理）**：Surface 是 **3008x1376**，不是显示器的 3168x1440；
  截帧左侧还有一条黑边（约 50 px）—— 说明当前不是 edge-to-edge，被系统栏/挖孔 inset 让出了位置。
  R4 接 NVN 交换链前要改成沉浸式全屏（`WindowInsets` 不参与布局 + `setDecorFitsSystemWindows(false)`），否则画面会缩。
