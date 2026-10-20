# TotK 移植进度

更新日期：2026-10-20。此文件随工作更新，是中断后继续移植的入口。

路线图与分阶段验收门见 [TotK 移植脚手架计划](TOTK_PORT_SCAFFOLD.zh-CN.md)（下称「计划」）。

交接入口见 [TotK 移植交接文档（HANDOFF）](HANDOFF.zh-CN.md)。

- 目标设备：一加 12（Snapdragon 8 Gen 3 / **Adreno 750** / Android）
- 起点：fork 自 `sydeEvans/d2r-android`（HEAD `5d8e322`），上游是 `jhaizhou-ops/d2r-mobile`
- 分支：`totk/scaffold`（`main` 保持 D2R 可构建，不混入 TotK 工作）

## 当前状态（继续开发先看这里）

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