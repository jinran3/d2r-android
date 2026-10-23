# Agent 交接会话日志

## 2026-10-23 07:36 Asia/Shanghai — [SESSION] NA-045 收尾：fs 句柄接缝修好，卡点前移到 nn::vi（阶段 B 门口）

- **NA-045 根因（定案）**：`nn::fs::ReadFile` 在本作有**三个重载**，而 `hle_fs.c` 只接管了 D2R 那个 5 参版本
  （`_ZN2nn2fs8ReadFileEPmNS0_10FileHandleElPvm`）。本作多出来的
  `…ElPvmRKNS0_10ReadOptionE`（6 参）与 `…ENS0_10FileHandleElPvm`（4 参）**名字不匹配强制接管表 → 没接管**，
  客体就走 sdk 自己的实现，而 sdk 那条路把**宿主发的句柄当 `detail::FileAccessor*`** 解引用：
  真机 `CRASH sig=11 addr=0xc0 pc=sdk+0xa5940`，指令 `ldr w8,[x0,#0x24]`，x0 = 句柄 0x9c。
  反汇编证据：`nn::fs::ReadFile`(0xa93b0, size 0x84) 是薄包装 —— `mov x0,x1`（句柄）+ `mov x1,x8`（out）→
  `bl 桩 0x647f40` → 槽 `0xb6d280` = `_ZN2nn2fs6detail12FileAccessor4ReadEPmlPvmRKNS0_10ReadOptionE`（把 x0 当 this）。
  系统核对：本作未定义的 fs/fssrv 符号 33 个、接管表 24 条，**差集 11 个**（见下）。
- **修复**：把两个重载都接进 `hle_fs.c`，共用同一个 `h_fs_ReadFile`（pread）；`ReadOption` 只影响缓存/优先级，宿主直读用不上。
- **真机证据（trim-b60，build exit 0 + install exit 0 + `deploy_totk.py --no-push` exit 0，日志 92 行）**：
  `[dm] >>> nnMain` → `fs 挂载 content: → …/d2r-package/romfs（只读）` → `oe::SetFocusHandlingMode 2` →
  `oe::SetPerformanceConfiguration mode=0 cfg=0x92220008（忽略）` → 崩在**新位置**（`FileAccessor` 那条不再出现）。
- **新卡点**：`CRASH sig=11 addr=0 pc=sdk+0x44f3f4 lr=sdk+0x44f3f4`。
  `pc 原文` = `aa1403e0 94083290 f94002a8 aa0003e2` ⇒ pc 处是 `ldr x8,[x21]`，**x21 = 0**（刚 `bl` 回来，x30 即 pc）。
  符号 `sdk+0x44f3c0` = `_ZN2nn2vi20GetDisplayVsyncEventEPNS_2os15SystemEventTypeEPNS0_7DisplayE`（size 0xbc），函数体：
  `bl 0x65be40`（槽 `0xb77200` = **`nn::vi::GetService()`**）→ `ldr x21,[sp,#8]`（**服务对象 = 0**）→
  `bl 0x65be30`（槽 `0xb771f8` = `nn::vi::GetDisplayIdWithValidation`）→ `ldr x8,[x21]` 崩。
  ⇒ **宿主完全没有 `nn::vi` 接管面**（`grep -rn 'HLE_FORCE("_ZN2nn2vi' dm/host/` 为空），而本作在 nnMain 早期就要 vi 的 vsync 事件。
- **可复用设施（下一批直接用）**：`dm/host/hle_thread.c:661 hle_bind_system_event()`（在客体线程上调 SDK 自己的
  `nn::os::CreateSystemEvent(跨进程=1)` 并记下写端句柄）与 `:676 hle_signal_system_event()`（任何线程可触发）。
- **仍欠的 fs 接管（记住）**：`MountCacheStorage` / `CreateCacheStorage` / `DeleteCacheStorage` / `OpenCacheStorageList` /
  `ReadCacheStorageList` / `CloseCacheStorageList` / `IsSaveDataExisting` / `MountSaveDataReadOnly` / `SetPriorityOnCurrentThread`。
  现在没接管的走桩（返回 0），存档相关迟早要真实现。
- 分级：「文件格式对」已核；「运行口径对」——DT_INIT + nnMain + romfs 挂载 + oe 初始化都过了；
  「真机跑过」仍未出图，**阶段 B 的第一个动作（vi/vsync）就是现在的卡点**，B–F 仍 NOT RUN。

[END] na-045-readfile-b60
退出码：`build.py --game-run --version trim-b60` exit 0；`adb install -r` Success；`deploy_totk.py --no-push` exit 0
产物：`dm/android/build/D2R-Android-port.apk`（trim-b60）；真机日志 `D:/Switch/totk-work/device/game_b60.log`（92 行）
结果：SUCCESS（fs 重载接缝修好，卡点前移到 nn::vi）

## 2026-10-23 09:28 Asia/Shanghai — [SESSION] NA-049 定位：崩溃函数 = main+0xbde198，与 GetSystemTick / 一对单例同族

- **函数入口找到**：`main+0xbde198`（`stp x29,x30,[sp,#-0x30]!`）。逻辑：
  ```text
  adrp x8,0x394c000 ; ldr x8,[x8,#0xf08]   ; x8 = 全局 main+0x394cf08 → 指向对象 main+0x3abaeb8
  adrp x21,0x394c000; ldr x21,[x21,#0xc38] ; x21 = 全局 main+0x394cc38 → 指向对象 main+0x3abade8
  x9 = 0xa3d70a30d70b（魔数，smulh 后 = 除以 100）
  ldr x8,[x8]        ; 读 0x3abaeb8 的首字段（一个计数/时间值）再 /100
  ldr x9,[x21]       ; 读 0x3abade8 的首字段 —— **这里是 0**
  ldr x8,[x9,#0x20]  ; ← 崩（x9=0）
  ```
- **兄弟函数 `main+0xbde138`**（同区，结构相似）：`ldr x8,[x0] → blr [x8,#0xc0]` → `bl PLT 0x2ba3a90` → `str x0,[x19,#0xe0]` → 尾调 `[x8,#0xd8]`。
  该 PLT 槽 `main+0x3979098` = **`nn::os::GetSystemTick`** ⇒ 这一族函数在**读系统滴答、按 100 换算**，
  并把结果存进对象 `+0xe0`（"上次 tick"字段）—— 是帧调度/计时类代码。
- 两个目标对象都在同一段：`main+0x3abade8`（首字段 0，待查）与 `main+0x3abaeb8`（首字段是 tick 源）。
- 三个地址（`0x3abade8` / `0x3abade8 的槽 0x394cc38` / `0x3abaeb8 的槽 0x394cf08`）**在符号表里都没有名字**（无名数据区），
  `0x394cf08` 与 `0x394cc38` 都在 DT_RELR 表里、链接期值分别是 `0x3abaeb8` / `0x3abade8` ⇒ 装载无误，问题在对象未被初始化。
- 栈：`main+0xbde154 ← main+0xc58c20 ← main+0xbb95a8`（nnMain 内）。**还没找到「谁该写 0x3abade8 的首字段」**。

## 2026-10-23 09:08 Asia/Shanghai — [SESSION] NA-047 真机通过：`am::GetApplicationFunctions` 支付后越过 sdk+0x1ea684，卡点进 main+0xbde1e4

- **NA-047 结果**：设备接回后 `adb install -r`（versionName `trim-b63`）+ `deploy_totk.py --no-push` exit 0。
  `game_b63.log`（93 行）：`>>> nnMain` → `vi::GetDisplayVsyncEvent 接管：事件 0x70f0b04d60，宿主按 60 Hz 触发` →
  `CRASH sig=11 addr=0x20 pc=main+0xbde1e4 lr=main+0xbde154`。**`sdk+0x1ea684` 不再出现**，卡点前移。
- **新卡点定性**：`pc 原文` 的 `f9401128` = `ldr x8,[x9,#0x20]`，**x9 = 0**（上一条 `f94002a9` = `ldr x9,[x21]` 读出 0）；
  `x21` 由 `adrp x21,0x394c000; ldr x21,[x21,#0xc38]` 得来 ⇒ **全局槽 `main+0x394cc38` 指向的对象，其首字段是 0**。
  本地核对：`main+0x394cc38` **在 DT_RELR 表里**、链接期值 `0x3abade8` ⇒ 装载后应为 `base+0x3abade8`，
  与现场 `x21=0x72879a0de8` 反推的 `base=0x7284b703000` 完全吻合 ⇒ **槽本身没被写坏**；
  问题是它指向的静态对象（`main+0x3abade8`）**首字段为 0**（构造没跑 / 宿主该填的句柄没填）。
  栈：`main+0xbde154 ← main+0xc58c20 ← main+0xbb95a8`（都在 nnMain/nninitStartup 之后的无名静态函数里，符号表在 `0xbb91e0..0xc4e690` 之间没有条目）。
  紧邻的上一条日志是我们的 vi vsync 接管，且 `x0=0x70f0b04bb8`、事件 `0x70f0b04d60`（相差 0x1a8）—— **怀疑与显示/vsync 对象链有关**。

## 2026-10-23 08:36 Asia/Shanghai — [DECISION] 方向切回源仓库 App；新工程 totk-app 冻结（SHELVED），移植继续

- 用户决定：**不再推进 `totk-app`**，回到源仓库 App（`dm/`）继续移植。`totk-app/` 的代码**保留不删**（R0/R1 已通过，随时可续），
  `docs/TOTK_APP_REWRITE.zh-CN.md` 头部标 `status: SHELVED`。旧路径 `dm/` 解冻，继续作为主线。
- **继续移植 = 做掉上次的卡点 NA-047**：`dm/host/hle_sdkinit.c` 新增
  `HLE_FORCE("_ZN2nn2am23GetApplicationFunctionsEv", …)` —— 返回静态对象，虚表 64 项全指「返回 0」桩，
  **第 50 槽（+0x190）**换成 `h_am_af_prev_program`：写 s32 出参 `-1`、返回 0（直接启动、无前序程序）。
  依据：`nn::applet::GetPreviousProgramIndex`(sdk+0x1ea670) = `bl GetApplicationFunctions → ldr x8,[x0] → ldr x8,[x8,#0x190] → blr x8`，
  `w0==0` 时返回出参。照同文件 `GetCommonStateGetter` 的既有做法（静态对象 + 全 0 桩）。
- **构建**：`build.py --game-run --version trim-b63` **exit 0**，APK **17,906,127 字节**；
  本地核对：`llvm-strings dm/android/build/libdmandroid.so | grep -c _ZN2nn2am23GetApplicationFunctionsEv` = **1**（接管条目已编进去）。
- **真机验证：NOT RUN —— 设备掉线**。`adb devices` 为空（`adb reconnect` 也无效），装包/部署都拿不到设备。
  因此 trim-b63 **没有**真机证据，不能声明「卡点已越过」。

## 2026-10-23 08:22 Asia/Shanghai — [SESSION] R1 通过：新工程自己读出三模块并做对重定位（与基线逐项相等）

- `totk-app` 加 native 层：`core/loader/selfcheck.c`（MOD0 → 动态段 → DT_RELR/RELA/JMPREL，**只计数不执行客体代码**）、
  `android/jni/totk_jni.c`（纯转发）、`tools/build.py` 增 clang（NDK，`--target=aarch64-linux-android29`）编 `libtotkcore.so` 并以 **STORED + zipalign -p** 打进 APK、
  `tools/push_modules.py`（`adb push /data/local/tmp` + `run-as cp files/modules`）。
- **真机证据**（`R1-0.1`，`app.log`）：`main relr=499074 abs/glob=1421 jump=649 init_array=10717`、
  `sdk relr=15007 abs/glob=11214 jump=7813`、`subsdk0 relr=3424 abs/glob=11832 jump=3816` —— 与旧宿主基线**逐项相等**；
  `init_array` 首项 = 基址 + 0x10bee00（同一个偏移）。
- **坑（记下来）**：① 模块不能放 `/sdcard/Android/data/<pkg>/files`：Android 11+ App 内 `fopen` 直接 EACCES（`run-as` 也读不到），
  必须放内部 `files/modules` 并用 `run-as cp`；② `adb shell` 里带 `/sdcard/...` 会被 Git Bash 做路径转换，需要 `MSYS_NO_PATHCONV=1`。
- **遗留（R2 第一件事）**：三张镜像本轮各自 `malloc/free`，日志里三个模块**基址相同**；R2 必须常驻 + 各占不同地址 + 装键页（x18/TLS）。

## 2026-10-23 08:20 Asia/Shanghai — [SESSION] 新工程 R0 通过：可装、可起、纯色画面 + app.log 出证

- 目标按用户要求写死：**app 开发出来（R5 可交互画面）之前不停**，阶段判据见 `docs/TOTK_APP_REWRITE.zh-CN.md` §8。
- **新建 `totk-app/`**（不引用 `dm/` 任何代码）：`android/AndroidManifest.xml`（package `org.totk.android.port`，minSdk 29 / target 34，landscape，
  NoTitleBar.Fullscreen，debuggable 便于 `run-as` 读日志）、`android/src/.../MainActivity.java`（全屏 Activity + 自绘 View + 双写 logcat/`files/app.log`）、
  `tools/build.py`（aapt2 → javac → d8 → 塞 dex → zipalign → apksigner，一条命令）。
- **构建/真机证据**：`build.py` exit 0 → `totk-app/build/totk-app-R0.apk` 12,691 字节、`apksigner verify` 通过；
  `adb install -r` Success；`mCurrentFocus=org.totk.android.port/.MainActivity`；
  `app.log`：`totk-app R0-1.0 package=org.totk.android.port abi=arm64-v8a sdk=36 device=PJD110` / `resumed` / `surface 3008x1376`。
  截帧 `D://Switch//totk-work//device//totk-app-R0.png`（深蓝底 + 版本字 + 尺寸），肉眼已核。
- **两个实测偏差（R4 前必须处理）**：Surface 实测 **3008x1376**（显示器 3168x1440）；截帧左侧约 50 px 黑边 → 当前不是 edge-to-edge。
- 踩到的构建坑（记下来省下一次）：① Python `subprocess(text=True)` 解码中文 Windows 的 GBK 报错 → 改按字节捕获、打印时 `utf-8/replace`；
  ② `javac` 默认按平台编码读源文件，中文注释直接报错 → 必须 `-encoding UTF-8`；③ `run-as` 需要 `android:debuggable="true"`。

## 2026-10-23 08:10 Asia/Shanghai — [DECISION] 用户决定「真从零重写整个 App」；新工程 totk-app/，旧路径冻结为对照基线

- **决定**：不再在 `dm/`（D2R 血统宿主）上继续修 HLE 缺面，改为新建 `totk-app/`：自己的 Android 前端 + 宿主核心 + NVN 接管。
- **我给的反对意见（已记录，不再重复）**：当前卡点（`am::GetApplicationFunctions` 返回 0）与壳架构无关；从零重写会让已过的 10 道闸门
  （DT_RELR / init_array / nnMain / romfs 挂载 / oe 初始化 / vi vsync）全部重跑，且参考项目 `OJZen/totk-mobile` 自述「装载器/改写器/NVN 沿用 d2r-mobile 设计」
  —— 即成功跑通 TotK 的同类项目走的正是我们这条路。用户已知悉仍选择重写。
- **新方案文档**：`docs/TOTK_APP_REWRITE.zh-CN.md`（分层、阶段 R0–R5、每阶段可执行判据、两条陷阱、工作量量级）。
- **工程红线（务必遵守）**：
  1. **旧路径不删**。`dm/` 冻结在 `trim-b62`（commit `a2273ba`），继续可装机、可复现；新工程到达 R3（`>>> nnMain`）之前不允许下线。
  2. 新工程**禁止裸模块偏移**：任何函数地址必须由符号解析得到（陷阱 A 的教训）。
  3. 接管表缺口由「模块未定义符号集合 vs 接管表名集合」的差集自动生成，并在 CI 里当闸门（陷阱 B 的教训）。
  4. 数据侧不动：手机上的已导入数据包继续用（NA-050/051/052 成果有效）。
- **新工程第一批（NA-101 / R0）**：`totk-app/` 能编出可安装 APK，启动写一行日志 + 显示纯色 Surface；不加载游戏、不碰 NVN。
- 本轮只写方案与交接（上下文冻结门），**没有写任何新工程代码**；R0 从下一次开工开始。

## 2026-10-23 08:00 Asia/Shanghai — [SESSION] NA-046：vi vsync 接管落地，卡点前移到 applet/am（阶段 B 继续）

- **先纠正上一轮的一个错误判断**：上一条日志写「宿主完全没有 `nn::vi` 接管面」是**错的** —— 我当时的 grep 只扫了 `dm/host/*.c`。
  实际上 **`dm/gfx/hle_vi.c` 早就有** `nn::vi::Initialize` / `OpenDefaultDisplay` / `CreateLayer` / `GetNativeWindow`；
  缺的只是 `GetService` 与 `GetDisplayVsyncEvent`。结论方向没变（缺面导致 `GetService()` 返回 0），但表述要按事实写。
- **踩到一个新坑（值得记）**：我先在 `dm/host/` 下新建了 `hle_vi.c`，结果和 `dm/gfx/hle_vi.c` **同名**，
  构建按文件名生成目标文件 → 同一份强制接管表被链接两遍 → 启动 **`FATAL 强制接管清单重复：_ZN2nn2vi10InitializeEv`**（trim-b61，日志 18 行）。
  处置：删掉新文件，把 vsync 接管写进已有的 `dm/gfx/hle_vi.c`。**以后加宿主文件前先 `find . -name '<名字>'`**。
