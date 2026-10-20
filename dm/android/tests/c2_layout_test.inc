// c[2] 句柄表：D2R 与 TotK 两种布局下，读侧的槽号与句柄必须与写侧一致。
// The c[2] handle tables: under both the D2R and the TotK layout, the slot numbers and handles the
// reader resolves must agree with the writer.
#ifndef DM_ANDROID_C2_LAYOUT_TEST_INCLUDED
#define DM_ANDROID_C2_LAYOUT_TEST_INCLUDED
static void c2_layout_reference_test(void) {
    memset(&state,0,sizeof state);
    state.textures[1][10]=96;state.samplers[1][3]=97;state.samplers[1][10]=97;
    // D2R：分离贴图在 0x168 + 8r，分离采样器在 0x568 + 8r。
    // D2R: separate textures at 0x168 + 8r, separate samplers at 0x568 + 8r.
    setenv("DM_GAME_PROFILE","d2r",1);
    assert(dm_nvn_c2_layout_current()==dm_nvn_c2_layout_d2r());
    assert(shader_handle_word(1,2,0x168+8*10)==96);
    assert(shader_handle_word(1,2,0x568+8*3)==97);
    shader_binding d2r_texture={.handle=0x5a+2*10,.cb_slot=2};
    shader_binding d2r_sampler={.handle=0x568/4+2*3,.cb_slot=2};
    assert(shader_texture_slot(&d2r_texture,0)==10);
    assert(shader_texture_slot(&d2r_sampler,0)==-1);
    // TotK：合并句柄在 0x20 + 8r，纹理 ID 低 20 位 + 采样器 ID 第 20..31 位。
    // TotK: combined handles at 0x20 + 8r, the texture id in the low 20 bits and the sampler id in bits 20..31.
    setenv("DM_GAME_PROFILE","totk",1);
    assert(dm_nvn_c2_layout_current()==dm_nvn_c2_layout_totk());
    assert(shader_handle_word(1,2,0x20+8*10)==(96u|(97u<<20)));
    // D2R 的那两段在 TotK 档位下不再被读，句柄取不到就是 0（不能静默绑错资源）。
    // The D2R ranges are not read under the TotK profile: an unreachable handle is 0, never a wrong binding.
    assert(shader_handle_word(1,2,0x168+8*10)==0);
    assert(shader_handle_word(1,2,0x568+8*3)==0);
    shader_binding totk_texture={.handle=0x8+2*10,.cb_slot=2};
    assert(shader_texture_slot(&totk_texture,0)==10);
    assert(shader_texture_slot(&d2r_texture,0)==-1);
    // 图像句柄表两个档位同址。
    // The image handle table sits at the same offset in both profiles.
    state.images[1][2]=88;
    assert(shader_handle_word(1,2,0x120+8*2)==88);
    shader_binding image={.handle=0x120/4+2*2,.cb_slot=2};
    assert(shader_image_slot(&image,0)==2);
    unsetenv("DM_GAME_PROFILE");
    assert(dm_nvn_c2_layout_current()==dm_nvn_c2_layout_d2r());
    memset(&state,0,sizeof state);
    puts("Vulkan c[2] handle tables: D2R separate and TotK combined layouts match the shader offsets PASS");
}
#endif
