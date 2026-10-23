// c[2] 驱动常量段的句柄表布局：两个档位的偏移与合并句柄打包。
// The handle table layout of the c[2] driver constant segment: the offsets of both profiles and the
// combined handle packing.
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include "../native/nvn_c2_layout.h"

int main(void) {
    const dm_nvn_c2_layout *d2r = dm_nvn_c2_layout_d2r();
    const dm_nvn_c2_layout *totk = dm_nvn_c2_layout_totk();

    // D2R：分离贴图 0x168 + 8r（128 槽）、分离采样器 0x568 + 8r（128 槽）、图像 0x120 + 8r。
    // D2R: separate textures at 0x168 + 8r (128 slots), separate samplers at 0x568 + 8r, images at 0x120 + 8r.
    assert(d2r->tex_base == 0x168 && d2r->tex_end == 0x568);
    assert((d2r->tex_end - d2r->tex_base) / 8 == 128);
    assert(d2r->samp_base == 0x568 && d2r->samp_end == 0x968);
    assert((d2r->samp_end - d2r->samp_base) / 8 == 128);
    assert(d2r->img_base == 0x120 && d2r->img_end == 0x168);
    assert(d2r->combined == 0);

    // TotK：合并句柄 0x20 + 8r（32 槽），图像表仍在 0x120，中间没有分离采样器表。
    // TotK: combined handles at 0x20 + 8r (32 slots), the image table still at 0x120, no separate sampler table.
    assert(totk->tex_base == 0x20 && totk->tex_end == 0x120);
    assert((totk->tex_end - totk->tex_base) / 8 == 32);
    assert(totk->samp_base == 0 && totk->samp_end == 0);
    assert(totk->img_base == 0x120 && totk->img_end == 0x168);
    assert(totk->combined == 1);

    // 两个档位的贴图表都不能压到图像表上。
    // Neither profile's texture table may overlap the image table.
    assert(d2r->tex_base >= d2r->img_end || d2r->tex_end <= d2r->img_base);
    assert(totk->tex_end <= totk->img_base);

    // 档位名：只认 totk，其余（含未设置与未知值）一律 D2R。
    // Profile names: only "totk" is recognized, everything else (including unset) is D2R.
    assert(dm_nvn_c2_layout_for_profile("totk") == totk);
    assert(dm_nvn_c2_layout_for_profile("d2r") == d2r);
    assert(dm_nvn_c2_layout_for_profile(NULL) == d2r);
    assert(dm_nvn_c2_layout_for_profile("unknown") == d2r);

    // 合并句柄：纹理 ID 低 20 位 + 采样器 ID 第 20..31 位。
    // A combined handle packs the texture id into the low 20 bits and the sampler id into bits 20..31.
    assert(dm_nvn_combined_handle(96, 97) == (96u | (97u << 20)));
    assert(dm_nvn_combined_handle(0x12345, 0x789) == (0x12345u | (0x789u << 20)));
    // 超出位宽的位被截断，不许串到对方那半边。
    // Bits beyond the field widths are truncated and never spill into the other half.
    assert(dm_nvn_combined_handle(0x100000, 1) == (1u << 20));
    assert(dm_nvn_combined_handle(1, 0x1000) == 1u);

    puts("NVN c[2] layout: D2R separate tables and TotK combined handles PASS");
    return 0;
}