- **NA-046 实现**（`dm/gfx/hle_vi.c` 追加）：整条接管
  `_ZN2nn2vi20GetDisplayVsyncEventEPNS_2os15SystemEventTypeEPNS0_7DisplayE` ——
  在客体线程上调 `hle_bind_system_event(ev, 0)`（SDK 自己经 `CreateSystemEvent(跨进程)` 建事件），
  再起一条宿主 60 Hz 线程用 `hle_signal_system_event()` 推写端。**没去伪造 sf 代理对象**（原本的方案 4 只在 `GetService` 被别处调用时才需要）。
  反汇编依据：`GetDisplayVsyncEvent`(sdk+0x44f3c0, size 0xbc) 先 `vi::GetService()`（槽 0xb77200）→ 虚表 `+0xb8` 取内核事件句柄 →
  末尾 `bl 0x6488c0`（x0=out_event, w1=handle, w2=autoclear, w3=1）把句柄挂到 `nn::os::SystemEventType`。
- **真机证据（trim-b62，build/install/deploy 全 exit 0，日志 93 行）**：
  `[dm] >>> nnMain` → … → **`[dm] vi::GetDisplayVsyncEvent 接管：事件 0x70f2104d60，宿主按 60 Hz 触发`** →
  `CRASH sig=11 addr=0 pc=sdk+0x1ea684 lr=sdk+0x1ea684`。**vi 那条不再崩**，卡点又前移。
- **新卡点**：`sdk+0x1ea684` ∈ `_ZN2nn6applet23GetPreviousProgramIndexEv`（0x1ea670, size 0x44）：
  `bl 0x64f310`（槽 `0xb70c68` = **`_ZN2nn2am23GetApplicationFunctionsEv`**）→ `ldr x8,[x0]`，**x0 = 0**。
  ⇒ 和 `am::GetCommonStateGetter` 同一族：宿主该返回静态对象 + 全 0 虚表桩。这正是外部情报里
  「单一应用的 applet resource id、直接启动时无前序程序、无启动参数及无 DLC 列表」那一条，之前故意推迟，现在撞上了。
- 分级：「文件格式对」已核；「运行口径对」——nnMain/romfs/oe/vi-vsync 都过；「真机跑过」仍未出图，**阶段 B 走了一步**，B–F NOT RUN。

[BEGIN] na-045-readfile-b60
命令：`build.py --game-run --version trim-b60`；`adb install -r`；`deploy_totk.py --package <更新包> --dest fixed --device 3b864e51 --no-push --log-out …`
工作目录：D:\Switch\d2r-android
前置：HEAD=origin=cbddac8、工作区 CLEAN、机内 trim-b59、数据包已导入（`--no-push` 不重导）
改动：`dm/host/hle_fs.c` 新增两个 `nn::fs::ReadFile` 重载的强制接管（6 参带 ReadOption / 4 参无 out），共用 `h_fs_ReadFile`
预期结果：不再在 `nn::fs::detail::FileAccessor::Read` 里把句柄当 this；日志推进到读完 romfs / 进 NVN
日志路径：`D:\Switch\totk-work\device\game_b60.log`
回滚点：机内 trim-b59；代码 `git checkout cbddac8 -- dm/host/hle_fs.c`

## 2026-10-23 07:25 Asia/Shanghai — [SESSION] NA-044 定案并越过 DT_INIT：`>>> nnMain` 出证，新卡点进 nn::fs

- **NA-044 根因（定案，非推测）**：`dm/host/hle_svc.c` 里被接管的 `nn::mem::StandardAllocator::Allocate`
  转调「原版实现」时**写死了 D2R 的模块偏移 `sdk+0x2f9974`**。TotK 的 sdk 里该符号在 **0x1375f0**，
  而 0x2f9974 落在 `nn::codec::pcmDmx_ApplyFrame`（音频下混）**中间**，且那条指令正好是 `b 0x2f98e4` ——
  一跳进去就落进一段「按字节写两个数组」的循环，用残余寄存器写 `[x14+x1]`，x14 = main 基址 ⇒ 往 main 代码段偏移 0x408 写字 ⇒ SIGSEGV。
  与上一轮记录的现象逐条对上，但**上一轮的定性是错的**（当时判「目的指针被污染」，实际是宿主跳错了函数）。
- **证据链（每条都有命令/日志）**：
  1. 设备模块与本地副本**逐字节一致**：`adbd sha256sum` 与本地 `totk-work/guest-so/libdmguest_sdk.so` 都是 `4a58410801b8…`，
     排除「设备镜像与本地不同」。
  2. `0x2f98e8` 在全 sdk 里只有**一条** `strb w0,[x14,x1]`（`382169c0`），紧邻 `382169f2`，与 pc 原文一致。
  3. 但 `x14` 的反汇编来源是 `sub x14, x29, #0xb0`（栈），而现场 `x13/x15/x16` 与本函数本地初始化（`add x13,sp,#0x80` / `sub x15,x29,#0x70`）
     **全然不符** ⇒ 判定「函数序言根本没跑」= 跳到函数中途。用 `x1=0x408` 反证同理（该索引最大只到 263）。
  4. 新增崩溃打点（`x0..x30` + pc 原文四字 + `sp..sp+0x400` 栈扫描）出证：`fp(x29)==sp`、`[sp+8]=main+0x99d04`
     ⇒ 停在 main 的分配器包装器帧里；`x8=0x…7974`（= pc+0x8c）正是「被当作原版入口的那个地址」；`x30` 是宿主地址
     ⇒ 是**宿主** `hle_stdalloc_allocate` 转调出去的。
  5. 符号区间解析：`sdk+0x2f98e8` ∈ `nn::codec::pcmDmx_ApplyFrame`(0x2f93e0, size 0x1e3c)；`sdk+0x98f24` ∈ `__nnmusl_init_dso`；
     槽 `main+0x39793f0` 的导入是 `_ZN2nn3mem17StandardAllocator8AllocateEmm`（唯一提供者：sdk@0x1375f0）。
  6. 装载期槽位对拍（本轮新增，只读）：修前 main 0 / sdk 11 / subsdk0 31 条「不一致」，逐条查证**全是本模块自己有定义的
     拷贝重定位符号**（我的对拍一开始没跳过 `st_shndx!=0`）；修后 b59 = **main 2001/0、sdk 10/0、subsdk0 6537/0**。
- **修复**：`hle_stdalloc_allocate` 的原版入口改为**按符号解析**（`module_sym(sdk, "_ZN2nn3mem17StandardAllocator8AllocateEmm")`），
  符号缺失才退回老偏移 —— D2R 的路径一字未变（同一符号在 D2R 的 sdk 里就是 0x2f9974）。启动日志新增一行
  `分配器原版入口 <addr>（按符号，sdk 基址 <base>）`。
- **真机证据（trim-b58 / trim-b59 各一次，均 `deploy_totk.py --no-push` exit 0）**：
  `main: DT_INIT +0x10b9d80（init_array 10717 项）` → `分配器原版入口 …（按符号）` →
  `sdk: DT_INIT +0x400（83 项）` → `subsdk0: DT_INIT +0x20（45 项）` → **`[dm] >>> nnMain`**。
  NA-044 的成功判据（DT_INIT 走完 + 出现 `>>> nnMain`）**达成，且可复现（b58/b59 两次）**。
- **新卡点（下一次唯一动作）**：`CRASH sig=11 addr=0xc0 pc=sdk+0xa5940 lr=sdk+0xa93d0`。
  `pc 原文` 的 `b9402408` = **`ldr w8,[x0,#0x24]`**，而 x0 是个**句柄值**（b58 为 0x86 → addr=0xaa；b59 为 0x9c → addr=0xc0）。
  符号：`sdk+0xa5940` = `nn::fs::detail::FileAccessor::Read(Pm, l, void*, m, const ReadOption&)`（函数首条真指令就解引用 this），
  `sdk+0xa93d0` = `nn::fs::ReadFile(Pm, FileHandle, l, void*, m, const ReadOption&)`，
  链：`nnMain → main+0x20fe7c → nn::fs::ReadFile → FileAccessor::Read`。
  ⇒ 读文件的**句柄是由宿主 HLE 的 fs 接管发出来的**，而客体自己又走了 sdk 里真正的 `ReadFile`/`FileAccessor`
  路径（那条路径要的是 sdk 内部句柄表里的对象指针）。**接缝在「宿主 fs 接管的句柄 ≠ sdk 内部 FileAccessor 对象」**。
- 分级（照旧三级，别混着说）：「文件格式对」已核；「运行口径对」**本轮再进一步**（DT_INIT 全模块走完、进 nnMain）；
  「真机跑过」**仍未出图**，阶段 B–F 仍 NOT RUN。
- 本轮外部情报：无（全程本地反汇编 + 真机）。工具与中间产物在 `D:\Switch\totk-work\disasm-na044\`（仓库外，不提交）。

[BEGIN] na-044-disasm-b57
命令：`build.py --game-run --version trim-b57/58/59`；`adb install -r`；`deploy_totk.py --package <更新包> --dest fixed --device 3b864e51 --no-push --log-out D:\Switch\totk-work\device\game.log`
工作目录：D:\Switch\d2r-android
前置：HEAD=origin=ceb813a、工作区 CLEAN、`agent_handoff_check --resume/--verify` exit 0、设备 3b864e51 在线、机内 trim-b56、数据包已导入（全程 `--no-push`，不重导）
改动：① `dm/host/crash.c` 只读打点（x0..x30、pc 原文四字、栈扫描）；② `dm/host/loader.c` 只读对拍（导入槽 vs 符号定义）；
        ③ `dm/host/hle_svc.c` 业务修复（Allocate 的原版入口按符号解析，替代写死的 `sdk+0x2f9974`）
预期结果：定性 x14 来源并越过 main 的 DT_INIT
日志路径：`D:\Switch\totk-work\device\game_b57/b58/b59.log`
回滚点：机内 trim-b56；代码 `git checkout ceb813a -- dm/host/crash.c dm/host/loader.c dm/host/hle_svc.c`

[END] na-044-disasm-b57
退出码：`ci_checks.py` 16 通过 / 1 失败（交接控制面自干扰：工作区 DIRTY + 本条 BEGIN 未闭合，提交后恢复）；`build.py --game-run --version trim-b57/58/59` 均 exit 0
产物：`dm/android/build/D2R-Android-port.apk`（trim-b59，17,889,743 字节）；真机日志 `D:\Switch\totk-work\device\game_b58.log`(125 行) / `game_b59.log`
结果：SUCCESS —— NA-044 成功判据达成（`>>> nnMain` 出现两次），新卡点已定性
备注：b57 只加诊断；b58 修 Allocate 间接调用；b59 修对拍误报（只读诊断）。三次都是 `--no-push`，数据侧未动。

## 2026-10-23 01:40 Asia/Shanghai — [SESSION] 交接冻结：本轮（上游同步 + 外部巡检 + NA-044 方案定稿）完成，出交接提示词

- 本轮未改业务代码（全程只读情报 + 方案起草）。NA-044 的执行计划已定稿并写进本文件顶部与 HANDOFF「当前阻塞」：第 1 步反汇编 sdk+0x2f98e8 / main 调用链 → A–D 四分支 → trim-b57 复跑；**弱导入分道（上游 #66）与 svc 0x02 的 RELRO 语义故意不进第一批**（行为变化单批做）。
- 外部巡检全文见上条 01:15 [SESSION]。源码级核对补一条：本机 `walk_relr`（dm/host/loader.c:274–319）与 totk-mobile `host/relr.h`、rhythm-heaven-android 补丁三方语义逐条一致（偶项加基址 / 位图 bit−1 映射 / 位图后无条件推进 63 槽 / 0 槽跳过无效），且真机 relr 计数与本地逐位吻合 —— **RELR 修复定案，不再是嫌疑**。
- 控制面：HANDOFF 进入 `READY_FOR_HANDOFF`；observed_head = origin_head_at_checkpoint = `ec3a67e`（ec3a67efc86fb6bf73a15a922e961ec0bd2932cf）。
  本条提交后最终 HEAD = origin = **`c180b01`**（交接提示词按它写）。
- 提示词文件：`D:\Switch\TOTK_NEXT_PROMPT.md`（已重写为当前状态；旧版写 cd4c045 已过时）。
- 新会话首动作必须是读 `AGENTS.md` → `HANDOFF.zh-CN.md` → `agent_handoff_check.py --resume` + `--verify`（Administrator 环境变量带上 `DM_ANDROID_TOOLS`、`PYTHONIOENCODING`、`PYTHONUTF8`）。

## 2026-10-23 01:15 Asia/Shanghai — [SESSION] 上游同步 + 外部 TotK 移植巡检（只读情报，不改业务代码）

- **上游 `jhaizhou-ops/d2r-mobile` 自 NA-029 之后的新增**（gh 未登录，本机全用 GitHub 匿名 REST API；`gh auth login` 待用户补，恢复命令见下）：
  - **#66 `b84657b2` fix(loader): preserve null unresolved weak imports —— 对本项目有用**。`resolve_import` 增加 `weak` 参数：未解析的**弱**导入保持 0（guest 可感知“该可选函数不存在”），**强**导入才补桩；diff 里 `relocate()` 调用处传 `(s->st_info >> 4) == 2`，并带合成 ELF 的单测 `t_loader_weak.c`。我们 `dm/host/hle.c:33 resolve_import` / `dm/host/loader.c:135 resolve_sym` **没有弱符号分道**（NOP 未采纳于 NA-029，因当时 D2R 无此需求）；TotK 的可能力检测 API 若拿桩可能行为漂移，列为实施候选 —— 与「下一步唯一动作」里的“宿主 HLE 返回坏对象”嫌疑同族，实现时一并核对。
  - 以下上游改动**对本项目无用**（都是 D2R 产品侧）：西班牙语/俄语、Mac 悬停提示、Mac 打包、iCloud 启动、LiveContainer 代码签名区（`3af961d3`）、iOS 音频混音（`9393b00e`，将来 M4 音频可回看）、帧率无关。
  - `86b1315a` fix(nvn): honor image stride in buffer texture copies（#68）——**留给阶段 B/D 复核**：我们的 `nvn_vulkan` 拷贝路径若同样不认 stride，场的贴图拷贝可能坏。属“有用但非当前卡点”。
- **GitHub 全网搜 TotK / Switch 原生移植（按 AGENTS.md 第 12 条，只读思路与格式事实，代码一律不搬）**：
  - `OJZen/totk-mobile`（144★，Apache-2.0，最后推 2026-10-21）：**TotK v1.4.3 在 Apple silicon Mac/iPad 原生可读档游玩**，自述“装载器/改写器/NVN→Metal 沿用 d2r-mobile 设计”。`core/host/loader.c` 的 `relocate()` 仍只有 RELA/JMPREL **没有 RELR** —— 但他们也不会因此到不了 init_array，因为（见下条）他们在**改写器/准备链侧预展开 RELR**，装载时以普通重定位应用。
  - `kitcatkode/MacNativeGames`（同一家族社区仓，README 77 KB；描述写 totk android port wip，但目前出货是 Mac/iPhone/iPad）：`docs/v1.4.3-port.md`（46 KB）是 TotK 1.4.3 移植日志，**对我们当下最有价值的三条原文**：
    1. “新主模块与 SDK 的 RELR 重定位已展开，加载时共应用 554,281 项重定位” —— 数量级与我们（main 499,074 + sdk 15,007 + subsdk0 3,424 + rtld）吻合，**NA-044 的 RELR 语义获得独立印证**：偶地址项本身加基址、位图项覆盖后续 63 槽、处理完**无条件前移 63 槽**。`rhythm-heaven-android` 的补丁还记载了反例教训：按置位个数推进就整体错位（实测 sdk 6,383 个槽写坏地址、虚表全歪）——我们的 `walk_relr` 复核时按这条对账（本地已抽验，加载期计数与真机一致即为成立）。
    2. “新 SDK 的 GetInfo 28 返回没有额外 alias 保留区；新增 RELRO 只读权限及 PermissionLocked 处理；原生探针验证完整宿主页确实只读、4 KiB 逻辑边界、相邻可写页面保持可用、权限锁及无效请求拒绝” —— **TotK 1.4.3 的 SDK-21 新增了 RELRO/PermissionLocked 的 svc 语义**。我们 `dm/host/hle_svc.c:260` 对 `svc 0x02 SetMemoryPermission` 是**空操作直接返回 0**（D2R 够用）；Android 宿主页 4 KiB 与客体同粒度，比 Mac 的 16 KiB 页并集简单，可作为实施候选。**注意 RELRO 只是“把可写改只读”，漏实现不会导致写坏 —— 把它作为诊断线索之一，不当成根因**。
    3. “补齐单一应用的 applet resource id、直接启动时无前序程序、无启动参数及无 DLC 列表的语义” —— 与我们 `am::GetCommonStateGetter` 接管同族，将来真机出更栈深的 am 系问题时回来取。
  - `todwang96/rhythm-heaven-android`（**d2r-mobile 的 Android 补丁**，`patches/d2r-mobile-android.patch` 4 MB，Rhythm Heaven Switch v0 在 Android 可玩）：同一 loader 家族落到 Android 的完整记录。与我们当前реди-stage 相同的设施已验证：`mprotect(base, rx, R|X)` 封代码区、`mprotect(base+patch_off…, R|X)` 封补丁区、RELR 展开、`__builtin___clear_cache`、`force_check()` 的“条目未被引用”宽容模式、以及 **DM_SLOTLOG / DM_TLSHOOK / DM_ALLOCHOOK 三套宿主诊断钩子**（重点排查“导入槽被 HLE 换成宿主函数、宿主再用 sdk 内偏移转调 → 换游戏后偏移落在别的函数里”，与本会话 HANDOFF 中嫌疑 ② 同源）。其中 `DM_ALLOCHOOK` 直接验证 `nn::mem::StandardAllocator::Allocate` / `nn::nlibsdk::heap::CentralHeap::Alloc` / `nn::os::GetTlsValue` 三跳 —— 若 disasm 显示 x14 来自分配器/TLS 链，按这套钩子打点。
  - `rootrd/dontstarve-harmony`（Don't Starve Together 在 HarmonyOS，同一作者系，NVN→Vulkan 已到场景内可走）：同架构在第三台平台上跑通，佐证“这模型跨安卓系可行”；其 host 侧 `knsv` svc 表含 4.0 前信号量族 0x1A–0x1D 全集。
  - 移植雷达 `catoncat/d2r-port-radar` **已 404**（API、仓库都取不到了）：AGENTS.md 第 11 条的“定期看雷达”入口暂失效，改为上面四个仓库 + 搜索关键词人工巡检。
- **对本轮下一动作（NA-044 disasm）的直接增益**：反汇编 sdk+0x2f98e8 所在函数时，除 HANDOFF 已列两条嫌疑外，新增一条要顺带看的：**x14 若来自「分配器 / TLS / 系统对象链」或「宿主返回的对象」**，用 rhythm-heaven 的三套钩子方法（或者直接 `dm/host/hle_*` 现有 UNIMPL 计数）定位到具体哪个接口；若是函数指针表，「重定位结果像裸偏移（<16MB）**装载期就该报**」也在他们补丁里实现过，装载期红线提示可居低成本复用。

- 备忘：GH CLI 未登录，本巡检 API 配额（匿名 60/h）用去约 2/3；恢复登录命令：`gh auth login`（交互式，需要用户在浏览器授权）。巡检产物已在会话临时目录（`totk-relr.h`、`totk_kernel.c`、`totk_loader.c`、`macng_v143.md`、`d2r-android.patch` 等），**不进仓库、不提交**（保持“外部内容不落库”纪律），如需长期引用以 URL 为主。

## 2026-10-23 00:35 Asia/Shanghai — [SESSION] NA-044 续三：根因是宿主没实现 DT_RELR，补齐后过 init_array，新崩溃进了 sdk

- **根因定案**：`dm/host/loader.c` 的 `relocate()` 只遍历 `DT_RELA` / `DT_JMPREL`，**完全没有实现 `DT_RELR`**（tag 35=`DT_RELRSZ` / 36=`DT_RELR` / 37=`DT_RELRENT`）。TotK 三模块的相对重定位全部打包在这张表里，所以日志一直是 `relative=0`。
  本地解码（`D:\Switch\totk-work\patched-android\*.patched.bin`，只读脚本，不落盘产物）：
  main 9,357 个编码字 → **499,074 槽**（范围 0x3557000..0x3a13d40）、sdk 500 → 15,007、subsdk0 282 → 3,424；
  **init_array 的 10,717 项 100% 落在 RELR 里**，连 `__init_array_start/end` 边界槽（main+0x394b7b0 = 0x3557000、main+0x394b7a8 = 0x356bee8）也在。
- **完整解释**：客体 DT_INIT（`main+0x10b9d80`）里 `ldr x20,[...]` 取到的是**未加基址的链接期地址 0x3557000** →
  `ldr x8,[x20],#8` 读低地址 0x3557008（可读且为 0）→ `blr x8` → `pc=0`，x20 停在 0x3557008。与三条现象逐条对上：
  `addr=0`、`pc=0`、`x20=DT_INIT_ARRAY+8`。
