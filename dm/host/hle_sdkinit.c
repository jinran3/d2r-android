// nninitInitializeSdkModule 调的服务层初始化：真机上各自连 Horizon 系统服务（IPC），宿主没有这些服务进程。
// 原生接管：不建会话，直接返回；各服务的后续接口在用到时逐个接管成宿主实现（见同目录 hle_*.c）。
// nn::os::InitializeVirtualAddressMemory 属 SDK 的 os 层，不接管；fs::SetLocalApplicationAccessLog /
// SetResultHandledByApplication 只写 SDK 内部开关，不接管。
// Service layer initialization called by nninitInitializeSdkModule: on the real device each connects to a Horizon system service (IPC), the host has no such service processes.
// Native takeover: create no session, return directly; each service's later interfaces are taken over one by one as host implementations when they come into use (see hle_*.c in the same directory).
// nn::os::InitializeVirtualAddressMemory belongs to the SDK's os layer and is not taken over; fs::SetLocalApplicationAccessLog /
// SetResultHandledByApplication only write SDK-internal switches and are not taken over.
#include "hle.h"

static void once(const char *what) { LOG("init 接管：%s（空操作）", what); }

HLE_FORCE("nndiagStartup", "连 lm 日志服务；诊断日志改由宿主直接输出", void, h_nndiagStartup, void) { once("nndiagStartup"); }
HLE_FORCE("_ZN2nn2oe10InitializeEv", "连 am/oe 运行环境服务；运行环境查询逐个接成宿主默认值", void, h_oe_Initialize, void) { once("oe::Initialize"); }
HLE_FORCE("_ZN2nn3aoc10InitializeEv", "追加内容(DLC)服务：不建会话（无服务进程）；已拥有清单由 hle_misc.c 的 aoc 接口给出（术士君临，非空）", void, h_aoc_Initialize, void) { once("aoc::Initialize"); }
HLE_FORCE("_ZN2nn3err26InitializeContextWriterApiEv", "连 err 错误上下文服务；宿主不上报", void, h_err_InitCtx, void) { once("err::InitializeContextWriterApi"); }
HLE_FORCE("_ZN2nn2fs24InitializeForApplicationEv", "连 fsp-srv 文件服务；文件接口接宿主文件系统 + RomFS", void, h_fs_InitApp, void) { once("fs::InitializeForApplication"); }
HLE_FORCE("_ZN2nn4pctl10InitializeEv", "连 pctl 家长控制服务；单机无家长控制", void, h_pctl_Initialize, void) { once("pctl::Initialize"); }
HLE_FORCE("_ZN2nn4diag34InitializeApplicationAbortObserverEv", "注册到系统的中止观察；宿主崩溃由信号处理打印", void, h_diag_AbortObs, void) { once("diag::InitializeApplicationAbortObserver"); }

// am 的 CommonStateGetter：真机上由 oe::Initialize 连上 am 服务后创建这个对象（sdk+0xba1b90 的懒创建指针）；
// 宿主没有 am 服务进程，SDK 里那个指针一直是 NULL —— TotK 的 nninitStartup 会「取对象再调虚方法」，
// 于是 `ldr x8,[x0]` 在 sdk+0x1ead5c 直接 SIGSEGV（真机首跑 2026-10-22 实测，PLT 槽 0xb70db0）。
// 这里按本文件的既有做法接管这个接口：返回静态对象，虚表每一项都指向「返回 0」的桩。
// 对象布局只有第一项（虚表指针）有意义；64 项足够覆盖 0x130 这类高位槽（0x130/8 = 38）。
// am's CommonStateGetter: on the real device oe::Initialize connects to the am service and creates this object
// (the lazily-created pointer at sdk+0xba1b90). The host has no am service process, so that pointer stays NULL and
// TotK's nninitStartup dereferences it (SIGSEGV at sdk+0x1ead5c, PLT slot 0xb70db0, first device boot 2026-10-22).
// Following this file's convention, take the interface over: return a static object whose vtable is all
// "return 0" stubs. Only the first field (the vtable pointer) matters; 64 slots cover high offsets like 0x130.
static uint64_t h_am_method(void) { return 0; }
typedef uint64_t (*h_am_fn)(void);
static h_am_fn const g_am_vtable[64] = { [0 ... 63] = &h_am_method };
static struct { h_am_fn const *vtable; uint64_t pad[15]; } g_am_object = { g_am_vtable, {0} };
HLE_FORCE("_ZN2nn2am20GetCommonStateGetterEv", "am 公共状态读取器：宿主给静态对象，方法全部返回 0（没有 am 服务进程）", void *, h_am_common_state, void) {
    return &g_am_object;
}

// am 的 ApplicationFunctions（`GetApplicationFunctions`）：真机上由 am 服务给出，客体经它取「应用级函数表」
// （前序程序索引、启动参数、DLC 列表等）。宿主没有 am 服务进程，SDK 里那个指针一直是 NULL ——
// TotK 的 `nn::applet::GetPreviousProgramIndex` 先取对象再调虚表 **+0x190（第 50 槽）**，
// 于是 `ldr x8,[x0]` 在 sdk+0x1ea684 直接 SIGSEGV（trim-b62 真机实测）。
// 与 CommonStateGetter 同构（静态对象 + 全 0 桩），但第 50 槽的语义是「写 s32 出参、返回 Result」：
// 本机是直接启动、没有前序程序，按 Horizon 语义写 -1、返回 0，走成功分支。
// am's ApplicationFunctions (`GetApplicationFunctions`): on the real device the am service provides it and the guest
// uses it for application-level functions (previous program index, launch arguments, the DLC list). The host has no am
// service process, so the pointer stays NULL and TotK's `nn::applet::GetPreviousProgramIndex` dereferences it
// (SIGSEGV at sdk+0x1ea684, measured on the device with trim-b62) before calling vtable **+0x190 (slot 50)**.
// Same shape as CommonStateGetter (static object, all-zero stubs), but slot 50 means "write an s32 out param and
// return a Result": this is a direct launch with no previous program, so write -1 and return 0 to take the success path.
static uint64_t h_am_af_prev_program(void *self, int32_t *out) { (void)self; if (out) *out = -1; return 0; }
static uint64_t h_am_af_method(void) { return 0; }
typedef uint64_t (*h_am_af_fn)(void);
static h_am_af_fn const g_am_af_vtable[64] = {
    [0 ... 49] = &h_am_af_method,
    [50] = (h_am_af_fn)&h_am_af_prev_program,
    [51 ... 63] = &h_am_af_method,
};
static struct { h_am_af_fn const *vtable; uint64_t pad[15]; } g_am_af_object = { g_am_af_vtable, {0} };
HLE_FORCE("_ZN2nn2am23GetApplicationFunctionsEv", "am 应用函数表：宿主给静态对象；0x190 槽按「无前序程序」写 -1 返回成功", void *, h_am_app_functions, void) {
    return &g_am_af_object;
}
