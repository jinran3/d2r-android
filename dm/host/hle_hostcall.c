// 宿主调用号分派（0x85 起；0x80 的 TACT 解码已随裁剪移除）。
// Host call dispatch (0x85 and up; the 0x80 TACT decode was removed by the trim).
// 号码登记表在 hle.h；hle_svc.c 的 svc_dispatch 对 0x80 起调这里。
// The number registry is in hle.h; svc_dispatch in hle_svc.c calls here from 0x80 up.
#include "hle.h"
#include <stdio.h>
#include <stdlib.h>
// 私有Render门：弱实现走原图；UI强实现只读确认cohort。x8临时结果，跳板两路恢复x8。
// Private Render gate: the weak implementation takes the original picture; the UI strong implementation only reads to confirm the cohort. x8 is the temporary result, both trampoline paths restore x8.
__attribute__((weak)) int dm_touch_game_hide_own_glyph(uint64_t widget) { (void)widget; return 0; }
// hle_svc.c 的 svc_dispatch 对 0x80 起调这里；0x85保x0。
// svc_dispatch in hle_svc.c calls here for 0x80 and up; 0x85 preserves x0.

uint64_t svc_host_call(int num, uint64_t *regs) {
    switch (num) {
    case SVC_HOST_PRIVATE_SKILL_AIM: { void svc_private_skill_aim(uint64_t *); svc_private_skill_aim(regs); return 1; }
    case SVC_HOST_PRIVATE_SKILL_RENDER: {
        // 「不画原版技能格图标」只在触屏模式要（图标由我们的技能圈画）；手柄模式是原版底栏，图标得照画——先前不分模式，手柄版底栏六格全空（线上 iPad + 实体手柄反馈，Mac 上复现）
        // "Do not draw the original skill slot icons" is only wanted in touch mode (the icons are drawn by our skill ring); controller mode uses the
        // original bottom bar, so the icons must be drawn as usual -- earlier the modes were not told apart and all six slots of the controller bottom bar
        // were empty (reported from a released build on iPad + physical controller, reproduced on Mac)
        { int dm_padmode_current(void); regs[8] = !dm_padmode_current() && dm_touch_game_hide_own_glyph(regs[19]) ? 1 : 0; }
        const char *path=getenv("DM_SKILL_RENDER_GATE_LOG");
        if(path) { static FILE *fp; static unsigned n[2]; if(!fp)fp=fopen(path,"w");
            if(fp && n[regs[8]]++ < 64) { fprintf(fp,"widget=%#llx match=%llu\n",regs[19],regs[8]);fflush(fp); } }
        return 1;
    }
    case SVC_HOST_C2S_DELIVER: { void c2s_deliver(uint64_t *); c2s_deliver(regs); return 1; }
    case SVC_HOST_C2S_SYS: { void c2s_deliver_sys(uint64_t *); c2s_deliver_sys(regs); return 1; }
    }
    return 0;
}