- **顺手推翻两条旧假设**（别再按它们找）：①「打包器放置与 guest_elf.py 不一致」——`.so` 里 init_array 落位 0x4000+0x3557000 = 0x355b000，
  10,717 项与 patched.bin 逐字节一致、0 个零项（上轮 dd 读数是偏移算法问题，不是布局问题）；
  ②「设备上 guest .so 被清过」——`install_key_page` 在 Android 分支**根本不调用**（只在 iOS loader.c:399 / 桌面 loader.c:421），
  Android 只写前 DM_NSLOTS+1 个键槽并把键页 mprotect 成只读（`runtime.c:170-175`），与 0x3557000 不重叠。
- **修复**：`dm/host/loader.c` 新增回调式 RELR 解码器（`walk_relr`，偶数项 = 新游标、奇数项 = 覆盖随后 63 个槽的位图），
  `relocate()` 里**先 RELR 再显式表**（两张表零重叠，已离线核实），应用语义即 `*槽 += base`（**不跳过值为 0 的槽**：0 表示指向模块基址）；
  越界/格式一律 die。同步 `loader_hash_log()` 把 RELR 槽纳入地址无关哈希，否则 51.7 万未归一化槽会让 DM_LOADHASH 随 ASLR 变。
  `run_module_inits()` 在调 DT_INIT 前加体检打点；`dm/host/crash.c` 加「初始化游标」分类（x20 落在链接期/运行期数组区间的两种情形分开记，**打印原始值不减基址**）。
- **trim-b56 真机出证**（`deploy_totk.py --no-push` exit 0，`D:\Switch\totk-work\device\game.log` 73 行）：
  `main: reloc relative=0 relr=499074 abs/glob=1421 jump=649`、`sdk: relr=15007 abs/glob=11214 jump=7813`、`subsdk0: relr=3424 abs/glob=11832 jump=3816` —— 与本地预演逐位相同；
  `main: init_array 体检 base 0x7284a57000 数组 0x7287fae000 共 10717 项：零项 0、仍是相对值 0；首三项 0x7285b15e00 0x7285b15e60 0x7285b17510`（= base+0x10bee00 ✓）。
  另注 force 计数由 132 → **133 条命中**（多接通了一个本作有导入的符号），非故障。
- **新卡点（下一步）**：`CRASH sig=11 addr=main+0x408 pc=sdk+0x2f98e8 lr=0x730a2e666c`，
  bt `main+0x99d04 sdk+0x98f24 main+0x10b9e64 run_module_inits+0xa4`；崩溃指令 `sdk+0x2f98e8: strb w0,[x14,x1]`（同循环 `strb w18,[x15,x1]`、`add x18,x13,x11`），
  x14 = **main 基址 0x7284a57000**、x1 = 0x408。main 偏移 0x400 是代码（`87 e5 01 94` = `bl`），写它必崩 ⇒ **目的指针被污染成了模块基址**。
  下一步先反汇编 sdk+0x2f98e8 所在完整函数，查 x14 是「被调用方返回的指针」还是「某个全局槽被加了基址」（注意三模块各有约 5 个 RELR 槽原值为 0）。
- 仍未出图，未到 `>>> nnMain`；阶段 B–F 全部 NOT RUN。证据：`D:\Switch\totk-work\device\game.log`（73 行）。
- 备注：本次 `ci_checks.py` / `agent_handoff_check.py --verify` 在工作区 DIRTY + `[BEGIN]` 未闭合期间报 FAIL，是检查项自身对「进行中的长操作」的自干扰，提交后即恢复。

[END] na-044-relr-b56
结果：构建 trim-b56 exit 0（APK 17,873,359 字节同前）；`adb install -r` exit 0，versionName=trim-b56-android-port；
`deploy_totk.py --no-push` exit 0（counts 一致、跳过重导、点启动、拉回日志）；
预期 result：**成立** —— RELR 三计数精确吻合、init_array 体检全通过，原 `pc=0` 崩溃**不再出现**，崩溃点前移进 sdk。
日志路径：D:\Switch\totk-work\device\game.log（73 行）+ 本文件上面的 [SESSION] 记录
回滚点（仍有效）：基座包 totk-package.zip + APK trim-b55
结束时间：2026-10-23T00:35:00+08:00

[BEGIN] na-044-relr-b56
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b56；adb install -r …；deploy_totk.py --package … --dest fixed --device 3b864e51 --no-push --log-out D:\Switch\totk-work\device\game.log
工作目录：D:\Switch\d2r-android
前置（已完成）：分支 totk/scaffold，HEAD=origin=cd4c045，代码工作区 CLEAN；agent_handoff_check.py --resume/--verify 均 exit 0；设备 3b864e51 在线；机内 trim-b55。
改动：宿主缺失 DT_RELR（根因，见下一条 SESSION）——dm/host/loader.c 新增 RELR 解码器并在 relocate() 中先应用，同步 loader_hash_log 与 run_module_inits 体检打点；dm/host/crash.c 增加 init_array 游标分类。
预期结果：三个模块 relr 计数 = 499074 / 15007 / 3424；init_array 体检零项 0、仍是相对值 0；日志出现 >>> nnMain。
日志路径：D:\Switch\totk-work\device\game.log 与本文件对应的 [END] 记录
回滚点：机内 trim-b55；代码 git checkout cd4c045 -- dm/host/loader.c dm/host/dm.h dm/host/crash.c
记录时间：2026-10-23T00:20:00+08:00

## 2026-10-22 23:52 Asia/Shanghai — [SESSION] NA-044 续二：过了 am 单例，进 main init_array，崩在 pc=0

- **认出上一处空指针**：崩溃槽位 `0xb70db0` 的导入是 `_ZN2nn2am20GetCommonStateGetterEv`（`nn::am::GetCommonStateGetter`）。
  它在 sdk 里有定义（0x1ce4e0，72 字节）：读全局 `sdk+0xba1b90`（懒创建的单例），为 0 就直接返回 0 ——
  这个单例本该由被宿主接管成空操作的 `oe::Initialize` 建出来。
- **修复 4**：`dm/host/hle_sdkinit.c` 按本文件既有做法接管该接口，返回静态对象（64 项虚表全部指向「返回 0」的桩）。
  trim-b55 实测：SDK 初始化走完，`SetHeapSize：首次设堆成功 2642 MB`，`main: DT_INIT +0x10b9d80（init_array 10717 项）`。
- **当前卡点**：`CRASH sig=11 addr=0 pc=0 lr=main+0x10b9ec8`，bt `run_module_inits+0x94` ——
  main 的 DT_INIT 遍历 10,717 项 init_array 时 `blr` 了空指针（x8=0）。
- **方法学记录（可复用）**：guest `.so` 由 `guest_elf.py` 生成，`.dynamic` 只有 HASH/STRTAB/SYMTAB/SONAME，
  **没有 DT_RELA**；宿主的 `parse_dynamic` 是从**镜像里的 MOD0** 取动态段，所以「槽位 → 符号名」要在 `*.patched.bin`
  里解析（本会话已写成一次性脚本：读 MOD0 → 动态段 → DT_SYMTAB/DT_STRTAB → rela/jmprel 按 r_offset 匹配）。

### 证据（命令与退出码）

- `deploy_totk.py --no-push`（trim-b55）→ **exit 0**；`game.log` **72 行**：
  `SetHeapSize` + `main: DT_INIT ...（init_array 10717 项）` + `CRASH ... pc=0 lr=main+0x10b9ec8`。
- `build.py --game-run --version trim-b55` → exit 0（APK 17,873,359 字节）。
- 本地反汇编与符号解析（`llvm-objcopy` 包 ELF + `llvm-objdump`）：`0x1eade4`/`0x1ce4e0` 两处均已核对。

### 已排除 / 待查（本轮末尾的两个只读事实）

- **init_array 本身没有空项**：本地 `main.patched.bin` 的 `DT_INIT_ARRAY=0x3557000`、size `0x14ee8`
  （10,717 项），逐项扫描 **0 个空项**；项值是**镜像相对地址**（0x10bee00 / 0x10bee60 / 0x10c0510 …）。
- **`main: reloc relative=0`** —— 宿主对 main 应用了 0 条 RELATIVE 重定位，而 init_array 的项按常理要靠
  RELATIVE 变成运行期绝对地址。崩溃在 `blr x8` 且 x8=0、pc=0，与「项值是相对地址未加基址」并不完全吻合 →
  下一步要一起查：① 设备上那个模块的该区域字节（本轮按 `guest_elf.py` 的 `0x4000 + 0x3557000` 去 dd，
  读到的不是数组内容，说明**打包器放置与 guest_elf.py 不一致**，先确认实际放置再比）；② 宿主是否在某处把该区清零
  （`install_key_page` 只清键页 0x3ad0000..0x3ae0000，理论上不重叠）。
- 结论：**空指针来源还没定**，但范围已缩到「init_array 的运行期内容」这一处，不是数组项缺失。

### 还差什么

- 定位 init_array 里的空项（或 init 函数内部的空回调）→ 见 HANDOFF「下一步唯一动作」。
- 阶段 B–F 仍 NOT RUN；现在连图都没出（进程在 init 阶段崩）。


## 2026-10-22 23:40 Asia/Shanghai — [SESSION] NA-044 续：连过三道启动闸门，卡在 nninitStartup 空指针虚调用

- **起点**：用户手动点启动闪退，日志确认是 trim-b51 上的同一个 `Invalid image bounds`（修复未装）。
- **trim-b52（加载器边界修复）装上后**：`subsdk0: base 0x71fe11e000 size 0x670000` —— 三模块全装载，
  `main: reloc relative=0 abs/glob=1421 jump=649` 也过了；下一道是 `FATAL 强制接管清单有误`
  （`nnssl*`/`nnsocket*`/`oe*`/`time*` 等 D2R 专属服务「无任何引用」）。
- **修复 2**：`dm/host/loader.c` 的 `force_check` 改成**按导入事实判定** —— 逐条目查「本作是否有这个未定义符号导入」：
  有导入却没接管 → 仍 `die`（真 bug）；本作不导入 → 记超集、不再拦。trim-b53 实测
  `force: 132 条命中，116 条本作未导入（共享表的超集，非故障）`。
- **下一道**：`FATAL 产物没有 UI 观测门 OBS_UIMSG（需 r6 起的产物）` —— 该门是 **D2R main 0xb1dc60** 的固定点，
  TotK 的 main 没有（`main.gates.tsv` 为空）。
- **修复 3**：`dm/host/diag.c` 的 `uimsg_subscribe` 缺门时改为**提示 + 返回**（消息类诊断不工作），不再 abort；
  D2R 有门，行为不变。trim-b54 装上后启动推进到：Vulkan 初始化（surface 3168×1440、pipeline cache、PSO manifest）、
  `>>> nnosInitialize`、guest AS/heap/alias/stack、`>>> nninitInitializeSdkModule` + 7 个 init 接管（空操作）、
  `>>> nninitStartup`。
- **当前卡点（本轮终点）**：`CRASH sig=11 addr=0 pc=lr=sdk+0x1ead5c`（SIGSEGV，跳 0）。
  反汇编 `sdk+0x1ead58` 段：`bl 0x64f5a0` → `ldr x8,[x0]`（x0=0）→ `ldr x8,[x8,#0x130]` → `blr x8`；
  `0x64f5a0` 是 PLT 跳板（`adrp x16,0xb70000; ldr x17,[x16,#0xdb0]; br x17`），即**某个导入返回了空对象**。
  日志里**没有任何 UNIMPL 行** → 该符号被解析到了真实 HLE/强接管函数，是它返回了 0，而不是落到记名桩。

### 证据（命令与退出码）

- `adb install -r` trim-b52 → exit 0；`deploy_totk.py --no-push` → exit 0（导入已存在自动跳过、counts 一致）。
- 首跑日志 `D:\Switch\totk-work\device\game.log`：14 行（subsdk0 FATAL）→ trim-b53 22 行（force 通过）→
  trim-b54 **70 行**（Vulkan + nninitStartup + CRASH）。
- `llvm-objcopy -I binary ... sdk.patched.bin → sdk_raw.elf` + `llvm-objdump -D --start-address=0x1ead30`：
  得到 `0x1ead58 bl 0x64f5a0` / `0x1ead5c ldr x8,[x0]`；`0x64f5a0` 为 PLT 跳板（槽 0xb70db0）。
- `build.py --game-run --version trim-b52 / b53 / b54` → 三次均 exit 0（APK 17,873,359 字节）。

### 纠错记录

- 第一次读崩溃偏移用了 `llvm-objdump -b binary`（LLVM 不支持），改用 `llvm-objcopy` 包一层 ELF 再反汇编。
- 试图从包里 sdk 模块的 `.dynamic` 找 reloc 符号失败：guest `.so` 由 `guest_elf.py` 生成，只有 HASH/STRTAB/SYMTAB/SONAME，
  **没有 DT_RELA/DT_JMPREL** → 槽位→符号名的映射不在 `.so` 里（在改写器的重定位产物里），下一步要换路子。

### 还差什么 / 下一步

- 认出槽 `0xb70db0` 对应的导入符号（建议：`DM_IMPORTS=1` 跑一次看解析表，或解析改写器给 sdk 的重定位表），
  再修那个返回 0 的 HLE/强接管函数。**阶段 B–F 仍 NOT RUN**（Vulkan 已初始化，但没有出图）。


[END] na-044-device-run
结果：**推包与导入成功，开机在 subsdk0 加载处 FATAL；修复已构建（trim-b52），待真机复验。**
不是 exit 0 —— 流程在「点启动游戏→等 game.log」这段被宿主的硬失败截断（宿主 `die()` → abort），
`deploy_totk.py` 本身按设计 exit 0（它只负责推到日志出现那一步）。
逐段：
- 设备：`3b864e51`（PJD110 / 一加 12 / Android 16）；原装 trim-b46，本轮 `adb install -r` 换 **trim-b51**（b46 早于 NA-046，
  不能假设有「从推送的包导入」行）；加载器修复后又构建了 **trim-b52**（exit 0），**尚未安装到手机**。
- 空间：`/sdcard` 与 `/data` 各约 141.6 GiB 可用（推包后 125.0 / 导入后 107.2）。
- 推包：`adb push` 16.60 GiB → `/sdcard/Android/data/org.d2r.android.port/files/totk-package.zip`；
  `stat -c %s` = **17,825,708,024**，与本机一致（字节校验通过）。
- 导入：点「从推送的包导入」后约 13 分钟完成；完成标记在**外部**目录
  `/sdcard/Android/data/org.d2r.android.port/files/d2r-package/manifest.json`：
  `format=1 subgroup_size=64 counts game=9 romfs=304,243 shaders=24,535`，
  `bytes.game=81,598,218 romfs=17,026,724,605 shaders=646,871,659` —— 与本地包**逐项一致**。
  内部 `files/d2r-package/` 只有 `game/`（9 个文件，78 MB），符合设计。
