// nn::vi（显示层）：真机经 vi 服务开显示、建图层、取原生窗口句柄；句柄交给 NVN 的窗口 builder。
// 宿主：返回宿主静态对象；接 Metal 时原生窗口对应前端的 CAMetalLayer（front_metal_layer()）。
// nn::vi (display layer): on a real device, the vi service is used to open the display, create a layer and get the native window handle; the handle is passed to NVN's window builder.
// Host: returns host static objects; when hooking up Metal, the native window corresponds to the front end's CAMetalLayer (front_metal_layer()).
#include "../host/hle.h"
#include <stdatomic.h>
#include <time.h>

static struct { uint32_t magic; } g_display = {0x50534944}, g_layer = {0x5259414c};
static struct { uint32_t magic; void *layer; } g_native = {0x4e49574e, 0};

HLE_FORCE("_ZN2nn2vi10InitializeEv", "显示服务初始化；宿主无 vi 服务", void, h_vi_Init, void) {}
HLE_FORCE("_ZN2nn2vi18OpenDefaultDisplayEPPNS0_7DisplayE", "开默认显示；宿主给静态对象", Result, h_vi_OpenDisp, void **out) {
    *out = &g_display; return RES_OK;
}
HLE_FORCE("_ZN2nn2vi11CreateLayerEPPNS0_5LayerEPNS0_7DisplayE", "建图层；宿主给静态对象", Result, h_vi_CreateLayer, void **out, void *disp) {
    (void)disp; *out = &g_layer; return RES_OK;
}
HLE_FORCE("_ZN2nn2vi15GetNativeWindowEPPvPNS0_5LayerE", "原生窗口句柄，交给 NVN 窗口 builder；宿主给静态对象", Result, h_vi_GetNative, void **out, void *layer) {
    (void)layer; *out = &g_native; return RES_OK;
}

// VSync 事件：真机由 vi 服务给出（`GetDisplayVsyncEvent` 先取服务对象，再经虚表 +0xb8 换到内核事件句柄，
// 最后由 SDK 自己把句柄挂到 `nn::os::SystemEventType`）。宿主没有服务框架，也不去伪造 sf 代理对象 ——
// 整条接管：在客体线程上让 SDK 自己经 CreateSystemEvent(跨进程) 建事件，宿主再按 60 Hz 触发写端。
// 生成原因（trim-b60 真机）：CRASH sig=11 addr=0 pc=sdk+0x44f3f4 —— 该函数拿到的服务对象是 0，随后 `ldr x8,[x21]` 崩。
// VSync event: on a real device the vi service provides it (`GetDisplayVsyncEvent` first obtains the service object, then
// goes through vtable +0xb8 to get a kernel event handle, and finally the SDK attaches that handle to an
// `nn::os::SystemEventType`). The host has no service framework and does not fake sf proxy objects -- the whole call is
// taken over: on the guest thread the SDK itself creates the event through CreateSystemEvent(inter-process), and the host
// signals the write end at 60 Hz.
// Why (device, trim-b60): CRASH sig=11 addr=0 pc=sdk+0x44f3f4 -- the service object it obtained was 0, then `ldr x8,[x21]` faulted.
static _Atomic(uintptr_t) g_vsync_ev;
static pthread_once_t g_vsync_once = PTHREAD_ONCE_INIT;
static void *vsync_ticker(void *unused) {
    (void)unused;
    struct timespec tick = {0, 16666667};   // 60 Hz
    for (;;) {
        uintptr_t ev = atomic_load(&g_vsync_ev);
        if (ev) hle_signal_system_event((void *)ev);
        nanosleep(&tick, NULL);
    }
    return NULL;
}
static void vsync_ticker_start(void) {
    pthread_t th;
    if (pthread_create(&th, NULL, vsync_ticker, NULL)) die("vi：vsync 触发线程建不起来");
    pthread_detach(th);
}
HLE_FORCE("_ZN2nn2vi20GetDisplayVsyncEventEPNS_2os15SystemEventTypeEPNS0_7DisplayE",
          "vsync 事件：宿主自建客体事件并按 60 Hz 触发（无 vi 服务框架）", Result, h_vi_GetVsyncEvent,
          void *ev, void *display) {
    (void)display;
    if (!ev) return RES_OK;
    hle_bind_system_event(ev, 0);   // 必须在客体线程上；本函数由客体 bl 进来，满足条件 | must run on a guest thread, which holds here
    atomic_store(&g_vsync_ev, (uintptr_t)ev);
    pthread_once(&g_vsync_once, vsync_ticker_start);
    LOG("vi::GetDisplayVsyncEvent 接管：事件 %p，宿主按 60 Hz 触发", ev);
    return RES_OK;
}
