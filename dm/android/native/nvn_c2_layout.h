#ifndef DM_ANDROID_NVN_C2_LAYOUT_H
#define DM_ANDROID_NVN_C2_LAYOUT_H
// c[2] 驱动常量段里的句柄表布局：**D2R 与 TotK 不一样**，必须按游戏档位选。
//
// D2R（原版暗黑 2 重制版的 Switch 版）：**分离**贴图 —— 贴图句柄在 c[2][0x168 + 8r]（128 槽），
//   分离采样器在 c[2][0x568 + 8r]（128 槽），图像句柄在 c[2][0x120 + 8r]（8 槽，写 8 个、读 9 个）。
//   这三个值是 dm/gfx/tools/dmsh_build.py 在 10,847 条变体上全量实测出来的。
//
// TotK（王国之泪的 Switch 版）：**合并**句柄 —— 全部贴图引用都落在 c[2][0x20 + 8r]（32 槽），
//   句柄类型 0（handle >> 28 == 0），即纹理 ID 在低 20 位、采样器 ID 在第 20..31 位。
//   实测（9,807 个着色器）：贴图立即数（TidB，机器码第 36..48 位）给出的字节偏移集合是
//   0x20、0x28 … 0x118 的干净 8 字节步进，一个都不越界；0x120 正好是图像句柄表的起点，
//   与 D2R 侧一致 → 合并贴图表就是 c[2][0x20 .. 0x120)。TotK 没有分离采样器表。
//
// 档位由环境变量 DM_GAME_PROFILE 决定：启动界面写 launch-settings.conf 的 game_profile 键，
// launch_settings.c 把它转成这个变量；没设或不是 totk 就是 D2R 布局（D2R 行为一字未动）。
//
// The handle table layout inside the c[2] driver constant segment differs between the two
// games and must be selected per profile.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct dm_nvn_c2_layout {
    unsigned tex_base, tex_end;    // 贴图句柄表 | texture handle table
    unsigned samp_base, samp_end;  // 分离采样器句柄表（合并句柄时为空）| separate sampler table (empty for combined handles)
    unsigned img_base, img_end;    // 图像句柄表 | image handle table
    unsigned combined;             // 1 = 贴图槽里放的是合并句柄 | 1 = the texture table holds combined handles
    unsigned bytes;                // c[2] 段的总字节数 | total size of the c[2] segment
} dm_nvn_c2_layout;

static inline const dm_nvn_c2_layout *dm_nvn_c2_layout_d2r(void) {
    static const dm_nvn_c2_layout layout = {0x168, 0x568, 0x568, 0x968, 0x120, 0x168, 0, 0x968};
    return &layout;
}

static inline const dm_nvn_c2_layout *dm_nvn_c2_layout_totk(void) {
    static const dm_nvn_c2_layout layout = {0x20, 0x120, 0, 0, 0x120, 0x168, 1, 0x968};
    return &layout;
}

// 按档位名取布局：认得 totk 就是 TotK，其余一律 D2R（未知档位不猜）。
// The layout for a profile name: only "totk" selects TotK, everything else is D2R (an unknown
// profile is never guessed).
static inline const dm_nvn_c2_layout *dm_nvn_c2_layout_for_profile(const char *profile) {
    if (profile && !strcmp(profile, "totk")) return dm_nvn_c2_layout_totk();
    return dm_nvn_c2_layout_d2r();
}

// 当前档位的布局。环境变量只在开机时由启动设置写一次，进程内不变。
// The layout of the current profile. The environment variable is written once at boot by the
// launch settings and does not change during the process.
static inline const dm_nvn_c2_layout *dm_nvn_c2_layout_current(void) {
    return dm_nvn_c2_layout_for_profile(getenv("DM_GAME_PROFILE"));
}

// 合并句柄的打包：纹理 ID 低 20 位 + 采样器 ID 第 20..31 位。
// Packing of a combined handle: the texture id in the low 20 bits and the sampler id in bits 20..31.
#define DM_NVN_TEXTURE_ID_BITS 0xfffff
#define DM_NVN_SAMPLER_ID_BITS 0xfff

static inline uint32_t dm_nvn_combined_handle(uint64_t texture, uint64_t sampler) {
    return ((uint32_t)texture & DM_NVN_TEXTURE_ID_BITS) | (((uint32_t)sampler & DM_NVN_SAMPLER_ID_BITS) << 20);
}

#endif