- 开机：game.log 出现并有 14 行 → `main` 装载成功（gates 0 / base 0x733b297000 / size 0x3aecb80）、
  `sdk` 装载成功（gates 101 / base 0x733a0a8000 / size 0xc63cc0）→ **`[dm] FATAL Invalid image bounds`**（subsdk0）。
- **根因（已定位并修复）**：subsdk0 没有补丁点（`sites.tsv` 为空），重写器只追加 16 KiB 键页 →
  `patched.bin` 长度 = **0x670000** = `PATCH_OFF`；`dm/android/native/runtime.c` 的边界检查写的是
  `patch_off >= 镜像长度` 判死，把「没有补丁区」误判成越界（`guest_elf.py` 自己的校验允许 `<=`）。
  修复：改成 `>`（键页仍由 layout 校验保证在镜像内）。`build.py --game-run --version trim-b52` → exit 0。
- 待复验：trim-b52 装到手机后重跑 `deploy_totk.py --no-push`（导入已存在会自动跳过），读到阶段 B–F。
- 结束时间：2026-10-22T23:20:28+08:00

## 2026-10-22 23:20 Asia/Shanghai — [SESSION] NA-044：真机推包、导入完成、开机首跑暴露 subsdk0 加载闸门

- **真机终于接上**（外部阻塞解除）：`adb devices` 有 `3b864e51`；`totk_device_check.py` 的红项都是「还没导包」的正常态。
- **推包 + 导入一次成功**：16.60 GiB 推送后字节校验一致；界面一键导入约 13 分钟；
  手机上 manifest 的 counts 与本地包逐项相同（romfs 304,243 / shaders 24,535 / romfs 字节 17,026,724,605）。
- **首跑遇到三个只有真机才暴露的问题**（全部已修）：
  1. `adb devices` 的守护进程横幅（stderr 并进 stdout）被当成设备 → 误报「接了 3 台设备」；
     改成只认 `序列号<TAB>状态` 且状态字符合法，另加「未授权」的人话提示。
  2. `get-state` 走了 `adb shell`（设备上没有这个可执行文件，exit 127）→ 改成宿主机命令 `adb get-state`。
  3. 导入完成标记轮询了**内部** `files/d2r-package/manifest.json`（不存在）→ 改外部包目录；
     并加幂等：已导入就直接核对 counts、跳过重导（重导一次十几分钟起）。
  另：启动行文字带 `"▸  "` 前缀 + 真机 3168×1440 横屏列表被截断 → `launcher_row` 改后缀匹配并支持滚动查找。
- **开机首跑结果（分级写）**：**「真机跑过」到 sdk 装载为止** —— main/sdk 两个模块进内存，
  subsdk0 加载闸门 FATAL（`Invalid image bounds`）。不是数据问题：包内 328,788 条目与 counts 已核对；
  是加载器把「无补丁区的模块」误判越界（见上一条 [END] 的根因）。修复已编译进 trim-b52。
- **未验证**：阶段 B（NVN 接管）/ C（描述符集与着色器）/ D（合并句柄拆分）/ E（变体挑选）/ F（预排贴图）全部 **NOT RUN**。

### 证据（命令与退出码）

- `totk_device_check.py` → exit 1（红项：档位未写 / 模块缺 / 数据缺 / 日志缺 —— 全是「还没导」的正常态）。
- `adb install -r dm/android/build/D2R-Android-port.apk` → exit 0（versionName trim-b51 → 后换 trim-b52）。
- `deploy_totk.py --package <更新包> --dest fixed --log-out ...` → 推包与字节校验通过（17,825,708,024 一致）。
- `deploy_totk.py --no-push ...` → **exit 0**：外部 manifest counts 与本地包一致 ✓，跳过重导，点「启动游戏」，
  拉回 `D:\Switch\totk-work\device\game.log`（11 行；随后增长到 14 行并出现 FATAL）。
- `dm/android/tests/test_deploy_totk.py` → exit 0（13 用例，含滚动查找、外部标记、未授权/多设备负路）。
- `build.py --game-run --version trim-b52` → exit 0（APK 17,873,359 字节）。

### 纠错记录

- 第一版部署在 RDP 浮窗挡在前面时抓 UI，5 次都没找到导入行（dump 到的是 `com.microsoft.rdc.androidx`）；
  把启动界面拉到前台 + 加滚动后正常。**教训**：真机 dump 前先确认 `mCurrentFocus` 是本应用。
- 首跑把「导入完成」误判死等：标记位置写错（内部 vs 外部），已按实测改。

### 还差什么

- **trim-b52 未装、未复验**：下一步就是装它 + `--no-push` 复跑，读到阶段 B–F。
- 阶段 B–F 全部 NOT RUN；真机结论目前只到「main/sdk 装载 + subsdk0 闸门已修」。

### 下一步

唯一 READY 动作：**NA-044（续）** —— 装 trim-b52 → `--no-push` 复跑 → 读 stages A–F（详见 HANDOFF）。

[BEGIN] na-044-device-run
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\deploy_totk.py --package D:\Switch\totk-work\package-totk\totk-package-updated.zip --dest fixed --log-out D:\Switch\totk-work\device\game.log
工作目录：D:\Switch\d2r-android
前置（已完成）：设备 3b864e51 接上（PJD110 / Android 16）；`totk_device_check.py` 已跑（红项均为「还没导入」的正常态）；
`adb install -r` 装 trim-b51 成功（原为 trim-b46；不装的话 NA-046 的「从推送的包导入」行可能不存在）；
df 实测 /sdcard 与 /data 各约 141.6 GiB 可用。
预期结果：exit 0；推 16.6 GiB → 字节校验一致 → 档位锁 totk → 导入完成（counts 与本地包一致）→ 开机 → 拉回 game.log
（若导入超时/开机起不来，按退出码 5/6 记录，不重复重推）
日志路径：D:\Switch\totk-work\device\game.log 与本文件对应的 [END] 记录
回滚点：基座包 totk-package.zip + APK trim-b50（本轮先装了 trim-b51）+ 业务提交 3990687
记录时间：2026-10-22T22:29:00+08:00

## 2026-10-22 22:20 Asia/Shanghai — [SESSION] NA-052：推包开机一键化 + runbook（手机不在，纯离线）

- **开工前先对账**：上次会话上下文耗尽，交接没写完 —— `--verify` 报 4 个 FAIL（frontmatter
  `observed_head` 旧于实际 HEAD、工作区写 CLEAN 实际 DIRTY、清单为空）。`e2d8f3f` 之后还有两个
  纯控制面提交（`4d95b12`/`eeb1c1f`），且 09:30 留下一份未提交的 `deploy_totk.py` 重写（NA-052 WIP）。
  按 AGENTS.md 第 6/14 条先修 HANDOFF（单独提交推送 `596b690`），`--verify` 复跑 exit 0 后才动业务代码。
- **NA-052（已完成，业务提交 `3990687`）**：审查 WIP → 对真实更新包干跑 → 修一个真 bug →
  补回归 → 写 runbook → 跑闸门 → 提交。全程**没推包、没动基座包、没碰真机**。
  - 六项要求全落地：① adb 解析（`--adb` > `DM_ANDROID_TOOLS` > 仓内/工作区约定 > PATH）；
    ② 默认推 `/sdcard/Download/`（`--dest fixed` = 应用外部目录固定名，界面一键导入）；
    ③ 推前查 `/sdcard` 与 `/data` 空间（< 35 GiB 拦、< 40 GiB 警；导入实测 ~33.1 GiB）；
    ④ 推完 `stat -c %s`（退 `wc -c`）核对字节数；⑤ `--dry-run` 与真跑同一个 `main()`；
    ⑥ runbook 进 `docs/TOTK_PORT_PROGRESS.zh-CN.md` 第 12 节（五步 + 每步日志 + 回退基座包）。
  - **修的 bug**：启动行文字带 `"▸  "` 前缀（`LauncherActivity.java:364` 的 `"▸  " + text(...)`），
    WIP 的 `row_centre` 全等匹配在真机上必然失配、把自动化静默降级成人工点 → 改后缀匹配；
    干跑的假窗口也改成带前缀，保证干跑与真机同一套匹配逻辑。
  - **脚本依赖全部核对过源码**（不是凭印象）：`FIXED_PACKAGE`/`getExternalFilesDir`、
    `manifest.json` 解包最后才写、`files/game.log` 内部存储 + O_TRUNC、界面行文字中英各一对。

### 证据（命令与退出码）

- `deploy_totk.py --dry-run --package <更新包>` → **exit 0**：21 条 adb 命令原样打印；
  包内清单 2.3 秒读出（format=1 / romfs 304,243 / shaders 24,535 / subgroup_size=64）；
  字节校验 17,825,708,024 通过；`--dest fixed` 24 条命令同样 exit 0。
- `dm/android/tests/test_deploy_totk.py` → **exit 0**（10 用例：干跑两条 dest、后缀匹配、df 解析、
  字节不一致 / 空间不足 / 没设备 / 多设备 / adb 解析优先级 / conf 改写 / 包不存在）；
  带与不带 `DM_ANDROID_TOOLS` 两种环境都跑过。
- `ci_checks.py` → **17 项通过 / 0 失败**（原 16 + 新增 `t_deploy`；JDK 两条 Java 闸门真跑真过）。
- `build.py --game-run --version trim-b51` → **exit 0**，APK 17,873,359 字节（长操作
  `[BEGIN]/[END] na-052-trim-b51` 已闭合；与 trim-b50 同大小 —— 只改 Python 工具）。
- `agent_handoff_check.py --verify` → exit 0；`git diff --check` → exit 0（修了 WIP 文件 EOF 多余空行后才过）。
- 设备：`adb devices` 空（本轮未重复实测，以上一轮 06:44/07:05 的 exit 2 记录为准）→ **真机行为 NOT RUN**。

### 纠错记录

- 第一次跑 `ci_checks` 用错 `DM_ANDROID_TOOLS`（点号路径 `D:\Switch.tools\android` 不存在）→
  JDK 闸门被跳过（正是交接文档警告的假绿）；真实工具链是 `D:\Switch\.tools\android`。
- `t_deploy` 在带 `DM_ANDROID_TOOLS` 的环境下红了一条：测试的「找不到 adb」负例没屏蔽环境变量 → 补屏蔽后过。
- 写 frontmatter 时把 `origin_head_at_checkpoint` 写成补零假哈希 → `git rev-parse` 取真值改回。

### 还差什么

- **真机**：NOT RUN（唯一外部阻塞：一加 12 的 adb/PnP 断开）。
- **NA-044（唯一 READY 动作）**：手机一回来，`totk_device_check.py` → `deploy_totk.py --dest fixed`
  推更新包 → 导入 → 开机 → 读 `files/game.log`（详见 HANDOFF 与进度文档第 12 节）。

### 下一步

唯一 READY 动作：**NA-044 = 真机推包开机**（目标包 = `totk-package-updated.zip`；不推基座包）。

[BEGIN] na-052-trim-b51
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b51
工作目录：D:\Switch\d2r-android
预期结果：exit 0，APK 落在 dm/android/build/D2R-Android-port.apk（版本号比 trim-b50 递增；
NA-052 只改 dm/android/tools/ 下的 Python 工具与测试，不碰 C/Java 源码，APK 大小应与 trim-b50 同级）
日志路径：本文件对应的 [END] 记录
回滚点：596b690（控制面）；业务未提交，回退即 git checkout -- 对应文件
记录时间：2026-10-22T21:58:00+08:00

[END] na-052-trim-b51
退出码：0
产物：dm/android/build/D2R-Android-port.apk（17,873,359 字节，2026-10-22 22:12:58，与 trim-b50 同大小 ——
NA-052 只改 dm/android/tools/ 下的 Python 工具与测试，不碰 C/Java 源码；zipalign 的
"WARNING: header mismatch" 与以往各批相同，是既有警告）
结果：SUCCESS
备注：构建期间本文件只有本条 [BEGIN]/[END]，无其它未闭合长操作。

## 2026-10-22 21:51 Asia/Shanghai — [SESSION] 对账修正：HANDOFF ↔ Git 不一致（NA-052 开工前）

- **发现的不一致**（`agent_handoff_check.py --verify` exit 1，4 个 FAIL）：
  ① frontmatter `observed_head: e2d8f3f` 旧于实际 HEAD —— `e2d8f3f` 之后还有两个纯控制面提交
  （`4d95b12 docs: checkpoint NA-050...`、`eeb1c1f docs: refresh the device blocker evidence`）；
  ② frontmatter `code_worktree: CLEAN` 与实际 DIRTY 不符；③「代码工作区」清单为空，实际有
  ` M dm/android/tools/deploy_totk.py`。
- **原因**：上次会话上下文耗尽，交接没写完 —— 它 09:30 把 `deploy_totk.py` 重写成 NA-052 要的
  「推包→导入→开机→读日志」一条命令（+530 行，含 adb 解析、`--dry-run`、空间预检、推送后字节校验），
  没提交、没写 runbook、没接回归，只留在了工作区。
- **处置**（按 AGENTS.md 第 6/14 条：先修 HANDOFF、不丢未提交改动、不用 `git reset --hard`）：
  更新 frontmatter（`observed_head`/`origin_head_at_checkpoint` → `eeb1c1f`、`code_worktree` → `DIRTY`）、
  当前快照与「代码工作区」清单登记该 WIP，控制面单独提交推送；`--verify` 复跑 exit 0 后才动业务代码。
- **证据**：`git rev-parse HEAD` / `git rev-parse origin/totk/scaffold` 均为
  `eeb1c1fffbb68fd88846930d805a68344559703d`；`git status --short --untracked-files=all` 仅
  ` M dm/android/tools/deploy_totk.py`；`stat` 该文件 mtime 2026-10-22 09:30:00。
- **下一步**：NA-052 继续 —— 审查 WIP → 用更新包跑 `--dry-run` → 补回归（`dm/android/tests/` +
  `ci_checks`）→ 写「开机操作手册」→ 闸门 → 业务提交。**不推包、不动基座包**（真机推包是 NA-044）。

[END] na-051-preflight
结果：exit 0 —— **7 条闸门全绿，结论行「全绿 → 可以推机」**（对象是**更新包** `totk-package-updated.zip`）。
逐条：APK 17,873,359 字节（绿）| 数据包清单 exit 0（2.3 秒，game 9 / romfs 304,243 / shaders 24,535）|
数据包条目 exit 0（romfs 17,026,724,605 字节）| 着色器包 exit 0（660.8 秒；11,447 meta / 1,640 份变体名单 / 5,913 个完整键；
c[2] 偏移 32 个全在 [0x20,0x120) 且 8 字节对齐）| 变体键链 exit 0（358.9 秒；归档里 47,260 个着色器，
宿主口径完整键/c1/控制段长度不匹配均为 0；变体名单 5,913 个键，缺文件 0、不在索引里 0；「结果：一致 ✓」）|
NVN 接口覆盖 exit 0（缺名字 0 / 空实现 0 / 缺实现 0）| ci_checks exit 0（**16 项通过 / 0 失败**）|
交接面 exit 0（VERIFY OK）。
基座包未被改动：17,842,231,302 字节、mtime 2026-10-21 03:15:32（与合并前一致）。
输出文件：D:\Switch\totk-work\package-totk\preflight-updated2.txt（2,090 字节）。
结束时间：2026-10-22T07:06:40+08:00

## 2026-10-22 07:06 Asia/Shanghai — [SESSION] NA-050 / NA-051：overlay 合进宿主包（更新包产出）+ 完整预检全绿

- **NA-050（已完成）**：新增自有工具 `dm/tools/totk_merge_package.py`，把 NA-049 导出的 14,397 个被替换文件
  合进基座包，跳过 727 个 `removed` 路径，产出**更新包** `D:\Switch\totk-work\package-totk\totk-package-updated.zip`
  （**17,825,708,024 字节 / 328,788 条目** = game 9 / romfs 304,243 / shaders 24,535）；配套回归
  `dm/android/tests/test_merge_package.py`（已接进 `ci_checks` 的 `t_mergepkg`）。
- **NA-051（已完成）**：用更新包跑完整预检，**7 条闸门全绿 → 可以推机**。
- **附带修掉的一个会自我误报的红**：预检的「变体键链」在 06:23 那次被判「超时 1800 秒」，
  同一命令单独跑是 exit 0（本机实测 358.9 秒）→ 是执行环境（机器负载/休眠）不是数据缺陷；
  已把闸门超时放宽到 3600 秒（`totk_preflight.py --gate-timeout`）。
- **附带修掉的两个坑**：① 长操作留的 `[BEGIN]` 会让**它自己内部**的交接校验报红
  → 新增 `DM_HANDOFF_PENDING_OPS` 点名豁免（默认行为不变，负向测试仍过）；
  ② 预检不带 `DM_ANDROID_TOOLS` 时 `ci_checks` 会跳过 JDK 闸门 → 跑预检必须带这个环境变量。

### 证据（命令与退出码）

- `totk_merge_package.py --base-package <基座包> --overlay-manifest <清单> --overlay-dir <导出目录> --output <更新包> --json` → **exit 0**；
  报告 `merge-report.json`：replaced 14,397 / dropped 727 / entries 328,788 / bytes 17,825,708,024。
- **独立抽样复核**（本会话，sha256 逐字节比）：240 个随机 `added`/`changed` + 2 个「同大小但内容被替换」的老样本
  （`TerrainArc/StartIsland.tscb`、`UI/Map/MainField/U_06-03_04.bntx.zs`）与导出目录**全部一致**；
  40 个随机 `unchanged` 与基座包**逐字节相同**；727 个 `removed` 路径在包里 **0 残留**。
- **两条独立路径互相印证**：更新包 `manifest.json` 的 `bytes.romfs` = 17,026,724,605，
  与 BKTR 更新映像文件表总字节**逐字节相等**；条目数 328,752 + 763 − 727 = 328,788 ✓。
- **代码与数据现在同一次构建**（此前不是）：包里 `game/` 的模块改自**更新**（v1.4.2）的 `main` NSO
  （`patched-android/main.patched.bin` 头 0x20 build id `f40300aa001440f9f30301aa616301d0`
  与 `nso/upd_main.img` 逐字节相同，本体的 `base_main.img` 不是它）→ 「v1.4.2 代码 + 本体数据」的错配已消除。
- 完整预检 → **exit 0，7 条全绿**（逐条见上面那条 `[END] na-051-preflight`）。
- `ci_checks.py` → **16 项通过 / 0 失败**；`agent_handoff_check.py --verify` → exit 0；`git diff --check` → exit 0。
- 代码提交并推送：`e2d8f3f totk: merge the BKTR overlay into the host data package`。
- `build.py --game-run --version trim-b50` → **exit 0**，APK 17,873,359 字节（2026-10-22 07:08:14）。
- 设备：`adb devices` 为空、`totk_device_check.py` exit 2（手机没接上）→ **真机行为 NOT RUN**。

### 纠错记录

- 第一次写 HANDOFF 时用 `s.index("## 下一步唯一动作")` 定位，命中了正文里带反引号的那一处，
  把「当前快照」整段冲掉了 → `git checkout -- docs/HANDOFF.zh-CN.md` 还原后改成**按整行精确匹配**定位。
- 预检第一次跑时 `ci_checks` 报 3 个错，是 HANDOFF 的「代码工作区」清单没跟上新写的文件 → 先提交代码、再同步清单。

### 还差什么

- **真机**：NOT RUN（外部阻塞：一加 12 的 adb/PnP 断开；`adb devices` 空）。
- **NA-052（下一个 READY 动作）**：把「推包 → 导入 → 开机 → 读日志」做成一条命令 + 一页纸 runbook，
  并把 `deploy_totk.py` 改到适配更新包（adb 解析、默认外部目录 `/sdcard/Download/`、空间预检、推送后校验、--dry-run）。

### 下一步

唯一 READY 动作：**NA-052 = 推包开机这一段的一键化与 runbook**（详见 HANDOFF）。


[BEGIN] na-051-preflight
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\totk_preflight.py --package D:\Switch\totk-work\package-totk\totk-package-updated.zip --shaders D:\Switch\totk-work\package-totk\shaders --code D:\Switch\totk-work\shaders-index5\code --bfsha D:\Switch\totk-work\shaders-out --index D:\Switch\totk-work\shaders-index5\shader_index.tsv
工作目录：D:\Switch\d2r-android
预期结果：exit 0，7 条闸门全绿，结论"可以推机"（重点看"变体键链"这次是 exit 0 而不是超时）。
日志路径：D:\Switch\totk-work\package-totk\preflight-updated2.txt 与本文件对应的 [END] 记录
记录时间：2026-10-22T06:48:32+08:00

> 只追加，不覆盖。最新记录放在最上方。
> 当前状态以 [HANDOFF](HANDOFF.zh-CN.md) 为准。

[BEGIN] na-050-preflight
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\totk_preflight.py --package D:\Switch\totk-work\package-totk\totk-package-updated.zip --shaders D:\Switch\totk-work\package-totk\shaders
工作目录：D:\Switch\d2r-android
预期结果：exit 0，7 条闸门全绿，结论"可以推机"。
日志路径：本文件对应的 [END] 记录
记录时间：2026-10-22T00:45:46+08:00

[END] na-050-preflight
结果：exit 1（**不是包的问题**，两个红项都是本次执行方式造成的）：
  ① 交接面红：预检在运行期间我自己才写入这条 [BEGIN]，它内部的 agent_handoff_check 看到"长操作 BEGIN 未闭合"；
  ② ci_checks 红：预检没继承 DM_ANDROID_TOOLS，JDK 闸门被跳过（输出里出现 C:\Users\techjin\dm-work\tools\android\jdk）。
  与包有关的闸门全绿：数据包清单 exit 0（game 9 / romfs 304,243 / shaders 24,535）、数据包条目一致、
  着色器包 exit 0（584.7 秒）、NVN 覆盖 exit 0、APK 绿；"变体键链"黄项是因为少传 --code/--bfsha/--index。
  处置：闭合本条后，用**完整档**参数 + DM_ANDROID_TOOLS 重跑（见下一条记录）。
结束时间：2026-10-22T00:50:57+08:00

[BEGIN] na-050-merge-package
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\tools\totk_merge_package.py --base-package D:\Switch\totk-work\package-totk\totk-package.zip --overlay-manifest D:\Switch\totk-work\overlay\totk-overlay.tsv --overlay-dir D:\Switch\totk-work\overlay\export --output D:\Switch\totk-work\package-totk\totk-package-updated.zip --json
工作目录：D:\Switch\d2r-android
预期结果：exit 0；新包 totk-package-updated.zip，条目 game 9 / romfs 304,243 / shaders 24,535；727 个 removed 路径不在包里；14,397 个 overlay 路径大小与清单一致；基座包不被改动。
日志路径：D:\Switch\totk-work\package-totk\totk-package-updated.zip 与本文件对应的 [END] 记录
记录时间：2026-10-22T00:33:38+08:00

[END] na-050-merge-package
结果：exit 0；新包 D:\Switch\totk-work\package-totk\totk-package-updated.zip（17,825,708,024 字节），条目 328,788 = game 9 / romfs 304,243 / shaders 24,535 / manifest.json 1；替换 14,397、删除 727。
交叉印证：新包 manifest.bytes.romfs = 17,026,724,605，与 BKTR 更新映像文件表的总字节逐字节相等。
结束时间：2026-10-22T00:39:00+08:00

## 2026-10-22 00:32 Asia/Shanghai — [SESSION] NA-049：修正 changed 口径并导出被替换的文件

- 结果：把 `changed` 的判定从"按大小"换成"虚拟区间与重定位表 `isPatch=1` 区域相交"，找回 **6,656 个同大小但内容被替换的文件**（原口径会永久漏掉它们）；清单重算为 added 763 / changed 13,634 / unchanged 289,846 / removed 727。
- 导出：14,397 个文件、474,841,307 字节到仓库外 `D:\Switch\totk-work\overlay\export\`，逐文件与清单核对一致。

### 证据（命令与退出码）

- `totk_bktr.py ... --overlay-manifest <TSV> --export-overlay <目录> --json` → exit 0。
- `build_package.py overlay <TSV> --romfs <导出目录> --statuses added,changed` → exit 0，`checked_against_romfs=14397`。
- 独立复核脚本：样本 zstd→SARC 1,511 条；`TerrainArc/StartIsland.tscb` 与 `UI/Map/MainField/U_06-03_04.bntx.zs` 导出内容与本体**不同**（同大小）；`Pack/ZsDic.pack.zs` 确认为 unchanged、不在导出集。
- 可复现性：第二次导出 added 子集，与首轮 **763/763 逐字节相同**。
- `ci_checks.py` → **15 项通过 / 0 失败**；`build.py --game-run --version trim-b49` → **exit 0**（APK 17,873,359 字节，长操作 `[BEGIN]/[END] na-049-trim-b49` 已闭合）；`agent_handoff_check.py --verify` → exit 0；`git diff --check` → exit 0。
- 代码提交并推送：`93b2d3c totk: export the replaced files and classify them by patch region`。

### 纠错记录

- 首次 `ci_checks.py` exit 1：改了测试文件但没同步 HANDOFF 的工作区清单 → 补清单后 15/0。
- 工具的导出进度行原本写 stdout，会污染 `--json` 输出 → 改到 stderr；`--json` 现在是纯 JSON。
- HANDOFF_LOG 的 `[END]` 第一次插到了 `[BEGIN]` 中间 → 已重排为成对且内容完整。

### 还差什么

- **NA-050**：把 overlay 合进宿主数据包（新增 763、替换 13,634、删除 727），产出新包并跑 `inspect` + `totk_preflight.py`。
- 真机：NOT RUN；外部阻塞仍是一加 12 的 adb/PnP 断开。

### 下一步

唯一 READY 动作：**NA-050 = overlay 合并成宿主数据包**（详见 HANDOFF）。

[BEGIN] na-049-trim-b49
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b49
工作目录：D:\Switch\d2r-android
预期结果：构建 exit 0，产出 APK；随后复跑 ci_checks / agent_handoff_check / git diff --check。
日志路径：D:\Switch\handoff-build-check.log 与本文件对应的 [END] 记录
记录时间：2026-10-22T00:24:26+08:00

[END] na-049-trim-b49
结果：exit 0；APK D:\Switch\d2r-android\dm\android\build\D2R-Android-port.apk（17,873,359 字节，2026-10-22 00:25:36）。
结束时间：2026-10-22T00:25:52+08:00

[BEGIN] na-049-export-overlay
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\tools\totk_bktr.py <更新 NCA> --keys <prod.keys> --base <本体 NCA> --overlay-manifest D:\Switch\totk-work\overlay\totk-overlay.tsv --export-overlay D:\Switch\totk-work\overlay\export --json
工作目录：D:\Switch\d2r-android
预期结果：导出 added+changed 共 14,397 个文件、474,841,307 字节到仓库外目录；逐文件大小与清单一致；样本 Mals/USen.Product.142.sarc.zs 头 4 字节为 28b52ffd。
日志路径：D:\Switch\totk-work\overlay\export\ 与本文件对应的 [END] 记录
记录时间：2026-10-21T20:52:25+08:00

[END] na-049-export-overlay
结果：exit 0；导出目录 D:\Switch\totk-work\overlay\export\ 共 14,397 个文件、474,841,307 字节（与清单 added+changed 完全一致）。
校验：build_package.py overlay <清单> --romfs <导出目录> --statuses added,changed → exit 0，checked_against_romfs=14397。
样本：Mals/USen.Product.142.sarc.zs 1,798,330 字节、头 28 b5 2f fd、字典 id=1 解出 SARC 1,511 条；Pack/ZsDic.pack.zs 为 unchanged（108,344 字节），不在导出集内。
发现并修正：工具的进度行原本写 stdout，会污染 --json 输出（已改到 stderr）；导出期间同时确认“按大小判定 changed”会漏 6,656 个同大小但被替换的文件，判定口径已改为重定位表 isPatch=1 区域相交。
结束时间：2026-10-21T23:37:29+08:00

## 2026-10-21 20:40 Asia/Shanghai — [SESSION] NA-048：overlay 元数据清单与校验入口完成

- 结果：`totk_bktr.py --overlay-manifest` 生成 26,549,605 字节 TSV，共 304,970 条正文状态行（另有 3 行头）：updated 304,243 / base 304,207 / added 763 / removed 727 / changed 6,978 / unchanged 296,502。样本 `Mals/USen.Product.142.sarc.zs` = added、1,798,330 字节；`Pack/ZsDic.pack.zs` = unchanged、108,344 字节。
- `build_package.py overlay` 只消费清单，不读虚拟偏移正文、不生成 zip；可选 `--romfs` 核对非 removed 文件路径与大小。合成回归覆盖合法清单、坏尺寸、路径逃逸；CI 新增 `t_overlay`。

### 证据（命令与退出码）

- `totk_bktr.py ... --overlay-manifest D:\Switch\totk-work\overlay\totk-overlay.tsv --json` → exit 0。
- `build_package.py overlay D:\Switch\totk-work\overlay\totk-overlay.tsv` → exit 0；产物 `overlay-check.json`。
- `dm/android/tests/test_overlay_manifest.py` → exit 0；坏尺寸负例 exit 1（按设计）。
- `ci_checks.py` → **15 项通过 / 0 失败**；`agent_handoff_check.py --verify` → exit 0；`git diff --check` → exit 0。
- `build.py --game-run --version trim-b48` → **exit 0**，APK 17,873,359 字节；长操作已闭合 `[BEGIN]/[END] na-048-trim-b48`。
- 代码提交并推送：`e800e97 totk: validate a metadata-only overlay manifest`。

### 纠错与边界

- 首次生成命令因 PowerShell `Out-File` 先于父目录创建而失败，修正后成功；overlay 校验首次因漏收 `unchanged` 键 exit 1，修正后 exit 0。
- **这不是覆盖包**：只证明“清单格式与差异统计对”；正文导出、全量包合并、真机运行均为 `NOT RUN`。

### 下一步

唯一 READY 动作：**NA-049 = 只导出 added+changed 的 7,741 个文件（455,088,154 字节）到仓库外并逐文件校验**。


[BEGIN] na-048-trim-b48
命令：D:\Switch\.tools\venv\Scripts\python.exe dm\android\tools\build.py --game-run --version trim-b48
工作目录：D:\Switch\d2r-android
预期结果：构建 exit 0，产出 APK；随后复跑 CI / agent_handoff_check / git diff --check。
日志路径：D:\Switch\handoff-build-check.log（控制台构建输出另存于本会话）
记录时间：2026-10-21T20:34:18+08:00

[END] na-048-trim-b48
结果：exit 0；APK D:\Switch\d2r-android\dm\android\build\D2R-Android-port.apk（17,873,359 字节，2026-10-21 20:34:18）。
结束时间：2026-10-21T20:34:56+08:00

## 2026-10-21 19:09 Asia/Shanghai — [SESSION] NA-047：BKTR 运行读取口径解开，更新文件表可读

- 会话目标：手机不在，只做不需要真机的工作；把更新包 BKTR 从“结构已定位”推进到“可按虚拟映像读文件表”。
- 结果：重定位按 `isPatch` 在更新载荷/本体 RomFS 段之间选源；子段表的 offset 是**载荷物理偏移**，每个子段把自己的 `ctr` 写入 AES-CTR 低 32 位，跨子段必须拆读。更新 RomFS 数据区 `0x1FE0000`，文件表解析为 **304,243** 个文件（本体 304,207），新增 763 / 删除 727 / 同名大小改变 6,978。样本 `Mals/USen.Product.142.sarc.zs`（1,798,330 字节）读出 zstd 帧 `28 b5 2f fd`，字典 id=1 解出 SARC 1,511 条。真机：**NOT RUN**。工具代码已提交并推送：`f979784 totk: read the patched romfs through bktr relocations`。

### 证据（命令与退出码）

- `git ls-remote https://github.com/SciresM/hactool.git HEAD` → exit 0；只读参考格式事实，代码未复制。克隆后补 `git config --global --add safe.directory`，`git -C D:\Switch\totk-work\ref-hactool log --oneline -3` → exit 0。
- `python dm/tools/totk_bktr.py <更新 NCA> --keys <prod.keys> --base <本体 Program NCA> --json`
  → **exit 0**，产物 `D:\Switch\totk-work\bktr-updated.json`；其中 `updated_romfs` 给出上述文件计数与样本。
- 只读样本复核脚本（读更新表路径、zstd 字典、SARC 条目）→ exit 0，输出 `dict 1 content 11443096 magic SARC sarc_entries 1511`。
- `python dm/android/tools/build.py --game-run --version trim-b47` → **exit 0**，APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python dm/android/tools/ci_checks.py` → **14 项通过 / 0 失败**；`tools/agent_handoff_check.py --verify` → exit 0；`git diff --check` → exit 0。

### 还差什么

- **NA-048**：把 304,243 条更新路径/大小变成宿主包可用的 overlay 清单，并接到重打包入口；本体数据仍可先开机，补丁不阻塞主线。
- IVFC 各层哈希尚未逐块重算；这是“运行读取口径”证据，不是哈希树全验。
- 真机：NOT RUN；外部阻塞仍是一加 12 的 adb/PnP 断开。

### 下一步

唯一 READY 动作：**NA-048 = 更新文件表 → overlay 清单/重打包入口**（详见 HANDOFF）。

## 2026-10-21 18:06 Asia/Shanghai — [SESSION] NA-046：推送包可直接导入，构建与全部离线闸门通过

- 会话目标：手机不在，只做不需要真机的工作；收口接手时发现的固定路径导入改动。
- 结果：启动界面新增「从推送的包导入」，读取应用外部目录的 `totk-package.zip`；缺失文件明确提示先 `adb push`。两条导入路径现在共用同一套 `PackageArchive.unpack(InputStream, ...)` 契约，流由外层 try-with-resources 关闭，取消/异常清理仍由原流程负责。真机行为 **NOT RUN**。

### 证据（命令与退出码）

- `python dm/android/tools/build.py --game-run --version trim-b46` → **exit 0**；
  APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python dm/ios/tools/dm_i18n.py --header > dm/host/dm_i18n_tab.h` → exit 0；
  `dm/ios/tools/dm_i18n.py --check` → exit 0（206 条）。
- `python dm/android/tools/ci_checks.py` → **14 项通过 / 0 失败**。
- `python tools/agent_handoff_check.py --verify` → **exit 0**；`git diff --check` → exit 0。
- 代码提交并推送：`5376efc totk: import a package pushed to the external directory`；
  `git rev-parse HEAD origin/totk/scaffold` 同为 `5376efce2f79ccc2e2b2ba3b5bf4ea5a697b6582`。

### 纠错记录

- 用户消息给出的解释器路径 `D:\Switch.tools\venv\Scripts\python.exe` 与工具路径
  `D:\Switch.tools\android` 均不存在；实际是 `D:\Switch\.tools\venv\Scripts\python.exe`
  与 `D:\Switch\.tools\android`。第一次按错误路径跑 `--resume/--verify` 与 `build.py` 都是
  “命令不存在” / `FileNotFoundError`，不是业务失败。
- 接手时旧 HANDOFF 写着 CLEAN，Git 实际 DIRTY；先按协议修 HANDOFF，`--verify` 回到 exit 0
  后才处理业务代码。

### 还差什么

- 真机的一切：NOT RUN；唯一外部阻塞仍是一加 12 接不上（adb 空，PnP Code 45）。
- 更新包 BKTR 补丁、Mac 侧翻译链重建、运行期三件事仍待办。

### 下一步

唯一 READY 动作：**NA-047 = BKTR 虚拟偏移坐标系的离线定位**（详见 HANDOFF）。

## 2026-10-21 17:52 Asia/Shanghai — [SESSION] 接手核对：HANDOFF 与 Git 冲突，已按协议修正交接状态

- 会话目标：继续 TotK 原生移植；手机断开，只做不需要真机的工作。
- 接手核对：先读 `AGENTS.md` 与 HANDOFF；`agent_handoff_check.py --resume` exit 0、
  `--verify` exit 1（4 项）——HANDOFF 写着 `observed_head=82d492e` / `CLEAN`，
  Git 实际是 `totk/scaffold = origin/totk/scaffold = dac588d`，并有两个未提交代码文件。
  用户消息里的解释器路径 `D:\Switch.tools\venv\Scripts\python.exe` 不存在；
  实际 3.12 venv 是 `D:\Switch\.tools\venv\Scripts\python.exe`（`--version` = 3.12.14）。

### 修正了什么

- 按「Git 与 HANDOFF 冲突时先修 HANDOFF、不写业务代码」处理：
  frontmatter 与当前快照已改成真实 HEAD `dac588d`、origin 同 HEAD、代码工作区 `DIRTY`，
  两个未提交文件已逐条入账：
  `dm/android/java/org/d2r/android/port/LauncherActivity.java`、`dm/i18n/ui_text.tsv`。
- 现有改动看起来是未收口的离线原子任务「固定路径导入」（把 zip 推到应用外部目录后直接导入），
  没有删除或覆盖；唯一 READY 动作改成 **NA-046 = 收口该改动并过构建/CI/交接闸门**。
  NA-044（手机接上后推包开机）与 BKTR / Mac 清单继续排队。

### 证据（命令与退出码）

- `git rev-parse HEAD origin/totk/scaffold` → 两者均为
  `dac588dac35580dcfb761a115b76d80ffcc2c447`，exit 0。
- `git status --porcelain=v1 -b` → `## totk/scaffold...origin/totk/scaffold`，
  两个 ` M` 文件；`git diff --check` exit 0。
- `python tools/agent_handoff_check.py --resume` → exit 0；
  修正前 `--verify` → exit 1（HANDOFF CLEAN vs Git DIRTY）。
- 真机：`NOT RUN`（设备未连接）；业务构建/CI：在 NA-046 完成时运行。

### 下一步

唯一 READY 动作：**NA-046**（详见 HANDOFF「下一步唯一动作」）。

## 2026-10-21 11:45 Asia/Shanghai — [SESSION] 续七：子段桶的条目是 16 字节；区域里的载荷不像文件内容

- 会话目标：把「区域 → 文件」再推一步。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空。

### 做了什么与结果

1. **子段桶的条目是 16 字节**（不是 20）：`{u64 虚拟偏移, u32 填充, u32 ctr}` ——
   **没有大小字段**，大小是拿「下一条减这一条」算出来的（`nsz` 的 `getAllEntries` 就是这么算的）。
   桶 0 的结束偏移 = 载荷长度（478,426,112 ✓）。
2. **区域里的载荷字节不像「文件内容」**：第 0 区（虚拟 [0, 26,752) ← 载荷 [85,015,632, …)）
   在载荷里是 **32 字节随机数据 + 全零**；载荷 0 处同样是高熵数据。
   → 说明「虚拟偏移」的坐标系还没定准（虚拟 0 可能是虚拟映像的**哈希区**而不是数据区），
   载荷里每一段也未必是「改好的文件」。
   → 这一步**没有再往前推**；把已知的与未知的都写清楚了（见进度文档 §10）。

### 证据（命令与退出码）

- 子段桶与区域内容探针（仓库外 `probe_bktr_sub.py` / `probe_bktr_region0.py`）→
  逐 16 KB 页打印页头（页 0：条目 1 / 页 1：条目 646 / 页 2 起是哈希区），
  并打印第 0 区在载荷里的前 0x60 字节（32 字节随机 + 全零）。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 还差什么

- **真机的一切**：NOT RUN。
- **BKTR 的最后一步**：① 区域 → 文件（需要虚拟映像自己的文件表；且要先定准虚拟偏移的坐标系）；
  ② 载荷的分帧方式；③ 子段桶（646 条）的语义。
  三个都写进了 `docs/TOTK_PORT_PROGRESS.zh-CN.md` §10，下一轮可直接接着做。
- 运行期仍未验的三件事不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对是一条命令
（`python dm/android/tools/totk_device_check.py`，退出码 0 才继续）。

## 2026-10-21 11:20 Asia/Shanghai — [SESSION] 续六：BKTR 的结构解开了（区域级的虚拟↔物理映射）

- 会话目标：把更新包补丁的最后一块拼上。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空。

### 结果：结构解开了，剩下的只是「区域 → 文件」

关键突破来自**本机 venv 里已经装着的 `nsz` 5.0.0**（`nsz/Fs/Bktr.py`）——
只读它的**结构事实**（布局与字段），代码仍是自己写（本仓库 MIT，不搬它的代码）。

- NCA 头的 fs_header 里有两个 BKTR 头（各 32 字节）：
  `u64 偏移, u64 长度, 'BKTR', u32 版本, u32 条目数, u32 保留`
  - 头 A：偏移 `0x1C843400`、长度 `0x14000`、条目数 **2,658**（重定位桶）
  - 头 B：偏移 `0x1C857400`、长度 `0x8000`、条目数 646（子段桶）
- **重定位区**：开头 `{u32 填充, u32 桶数=4, u64 补丁映像总长=17,086,048,256}`，
  接着 2,034 个 `u64` 桶边界，然后**每个桶正好一个 16 KB 页**，
  页头 `{u32 填充, u32 条目数, u64 结束偏移}`，其后是
  **`{u64 虚拟偏移, u64 物理偏移, u32 isPatch}`（20 字节）**。
  实测四个桶：818 / 818 / 818 / 204 条（合计 2,658 ✓），
  结束偏移 0x6C8BD840 / 0xFD701C70 / 0x278F0DCF0 / 0x3FA686800（最后一个 = 补丁映像总长 ✓）。
- **语义**：虚拟偏移 = 这一段在「补丁后映像」里的位置；物理偏移 = 它的内容在段载荷
  （`0x1C843400` 之前那 478,426,112 字节）里的位置。虚拟偏移从 0 单调到 17,062,338,768。
  映射是**区域级**的：第 0 条 = 「虚拟 [0, 26,752) ← 载荷 [85,015,632, …)」。
- 虚拟偏移**不是**本体文件的数据起点（只撞上 6/2,658）：更新后的文件大小变了，
  虚拟映像的数据区布局与本体错位（本体数据区起点 0x1FE8000，更新 0x1FE0000，哈希树小了 32,768 字节）。
- **子段桶**：条目 `{u64 虚拟偏移, u32 大小, u32 填充, u32 ctr}`，桶 0 的结束偏移 = 载荷长度 ✓。

### 证据（命令与退出码）

- `python dm/tools/totk_bktr.py <更新包 .nca> --keys <prod.keys>` → **exit 0**，
  现在会打出「BKTR 桶：共 4 个，每个占 16 KB；补丁映像总长 17086048256」与每个桶的条目数、
  虚拟区间、物理区间、结束偏移。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 还差什么

- **真机的一切**：NOT RUN。
- **BKTR 的最后一步**：把「区域」还原成「文件」→ 需要**虚拟映像自己的文件表**
  （目录树 + 元数据表 + 哈希树）；本体那张表布局已错位，用不了。
  载荷里 `0` 开头那 85,015,632 字节很可能就是它（或一部分），还没确认。
  另两项：载荷的分帧方式、子段桶（646 条）的语义。
- 运行期仍未验的三件事不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对是一条命令
（`python dm/android/tools/totk_device_check.py`，退出码 0 才继续）。

## 2026-10-21 10:40 Asia/Shanghai — [SESSION] 续五：查清本体 RomFS 的「file_hash_table」是什么 → 内容哈希这条路排除

- 会话目标：把「按内容哈希映射」这个最后的想法试掉。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空。

### 结果：这条路**排除**了，而且顺带查清了一个格式事实

- 本体 RomFS 的 `file_hash_table`（偏移 0x3F7FE8138，1,216,828 字节）的真实结构是
  **28 字节头 + 304,200 个 4 字节项**：每项要么是 `0xFFFFFFFF`（空桶），
  要么是一个**文件元数据表偏移**。
  拿这些偏移去读元数据表，条目的父目录/兄弟/数据偏移/大小/名字**全部对得上**
  （`DmT_GO_MeetAgain_Text_008_b.bwav`、`Mrg_H-5_MrgD100_B8-BE-AY-FEB1B5F5.bcett`…），
  条目数 304,200 与本体的 304,207 个文件一致。
- ⇒ **这张表里根本不存哈希**（哈希只体现在桶的顺序上）。
  → **「用内容哈希把补丁块映射到本体文件」这条路不成立**：本体里没有内容哈希可用。
  这也解释了先前为什么 sha256 / sha1 / md5 / blake2b / blake2s（含各种零填充口径）
  在表里一个都找不到。
- 另外查过路径哈希：java*31 / djb2 / sdbm / fnv1 / fnv1a / crc32 等 14 个底数 × 正反序 ×
  带不带结尾 NUL × 全路径或只文件名 ≈ 100 多种口径，**与表里的值都对不上** ——
  因为表里没有哈希值可比。
- 补丁那 114,688 字节区域里**没有任何文件名字**（≥8 字符的可打印串 0 处），
  它的 4 字节字也不是本体的元数据表偏移 → 既不是名字表，也不是「指向本体文件」的表。
  → **下一步要换思路**：要么它与桶顺序哈希有关（得先复原排序函数），
  要么映射根本不在表里。

### 证据（命令与退出码）

- 本体哈希表结构探针（仓库外 `probe_hash_table.py` / `probe_path_hash.py` / `probe_path_hash2.py`）→
  打印 400 个非空桶的（hash, 全路径）与按 meta 偏移读出的条目（名字/大小都对），
  再用 ≈100 种路径哈希口径逐个比对 → **无一命中**。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 还差什么

- **真机的一切**：NOT RUN。
- **BKTR 的最后一步**（载荷块 ↔ 本体文件）：见上面「下一步要换思路」；
  已经排除的：160 种定长解释、载荷偏移、本体文件偏移、长度求和、内容哈希、路径哈希。
- 运行期仍未验的三件事不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对是一条命令
（`python dm/android/tools/totk_device_check.py`，退出码 0 才继续）。

## 2026-10-21 10:10 Asia/Shanghai — [SESSION] 续四：哈希口径也没走通；模块与数据不是同一次构建（已记进怀疑清单）

- 会话目标：把 BKTR 映射的最后一个想法（「按内容哈希映射」）试掉，并核实「本体数据 + 更新模块」这个组合的版本关系。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空。

### 做了什么

1. **「按内容哈希映射」试掉了，没走通**：本体 RomFS 的 `file_hash_table`（38,025 条 × 32 字节，
   偏移 0x3F7FE8138）里，用 `Mals/USen.Product.100.sarc.zs` 的内容算出的
   sha256 / sha1 / md5 / blake2b / blake2s，以及把内容零填充到 0x200 / 0x400 / 0x1000 / 0x2000 / 0x4000 / 0x10000
   之后的哈希，**一个都找不到**；连「连同映像里后面真实存在的字节凑到块边界」也不命中。
   而且那张表的前 64 字节根本不像 32 字节哈希（是 `ff ff ff ff` + 若干 4 字节小值），
   → **任天堂的哈希口径还没复原**，这条路暂时走不通。
2. **核实了「本体数据 + 更新模块」的版本关系**（实测）：
   - 本体 main 的 NSO 头构建号 `cef09201…`（36,549,681 字节）；
   - 更新 main 的 NSO 头构建号 `076db101…`（35,621,994 字节）→ **两者是不同构建**；
   - 数据包里发的 `game/libdmguest_main.so` 里带构建号 `5cb42b1c…`（= 文档里记的 TotK 构建号）。
   → 第一次开机跑的是「**v1.4.2 的代码 + 本体的数据**」，而更新补丁要替换 **2,658 个文件**。
   这条已经写进怀疑清单第 7 条：游戏若按数据版本做检查就会拒；不检查的话，进游戏看到的是本体那版内容。

### 证据（命令与退出码）

- 哈希口径探针（仓库外 `D:\Switch\totk-work\probe_bktr57..59.py`）→ 逐个口径打印命中位置，**全部为 0x-1**。
- 构建号核对（仓库外 `build_ids.py` / `check_module_build.py`）→ 本体 `cef09201…`、更新 `076db101…`、
  包里的模块 `5cb42b1c…`（在 `libdmguest_main.so` 的 +0x355a048）。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 还差什么

- **真机的一切**：NOT RUN（推包 / 导入 / 开机 / 出图 / 性能）。
- **BKTR 的最后一步**：载荷块 ↔ 本体文件的映射。下一步已收窄成两件事：
  ① 复原本体 RomFS 的文件哈希口径（`file_hash_table` 的内容形式还没搞清）；
  ② 或者找到那张 114,688 字节区域（= 3,584 × 32 = 元数据块 `level[1].hash_data_size`）的真实结构。
- 运行期仍未验的三件事（合并句柄拆分 / 变体挑选的机器码位置 / 预排布贴图内容）不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对是一条命令
（`python dm/android/tools/totk_device_check.py`，退出码 0 才继续）。

## 2026-10-21 09:40 Asia/Shanghai — [SESSION] 续三：重定位表查到「一半」就停，结论写清楚

- 会话目标：把更新包补丁的最后一步（载荷块 ↔ 本体文件的映射）再推一次，推不动就把结论写清楚，
  别让下一轮重走同一条路。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空。

### 这一段做了什么

专门攻那 81,920 字节的重定位表。**结论：推到「一半」，没能全解出来**，但把已知的与已排除的都写进了
`docs/TOTK_PORT_PROGRESS.zh-CN.md`，下一轮可以直接从那里接着来。

- **已知**：区域是 `[0x1C843400, 0x1C85F400)` = 114,688 字节（7 页 × 16 KB；头里的「块总长」只覆盖前 5 页）；
  前 5 页的计数 `[4, 818, 818, 818, 204]` → **2,658 条**，与 fs_header 的 `0xA62` 一致；
  页里有**两条交错的单调 u64 序列**（步长 40 字节，跨页连续，最大到 ~17 GB）；
  ⚠️ **纠正**：先前写的「约 55% 的 u64 值正好是本体某个文件的数据起点」是**错的** ——
  那是把**值为 0** 的项也算进去了（本体第一个文件的数据起点就是 0）。
  去掉 0 之后，整个 81,920 字节里**只有 15 处**能命中本体文件的数据起点（间隔还不规则：
  300 / 720 / 820 / 880 / 2312 / 4232 / 4608 字节），基本可当巧合 → **这张表里没有本体文件的偏移**。
  换个更像的解释：114,688 字节 = **3,584 × 32**，而 3,584 × 32 正好等于元数据块里
  `level[1].hash_data_size`（0x1C000）→ 它很可能是**第 1 层的 IVFC 哈希树**，
  那么「哪个载荷块替换哪个本体文件」也许靠的是**内容哈希**而不是这张表（这条还没验证：
  要先把载荷按 16 KB 块切开才能算哈希）。
- **已排除的解释**（下一轮别再试）：
  ① 起点 0–63 × 步长 8/12/16/20/24/28/32/36/40 共 **160 种**组合，
     没有一种能让「长度之和 = 载荷长度 478,426,112」成立；
  ② 记录里的 u64 是载荷偏移 —— 载荷里 14 个消息归档的偏移（0x147d5cd0 等）在表里**找不到**；
  ③ 记录里的 u64 是本体文件偏移 —— 本体 `Mals/*` 的 14 个文件偏移（两种口径）在表里都**找不到**；
  ④ u32 字段是新的长度 —— 这些值加起来只有几千，离 478 MB 差两个数量级；
  ⑤ 「按内容哈希映射」也没走通：本体 RomFS 的 `file_hash_table`（38,025 条 × 32 字节）里，
     该文件内容的 sha256 / sha1 / md5 / blake2b / blake2s 以及各种零填充后的哈希**一个都不命中**
     → 任天堂的哈希口径还没复原，要走这条路得先解决它。
- 另外查清了一条**会被误当成故障**的红字（`【红】数据包没有 derived.tsv` 对 TotK 是正常的），
  以及**游戏的消息文本在 `romfs/Mals/`（14 个语言，已实测在包里）**，两条都写进了预演清单。

### 证据（命令与退出码）

- 重定位表的分析脚本（仓库外 `D:\Switch\totk-work\probe_bktr4*.py`）→ 逐条打印页面计数、
  单调性、命中本体文件起点的比例；结论如上。
- `python dm/android/tools/build.py --game-run --version trim-b44` → **exit 0**，
  APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 还差什么

- **真机的一切**：NOT RUN。
- **BKTR 的最后一步**：记录布局（已缩小到「2,658 条、每条 20 字节左右、含一个与本体文件起点相关的 u64」，
  但字段含义没定），以及载荷块与记录的对应关系。
- 运行期仍未验的三件事不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对是一条命令
（`python dm/android/tools/totk_device_check.py`，退出码 0 才继续）。

## 2026-10-21 09:10 Asia/Shanghai — [SESSION] 续二：开机前的核对收成一条命令，消息归档与本体对上了

- 会话目标：接着上一条日志，把「第一次开机」这件事再往前推一步 —— 手机一回来就能一条命令查完，
  不靠人记那串 adb 命令。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、工作区干净；`adb devices` 仍为空、PnP 仍查不到设备。

### 做了什么

1. **新增 `dm/android/tools/totk_device_check.py`**（`30bd9e9`）：开机前的一次性核对。
   查：设备在不在 → `files/temp/launch-settings.conf` 的 `game_profile` 是不是 totk →
   `files/temp/gpu-driver.conf` 的 `subgroup_size` 是不是 64 → 内部 `d2r-package/game/` 里
   3 个 `.so` 与 6 份布局表 → 外部 `d2r-package/` 的 `manifest.json`/`romfs`/`shaders` →
   清单的 `format` 与 `counts`（romfs 304,207 / shaders 24,535）→ `/data` 可用空间够不够 33 GiB →
   并把 `files/game.log` 拉下来（`--pull-log`）。
   **退出码 0 = 可以开机 / 1 = 有红项 / 2 = 手机没接上**；只读（只读文件与 `df`）。
2. **消息归档在本体里找到对应物了**：把本体 RomFS 里 `Pack/` 之外的 203,031 个 `.zs`
   按 SARC 解开，找出条目带 `Msg/` 的 —— **正好 14 个**：`romfs/Mals/<语言>.Product.100.sarc.zs`
   （每个 1,510 条）。载荷里对应的 14 个 zstd 帧每个 **1,511 条**（多一条），
   压缩大小与本体逐个对得上 → **「载荷 = 更新过的文件内容」这个模型成立**。
   顺带一个对移植有用的结论：**游戏的消息文本在 `romfs/Mals/`，不在 `Pack/` 里**（找文本时容易漏）。

3. **查清了一条会被误当成故障的红字**：`【红】数据包没有 derived.tsv：…`
   —— 对 TotK 是**正常**的：那三张派生表（经验表 / 技能图标索引 / 关联亮度）是 **D2R 专属**的游戏系统，
   TotK 的包里本来就没有这个文件（`dm/android/tools/build_package.py` 的 `assemble()` 只在 `derived`
   不为 None 时才写它），宿主只在**调试浮层**里用它们（`dm/host/dm_hud_exp.h`），游戏本体不读。
   → 看到这行**忽略**，不要重新出包。已写进进度文档的「0.5 不是故障的红字」一节。
4. **游戏的消息文本确实在包里**：实测数据包里有 `romfs/Mals/<语言>.Product.100.sarc.zs` 14 个
   （CNzh/EUde/EUen/EUes/EUfr/EUit/EUnl/EUru/JPja/KRko/TWzh/USen/USes/USfr，1,477,675–1,888,200 字节），
   宿主把 `DM_ROMFS` 指到 `<外部存储>/d2r-package/romfs`，所以游戏按相对路径能开到。
   ⚠️ 找文本时别只看 `Pack/`（那里没有消息归档）。

### 证据（命令与退出码）

- `python dm/android/tools/totk_device_check.py` → **exit 2**（手机没接上，按设计如此），
  打印「adb devices 为空 —— 手机还没接上」；其余各项要设备在场才能查。
- `python dm/tools/totk_bktr.py <更新包 .nca> --keys <prod.keys> --romfs <本体 RomFS> --compare-base <数据包 zip>`
  → **exit 0**，打印 14 行「载荷里的消息归档 ↔ 本体 `romfs/Mals/`」的逐个对照（条目 1,511 vs 1,510，压缩大小对得上）。
- `python dm/android/tools/build.py --game-run --version trim-b43` → **exit 0**，
  APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python dm/android/tools/ci_checks.py` → 14 项通过 / 0 失败；`tools/agent_handoff_check.py --verify` exit 0。

### 本条日志所在这一轮的提交

| 提交 | 内容 |
| --- | --- |
| `30bd9e9` | `dm/android/tools/totk_device_check.py`：开机前的一次性核对（代码侧） |

（交接控制面另有一个提交。）

### 还差什么

- **真机的一切**：NOT RUN（推包 / 导入 / 开机 / 出图 / 性能）。
- **BKTR 仍差最后一步**：那 2,658 条记录每条指向本体哪个文件（试过多种定长记录的解释，
  没有一种能让「长度之和 = 载荷长度 478,426,112」成立），以及载荷的分块边界。
- 运行期仍未验的三件事（合并句柄拆分 / 变体挑选的机器码位置 / 预排布贴图内容）不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；开机前的核对已经收成一条命令
（`python dm/android/tools/totk_device_check.py`），命令序列与判据在
`docs/HANDOFF.zh-CN.md` 的「下一步唯一动作」里。

## 2026-10-21 07:35 Asia/Shanghai — [SESSION] 续：着色器回退路径查过了，BKTR 载荷解开了

- 会话目标：接着上一条日志，把「首次开机可能硬失败」的地方再查一遍，并把 BKTR 再往里推一层。
- 接手核对：`agent_handoff_check.py --resume` exit 0、`--verify` exit 0；分支 `totk/scaffold`、
  HEAD 与 `origin/totk/scaffold` 一致、代码工作区干净；`adb devices` 仍为空（手机还是没接）。

### 做了什么

1. **着色器的回退路径查过了**（`1b84d4e`）—— 这是真机上最可能的硬失败之一：
   `FATAL Missing Vulkan shader <目录>/<键>.spv`。
   宿主挑变体挑不中时会**按控制键**去取（`dm/android/native/nvn_vulkan_shader.inc` 的 `shader_get`
   最后一跳 `shader_load_by_key(key,1,1)`），所以**每份变体名单自身的 .meta/.spv 也必须在包里**。
   原先的包闸门只查「名单里列出的键有没有文件」，没查这一条，也没查「每个 .meta 都有 .spv」。
   现在两条都查了（`dm/gfx/tools/totk_shader_package.py --verify-shaders`）。
   实测本包：11,447 个 .meta、11,447 个 .spv、1,640 份名单（列了 5,913 个完整键）→ **一个都不缺**。
2. **BKTR 载荷解开了**（`5bfa14b`）—— 上一条日志里「载荷格式未知」这一项现在有答案了：
   载荷里是 **zstd 帧，用的是游戏自己的字典**（`/Pack/ZsDic.pack.zs` 里的 `zs.zsdic`，id=1），
   解出来是 **SARC 归档**：例如 `0x147d5cd0` 那个帧解出 12,373,528 字节、1,511 个条目，
   条目名就是游戏的消息归档（`LayoutMsg/TreasureFullShortCut_00.msbt`、
   `EventFlowMsg/Npc_TripMaster_13.msbt`…）。
   本体的 `/Pack/*.pack.zs` 是同一套结构但用**字典 id=3**（`pack.zsdic`）——
   例如 `AI.Global.Product.100.pack.zs` 2,061 条、`AIScheduleParam.pack.zs` 1,917 条，
   `/Pack/Actor/` 下还有 15,049 个按角色分的 pack。
   → **补丁载荷 = 一批更新过的 pack 归档**。`dm/tools/totk_bktr.py --romfs <本体 RomFS>` 现在会把
   这些帧连同字典 id 与解出来的条目一起报出来。
   重定位表也解开了一半：81,920 字节 = **5 页 × 16 KB**，每页头里的计数是 `[4, 818, 818, 818, 204]`，
   首页那 4 条是页头 → 真正条目 **2,658** 个，与 fs_header 里的块总长 `0xA62` = 2,658 交叉印证
   ⇒ **这条补丁要替换 2,658 个文件**（平均 ~180 KB）。
   记录本身是 20 字节的定长结构，但试过多种起点与字段解释，
   **没有一种能让「长度之和 = 载荷长度 478,426,112」成立** → 每条到底指向哪个文件还没解出来。

### 再往前一步：载荷里的消息归档在本体里找到了对应物

把本体 RomFS 里全部 203,031 个 `.zs`（`Pack/` 之外的）按 SARC 解开，找出条目里带 `Msg/` 的，
**正好 14 个**：`romfs/Mals/<语言>.Product.100.sarc.zs`，每个 **1,510 条**。
载荷里对应的 14 个 zstd 帧每个 **1,511 条**（多一条 = 更新加了一个消息），
压缩大小与本体逐个对得上（本体 1,477,675 … 1,888,200；载荷 1,478,628 … 1,891,213）。
→ **「载荷 = 更新过的文件内容」这个模型成立**；顺带记住：游戏的消息数据在 `romfs/Mals/`，
不在 `Pack/` 里（找文本时容易漏）。

### 证据（命令与退出码）

- `python dm/tools/totk_bktr.py <更新包 .nca> --keys <prod.keys> --romfs D:\Switch\totk-work\romfs-test`
  → **exit 0**，「布局自洽：True」，并列出载荷里的 16 个 zstd 帧（前两个是误命中，解不开；
  其余解出 SARC 归档并给出条目数与前几条条目名）。
- `python dm/gfx/tools/totk_shader_package.py --verify-shaders D:\Switch\totk-work\package-totk\shaders`
  → **exit 0**，末行多了一句「回退路径的文件也在 ✓」（约 6 分钟，磁盘读 11,447 个 meta + 1,640 份名单）。
- `python dm/gfx/tools/test_totk_shader_package.py` → exit 0。
- `python dm/android/tools/build.py --game-run --version trim-b40` → **exit 0**，
  APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python dm/android/tools/ci_checks.py` → 13 项通过 / 1 项失败（失败项仍是交接控制面本身，
  因为文档还没改完；改完复跑即绿）。

### 本会话（本条日志所在的一轮）的提交

| 提交 | 内容 |
| --- | --- |
| `abca535` | `dm/tools/totk_bktr.py`：读出并核对更新包 BKTR 段的物理布局 |
| `1b84d4e` | `dm/gfx/tools/totk_shader_package.py`：包闸门加「回退路径的文件也在」检查 |
| `5bfa14b` | `dm/tools/totk_bktr.py`：加上载荷扫描（zstd 帧 + 解出来的 SARC 内容） |

（交接控制面另有一个提交。）

### 还差什么

- **真机的一切**：NOT RUN（推包 / 导入 / 开机 / 出图 / 性能）。
- **BKTR 还差两块**：① 每个载荷块对应本体哪个文件（映射在 `0x1C843400`–`0x1C857400` 那 81,920 字节里，
  每 16 KB 一页、页内是稀疏的定长记录，语义没解出来）；② 载荷的分帧方式（16 个 zstd 帧只占载荷的一部分，
  开头约 343 MB 里没有 zstd 帧头）。
- 运行期仍未验的三件事（合并句柄拆分 / 变体挑选的机器码位置 / 预排布贴图内容）不变。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**。
手机不在时可以接着做的离线活：① 解开上面那 81,920 字节的重定位表（把载荷块映射到本体文件）；
② 把 `dm/tools/totk_bktr.py` 接进 `dm/android/tools/totk_preflight.py` 当闸门；
③ 核对载荷里那 1,511 条的消息归档与本体里对应的归档差在哪（能顺带验证「补丁 = 更新过的 pack」这个结论）。

## 2026-10-21 06:45 Asia/Shanghai — [SESSION] 手机不在的一轮：首次开机预演清单 + 导入流程核对 + BKTR 布局定位

- 会话目标：按用户要求，这轮只做「不需要真机」的活，重点是**降低首次开机的失败概率**。
- 接手核对（按 `AGENTS.md` 的新会话恢复顺序做的，不是凭聊天推断）：
  读 `AGENTS.md` → 读 `docs/HANDOFF.zh-CN.md` 的 frontmatter / 当前快照 / 下一步唯一动作 →
  读 `docs/HANDOFF_LOG.zh-CN.md` 顶部条目 → `tools/agent_handoff_check.py --resume` exit 0 →
  `--verify` exit 0 → Git 核对：分支 `totk/scaffold`，HEAD `63ec043` = `origin/totk/scaffold`，
  代码工作区干净；`adb devices` 为空、PnP 查不到设备（**手机确实没接上**）。
  → 交接与 Git 一致，无冲突，直接开工。

### 这一轮做了什么

1. **首次开机预演清单**（写进 `docs/TOTK_PORT_PROGRESS.zh-CN.md` 的「首次开机预演清单」一节，254 行）：
   模块装载→nnMain 之前 / NVN 接管 / 描述符集 / 合并句柄拆分 / 变体挑选 / 预排布贴图，
   每段给出「真机上会看到什么日志行」「哪些行是硬失败」「画面该是什么样」；
   另附 **8 条怀疑清单**（位置 + 为什么可疑 + 真机上怎么确认），按规矩没有靠猜改代码。
   所有日志字符串都对着当前源码核过行号（`dm/host/main.c`、`dm/host/loader.c`、`dm/host/diag.c`、
   `dm/gfx/nvn/hle_nvn.c`、`dm/android/native/nvn_vulkan_*.inc`、`dm/android/native/gpu_driver.c`、
   `dm/android/java/org/d2r/android/port/*.java`）。
2. **纠正了两个会导致真机白跑的认知**：
   - **日志不在 logcat**：客体的日志行走 stderr，Android 前端把 stderr 重定向到**内部存储的
     `files/game.log`**（`dm/android/native/frontend_activity.c:205`）；logcat 只有 tag `D2RAndroid`
     与 tombstone。取法：`adb shell run-as org.d2r.android.port cat files/game.log`。
     game.log 每次开机 O_TRUNC 截断 → **重启就丢**。
   - **`deploy_totk.py` 写的 `game_profile=totk` 会被启动界面覆盖**（`LauncherActivity.java:639`
     在点「开始」时用界面里选中的那一行重写配置）→ 必须在界面里切到「王国之泪」，
     否则宿主按 D2R 的分离句柄表读 c[2]，画面必然不对。这是清单里的一号陷阱。
3. **手机端导入流程的离线核对**（结论见进度文档 §9）：
   包里 **328,752 个条目全是 stored（不压缩）** → 「zip 17 GiB + 解开 ~34 GiB」偏大，
   真实占用 ≈ **33.1 GiB**（外部存储）→ /data 至少留 35 GiB、建议 40 GiB；
   `PackageArchive` 的四个上限全部够用（entries 328,752/600,000；total 16.55/24 GiB；
   单条最大 196 MB/12 GiB；manifest 314 B/1 MiB），清单自报数与实测逐项一致。
   两个风险：包里**没有目录条目**（30 万次 mkdirs，导入十几分钟到一小时）；
   SAF 选 `/sdcard/Android/data/...` 未必读得到 → 备选 `/sdcard/Download/`。
4. **更新包的 BKTR 补丁：布局定死了**（新增 `dm/tools/totk_bktr.py`，本仓库 MIT、自己写）：
   - 段数据其实是**普通 AES-CTR**（content key + 段 CTR），不是别的加密
     （证据：这样解出来的 232 字节元数据块是**合法**的 IVFC 头，随机密钥凑不出来）；
   - 两个 BKTR 头在 **NCA 头的 fs_header+0x100**，不在段数据里（整段 456 MiB 扫过，`BKTR` 魔数 0 处）；
   - 元数据块在 fs_header+0x1A0/0x1A8（232 字节），**它的 sha256 与 fs_header+0x1B0 存的哈希逐字节相等**；
   - 段内物理分区（补丁数据 / 重定位校验表 / 两层 hash / 元数据块）全部定位。
   **仍未解决**：那 478 MB 的**载荷本身**是什么格式（已排除 zstd / xz / gzip / brotli 帧头）。
5. **Mac 侧翻译链**：命令清单与前置写进进度文档 §11；本轮**没有**改 `dmsh_chain.h`
   （它在 Mac 上 `--update-lock` 时会再变一次，徒增差异）。

### 证据（命令与退出码）

- `python dm/tools/totk_bktr.py D:\Switch\totk-work\cache\nca\d214ebdad75878d540c13f3155640f39.nca --keys D:\Switch\totk-work\keys\prod.keys`
  → **exit 0**，末行「布局自洽：True」，元数据块 sha256 与头里的哈希一致。
- `python -c "import zipfile …"` 逐条读包 → 328,752 个条目、**全部 compress_type=0**、解压后总长不变。
- `python dm/android/tools/ci_checks.py` → **13 项通过 / 1 项失败**；失败项是「Agent 交接控制面」，
  原因是本轮先改了文档还没改 HANDOFF；改完复跑即绿（见下方 [END]）。
- `python dm/android/tools/build.py --game-run --version trim-b39` → **exit 0**，
  APK `dm/android/build/D2R-Android-port.apk`（17,873,359 字节）。
- `python tools/agent_handoff_check.py --verify` → **exit 0**（HANDOFF 改完后复跑）。

### 本会话的提交

| 提交 | 内容 |
| --- | --- |
| `abca535` | `dm/tools/totk_bktr.py`：读出并核对更新包 BKTR 段的物理布局（代码侧） |

（交接控制面另有一个提交，只动 `docs/HANDOFF.zh-CN.md`、`docs/HANDOFF_LOG.zh-CN.md`、
`docs/TOTK_PORT_PROGRESS.zh-CN.md`。）

### 还差什么

- **真机的一切**：推包、导入、切档位、开机、看日志、图、性能 —— **本轮全部 NOT RUN**。
- **运行期仍未验的三件事**（与上一轮相同）：① 变体挑选在真机上命中哪个候选；
  ② 预排布贴图内容是否正确；③ 合并句柄拆分是否与画面一致。
  本轮把「怎么验」都写成了可执行的检查步骤（见进度文档 §2 与 §8 的怀疑清单）。
- **BKTR 载荷格式**（唯一的数据层缺口）：本体数据完整可用，先按「本体数据 + v1.4.2 的模块」开机。
- **Mac 侧翻译链**（需要 Mac）。

### 下一步

唯一 READY 动作仍是 **NA-044 = 手机接上后推包开机**；命令序列与「第一分钟该做什么」已写进
`docs/HANDOFF.zh-CN.md` 的「下一步唯一动作」（含开机前 5 条静态核对命令）。
手机不在时可以接着做的离线活：① 继续啃 BKTR 载荷格式（下一步候选：把 81,920 字节的重定位表
当表结构解出来）；② 把 `dm/tools/totk_bktr.py` 接进 `totk_preflight.py` 的闸门。

## 2026-10-21 04:30 Asia/Shanghai — [SESSION] 交接：本会话停在「可以推机」，手机一回来就开机

- 会话目标：按用户要求停下手上的活，把交接文档更新到可以直接开新对话接着做。
- 结果：设备前的静态闸门**全绿**（预检脚本完整档 exit 0，结论「全绿 → 可以推机」）；
  剩下的验证全部要真机；交接文档已按协议更新（快照 / 下一步唯一动作 / 本条日志）。

### 本会话的提交（按顺序，全部已推送到 `origin/totk/scaffold`）

| 提交 | 内容 |
| --- | --- |
| `5b44b51` | TotK 的 NVN 接口面对齐：名字表补 13 个（此前取址会拿到空函数指针）、13 个新接口落地、`nvn_slots_auto.py` / `nvn_table.py` / `nvn_coverage.py`、合并贴图绑定 |
| `152493c` | 把 TotK 调用的 NVN 接口全部补齐（缺口 103 → 0）：缓冲族 / 绘制 / 句柄绑定 / 整数清除 / 各类查询 |
| `25b56f4` | NA-038 的交接快照 |
| `001d1c9` | 最后 5 个空实现补成真实现（`nvnCommandBufferWaitSync` 98 次调用、间接派发、深度夹取、着色器局部内存、窗口收尾） |
| `2db6a3a` | 运行期按「完整键」挑着色器变体（1,640 个歧义控制键 → 43.6% 会拿错 SPIR-V） |
| `6ba874f` | 变体键链的端到端核对工具（`totk_variant_keys.py`） |
| `206777b` | 预排布贴图数据接上 |
| `14510c3` | 变体挑选再多试一个机器码位置 |
| `2c6f80b` | 真机预检脚本（一条命令给出带证据的推机结论） |
| `9a26e94` | 变体命中 / 退回计数（真机日志能直接回答假设成不成立） |
| `1191b01` | 变体挑选候选顺序的依据注释（静态推断，未真机确认） |
| `df23175` | 完整预检全绿的记录 |

### 关键事实（下一个会话直接用）

- **分支 / HEAD**：`totk/scaffold`，`df23175`（= `origin/totk/scaffold`），工作区干净。
- **闸门**：`ci_checks.py` 14 项通过 / 0 失败；`agent_handoff_check.py --verify` exit 0；
  `dm/gfx/tools/nvn_coverage.py --check` exit 0（取址缺口 0 / 缺实现 0 / 空实现 0）；
  `dm/gfx/tools/totk_preflight.py`（完整档）exit 0 → **「全绿 → 可以推机」**。
- **数据包**：`D:\Switch\totk-work\package-totk\totk-package.zip`（16.62 GiB；旧的留成 `totk-package-old.zip`）。
- **下一步唯一动作**：NA-044 = 手机接上后按 NA-036 的步骤推包开机（命令序列见 HANDOFF 的「下一步唯一动作」）。
- **真机日志要盯的四类行**：启动序列走到哪一步；`【红】NVN 未实现被调用：名字`；
  `[vulkan-shader] 控制键 … 命中变体 …（机器码来自 0x…）` 与 `… 退回多数派变体（累计退回 N 次）`；
  `UNIMPL <名字>`。
- **尚未验证的三个假设**（只有真机能定）：变体挑选的机器码位置；预排布贴图内容；合并句柄拆分与画面是否一致。
- **仍未解决**：更新包的 BKTR 补丁（已排除三种可能）。网络实测：`git` 到 github.com 通，
  `api.github.com` / `raw.githubusercontent.com` 超时不通 → 取参考实现要走 `git clone`。
- **本会话 NOT RUN**：真机的一切（推包 / 导入 / 开机 / 出图 / 性能）。

## 2026-10-21 05:05 Asia/Shanghai — [VERIFY] 完整预检全绿：可以推机

- 会话目标：把预检里唯一的黄项（变体键链要重解析归档）补跑掉，拿到「全绿」的结论。
- 结果：**7 条闸门全绿 → 结论「全绿 → 可以推机」**；一加 12 仍然断开（`adb devices` 空）。

[BEGIN] na-044-full-preflight

- 命令：`python dm/android/tools/totk_preflight.py --package D:\Switch\totk-work\package-totk\totk-package.zip --shaders D:\Switch\totk-work\package-totk\shaders --code D:\Switch\totk-work\shaders-index5\code --bfsha D:\Switch\totk-work\shaders-out --index D:\Switch\totk-work\shaders-index5\shader_index.tsv`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：全部闸门绿，结论为「可以推机」。
- 日志路径：无
- 回滚点：`633e60a`

[END] na-044-full-preflight

- 退出码：预检脚本 exit 0，结论「全绿 → 可以推机」。
- 产物：无新产物（只跑检查）。
- 结果：SUCCESS
- 备注：**真机部署与开机 NOT RUN**（手机断开）。这是本会话能离线做到的最后一步。

证据（本条目对应的命令与退出码）：

- APK 绿（17,873,359 字节，03:53 构建）；数据包清单绿（game 9 / romfs 304,207 / shaders 24,535；
  game 81,598,218 字节 / romfs 17,043,238,905 字节 / shaders 646,871,659 字节）。
- 着色器包绿（11,447 个 meta；c[2] 偏移全落在 [0x20,0x120)；1,640 份变体名单里的文件齐全）。
- 变体键链绿（归档里核对 **47,260** 个着色器：宿主口径完整键不一致 0 个、c1 不一致 0 个、控制段长度不一致 0 个；
  5,913 个变体键缺文件 0 个、不在索引里 0 个）。
- NVN 接口覆盖绿（取址缺口 0 / 空实现 0 / 缺实现 0 —— TotK 调用的 213 个接口宿主全部有实现）。
- `ci_checks.py` 绿（14/0）；`agent_handoff_check.py --verify` 绿。
- 设备：`adb devices` 为空 —— **剩下的每一步都要在真机上做**（推包 → 导入 → 切档位 → 开机看日志）。

## 2026-10-21 04:45 Asia/Shanghai — [TOTK] NA-043：变体挑选的运行期假设写清 + 命中/退回计数

- 会话目标：把「运行期机器码地址在哪」这个唯一未知假设落到代码注释与文档里，并让真机日志能直接回答它。
- 结果：结论写进代码注释与进度文档；宿主开始统计变体命中与退回次数；构建通过。

[BEGIN] na-043-variant-layout

- 命令：`dm/android/tools/build.py --game-run --version trim-b38`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：假设有据可依；真机日志能回答「通不通 / 通的是哪一处」。
- 日志路径：无
- 回滚点：`be91e7d`

[END] na-043-variant-layout

- 退出码：`build.py --game-run --version trim-b38` exit 0；`ci_checks.py` 14 项通过 / 0 失败。
- 产物：提交 `9a26e94`（命中/退回计数）与本条的注释改动。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **静态推断的链条**：游戏的着色器表项是 `{u64 程序地址; u32 ?; u64 控制段地址; u32 阶段数}`（`upd_main.img` 的
  `0x2f5234` 读表项首字段、`0x2f523c` 读 `+0xc`）；调用 `nvnProgramSetShadersExt` 时传
  `{data = 表项首字段 + 固定偏移, control = 表项 +0xc}`（`0x2f5244` 的 `stp x9,x10,[sp,#0x10]`）。
  NVN 的 `data` 语义是「着色器数据（程序）」⇒ 程序地址 = `data - 固定偏移` 或 `data` 本身。
  宿主按 `data` → `data-程序偏移` → `data+程序偏移` → `控制段+0x880` → `控制段+0x880+程序偏移` 的顺序试
  （候选与依据写在 `nvn_vulkan_shader.inc` 的注释里）。
- **真机日志能回答**：宿主统计命中与退回次数，命中打 `[vulkan-shader] 控制键 … 命中变体 …（机器码来自 0x…）`，
  退回打 `[vulkan-shader] 控制键 … 的变体没挑中，退回多数派变体（累计退回 N 次）`。
- **诚实标注**：以上是静态推断，**未在真机上确认**；真机第一件事就是看这两行日志。

- 下一步：手机一回来立刻按 NA-036 推包开机（包：`D:\Switch\totk-work\package-totk\totk-package.zip`，16.62 GiB）。

## 2026-10-21 04:25 Asia/Shanghai — [TOTK] NA-042：真机预检脚本（一条命令给出「可以推机 / 还差什么」）

- 会话目标：把「设备之前能查的全套闸门」收成一条命令，给出带证据的结论。
- 结果：`dm/android/tools/totk_preflight.py` 跑完 7 条闸门 → **没有红项、1 项黄** → 结论「可以推机」。

[BEGIN] na-042-preflight

- 命令：`python dm/android/tools/totk_preflight.py --package <包> --shaders <着色器目录> [--quick]`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：一条命令给出带证据的推机结论。
- 日志路径：无
- 回滚点：`091bbb4`

[END] na-042-preflight

- 退出码：预检脚本 exit 0（结论：没有红项，有 1 项黄）。
- 产物：仓库内 `dm/android/tools/totk_preflight.py`（提交 `2c6f80b`）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- 闸门与结果：APK 绿（17,873,359 字节）；数据包清单绿（game 9 / romfs 304,207 / shaders 24,535；
  game 81,598,218 字节 / romfs 17,043,238,905 字节 / shaders 646,871,659 字节）；着色器包绿（11,447 个 meta，
  c[2] 偏移全落在 [0x20,0x120)，1,640 份变体名单里的文件齐全）；NVN 覆盖绿（取址缺口 0 / 缺实现 0 / 空实现 0）；
  `ci_checks.py` 绿（14/0）；`agent_handoff_check.py --verify` 绿。
- 黄项：变体键链那条在 `--quick` 下跳过（要重解析归档，约 5 分钟）→ 真机前补跑一次。
- 脚本只读不改；每条闸门打印命令、退出码与证据行，红项逐条列出影响，退出码 0 = 可推机、1 = 有红项。

- 下一步：**NA-043** —— 把「客体的着色器表怎么选变体」在静态层面钉死（找游戏里 BAHS 容器解析的那段代码，
  确认运行期「机器码地址」到底在哪），好让变体挑选这条路的假设有据可依；手机一回来立刻按 NA-036 推包开机。

## 2026-10-21 04:05 Asia/Shanghai — [TOTK] NA-041：包重建（16.62 GiB）；M4 的 TotK 专属部分核对结果是「本来就是通用的」

- 会话目标：把真机测试前的准备做完，并把 M4 里「哪些要为 TotK 改」查清楚。
- 结果：① 数据包重建完成（16.62 GiB，含变体着色器）；② **M4 的触控 / 存档 / 音频 / 手柄映射都是通用件**，不需要为 TotK 重写，
  只需真机校准；③ 着色器绑定容量静态核对通过。

[BEGIN] na-041-package-and-m4-review

- 命令：`dm/android/tools/totk_package.py`（重建包）、`dm/android/tools/build_package.py inspect`、`dm/android/tools/build.py --game-run --version trim-b37`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：包里有变体着色器；M4 的 D2R 专属部分到底有哪些。
- 日志路径：无
- 回滚点：`e0dea7f`

[END] na-041-package-and-m4-review

- 退出码：`totk_package.py` exit 0（16.62 GiB）；`build_package.py inspect` exit 0（game 9 / romfs 304,207 / shaders 24,535）；`build.py --game-run --version trim-b37` exit 0；`ci_checks.py` 14 项通过 / 0 失败。
- 产物：`D:\Switch\totk-work\package-totk\totk-package.zip`（16.62 GiB；旧的留成 `totk-package-old.zip`）；APK `dm/android/build/D2R-Android-port.apk`（trim-b37）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。

证据（本条目对应的命令与退出码）：

- **包的清单**：`build_package.py inspect` 读出 `shaders: 24535`（5,534 个控制段键的 .spv/.meta + 5,913 个变体完整键的 .spv/.meta + 1,640 份 `.variants`）、
  着色器部分 646,871,659 字节、romfs 304,207 个文件。
- **触控是通用虚拟手柄**：`dm/android/java/org/d2r/android/port/TouchControls.java` 的六个窗口是
  左摇杆 / 右四键（A B X Y，菱形排布）/ 左肩 L+ZL / 右肩 R+ZR / 方向键 / 功能键（Minus Plus LS RS），
  坐标是相对屏幕算的，**没有引用 D2R 的 HUD 资源** → TotK 直接可用。
- **存档不用改**：`dm/android/native/frontend_activity.c` 把 `DM_SAVE` 指向 `<内部存储>/save`，
  客体按自己的档名开文件（`dm/gfx/nvn/hle_fs.c` 把它拼到 `DM_SAVE` 下）→ 两个游戏的档自然不同名。
- **绑定容量**：扫 11,447 个 `.meta` 得每阶段最多 UBO 9 / SSBO 8 / 贴图 21 / 图像 0；
  宿主上限是 UBO/SSBO 每阶段 16、贴图 128、c[2] 合并表 32 槽 → 都在范围内 ✓。
- 下一步：**NA-042** —— 真机预检脚本（一键跑完设备前能查的全套闸门），以及手机一回来就按 NA-036 推包开机。

## 2026-10-21 03:40 Asia/Shanghai — [TOTK] NA-039 / NA-040：5 个空实现补成真实现；1,640 个歧义控制键查清并做成运行期可解；预排布贴图接上

- 会话目标：把「TotK 调用、宿主还是空实现 / 接红桩」的接口收干净；把 M3 最大的坑（歧义控制键）查清并给出解法。
- 结果：① 覆盖缺口 **103 → 0**（213 个接口全部有实现）；② 歧义控制键**量化清楚**（43.6% 的着色器会拿错变体），
  给出并实现了「变体完整键 + 运行期挑选」的机制，键代数已用归档 47,260 个着色器逐个核对；③ 预排布贴图数据接上了。

[BEGIN] na-039-040-nvn-and-variants

- 命令：`dm/gfx/tools/nvn_coverage.py --check`、`dm/gfx/tools/totk_variant_keys.py`、`dm/gfx/tools/totk_shader_package.py`、`dm/android/tools/build.py --game-run --version trim-b34..36`、`dm/android/tools/ci_checks.py`
- 工作目录：`D:\Switch\d2r-android`
- 预期结果：接口覆盖清零；变体键这条链自洽；构建与闸门全绿。
- 日志路径：无
- 回滚点：`e47d300`

[END] na-039-040-nvn-and-variants

- 退出码：`nvn_coverage.py --check` exit 0（缺实现 0、空实现 0）；`totk_variant_keys.py` exit 0（47,260 个着色器键一致）；
  `totk_shader_package.py --verify-shaders` exit 0（11,447 个 meta、1,640 份变体名单、名单里的文件齐全）；
  `build.py --game-run --version trim-b36` exit 0；`ci_checks.py` 14 项通过 / 0 失败。
- 产物：仓库内 `dm/gfx/tools/nvn_slots_auto.py`、`nvn_table.py`、`nvn_coverage.py`、`totk_variant_keys.py`，
  改动 `dm/gfx/nvn/hle_nvn.c`、`nvn_obj.h`、`nvn_names_totk.txt`、`nvn_calls_totk.tsv`、`names.txt`、`nvn_thunks.S`、
  `nvn_count.h`、`nvn_protos.h`、`dm/android/native/nvn_vulkan.c`、`nvn_vulkan_draw.inc`、`nvn_vulkan_tex.inc`、
  `nvn_vulkan_shader.inc`、`dm/android/tools/ci_checks.py`；仓库外 `D:\Switch\totk-work\package-totk\shaders\`
  （5,534 个控制键 + 5,913 个变体文件 + 1,640 份名单）、`D:\Switch\totk-work\package-totk\totk-package-v2.zip`（重建中）。
- 结果：SUCCESS
- 备注：**真机部署与开机本批 NOT RUN**（手机断开）。变体挑选命中哪个候选、预排布贴图是否正确，都只有静态依据。

证据（本条目对应的命令与退出码）：

- **接口覆盖**：`nvn_slots_auto.py` 在 `upd_main.img`（.text 尾 `0x2ba61f0`）自动定位到 NVN 取址函数 `0xbbfac0`，
  解析出 **534** 个取址名；与名字表比对，**13 个名字宿主的表里没有** → `nvn_lookup` 返回 NULL → 客体拿到空函数指针（会崩）。
  补齐后名字表 536（D2R 的 523 个顺序不动 → 槽索引不变 → D2R 行为逐字节不变）。
- **调用面**：静态扫描 TotK main 的 `.text`（`adrp 槽页; ldr [xN,#off]; ldr [xN]; blr xN`）→ **213** 个接口被调用、
  2,946 个调用点。按调用点数从高到低逐个实现（缓冲族、绘制、句柄绑定、整数清除、各类查询与状态），
  缺口 103 → 0；其中「按值返回不透明结构体」的接口（`NVNmemoryPool` / `NVNmemoryPoolFlags`）改用 64 位返回：
  头文件把它们建模成 96/256 字节结构体（按值返回走间接返回约定），而游戏那边拿到的是寄存器里的普通值。
- **歧义控制键**：1,640 个控制键覆盖 5,913 次出现；多数派规则下 **4,273 次（43.6%）用错变体**。
  键代数已证明：流水线键 `sha256(控制段+机器码+c1)` 与宿主运行期 `sha256(控制段前0x880+机器码+c1)` 哈希的字节相同
  （控制段恰好 0x880 字节、机器码与 c1 在代码区首尾相接），归档里 47,260 个着色器逐个重算一致。
  包里同时存两套键 + `<控制键>.variants` 名单；宿主运行期在四个候选位置找机器码，算完整键去名单里挑。
- **预排布贴图**：游戏用 `nvnTextureBuilderSetPackagedTextureData` 给的是**指针**（不是池里偏移），
  宿主之前忽略它 → 那批贴图会没有内容；现在 builder 记住指针、初始化时用它当来源，走已有的解排布上传路径。
- **下一步**：**NA-041** —— TotK 专属的 M4 部分（触控布局 / 存档目录 / 音频），以及把 16.6 GiB 的包在手机上的导入流程准备好；
  手机一回来就按 NA-036 推包开机。

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