// 64 KiB 描述符的零 padding、批内版本和 fence 后复用是真实 uniform 契约。
// Zero padding across the 64 KiB descriptor, per-draw versions and reuse after fences are real uniform contracts.
static uint8_t *uniform_test_mapping(VkDescriptorBufferInfo info) {
    for(uniform_chunk *c=uniform_chunks;c;c=c->next)if(c->buffer.buffer==info.buffer){assert(info.offset+info.range<=c->buffer.size);assert(!(info.offset%uniform_stride));return (uint8_t*)c->buffer.mapped+info.offset;}
    assert(0);return NULL;
}
// arena 槽位承载的 uniform 把位置放在绑定偏移里，描述符自身只留块基址；测试必须按同一条规则组合，
// 否则读到的是 arena 块首而不是真实输入。
// An arena-carried uniform keeps its position in the bind-time offset while the descriptor holds only the block
// base; the test must combine them the same way, or it would read the block start instead of the real input.
static VkDescriptorBufferInfo uniform_test_combine(VkDescriptorBufferInfo info,uint32_t dynamic_offset) {
    info.offset+=dynamic_offset;return info;
}
static VkDescriptorBufferInfo uniform_test_position(shader_entry *s,const shader_binding *b) {
    uint32_t dynamic_offset=0;return uniform_test_combine(uniform_buffer(s,b,&dynamic_offset),dynamic_offset);
}
static void uniform_arena_reference_test(void) {
    uint8_t *bytes=malloc(65536);assert(bytes);for(unsigned i=0;i<65536;i++)bytes[i]=(uint8_t)(i*37+13);
    shader_entry fragment={.stage=1},compute_shader={.stage=5};shader_binding guest={.kind=1,.slot=3},driver={.kind=1,.slot=0},handles={.kind=1,.slot=2},constant={.kind=1,.slot=1};
    assert(descriptor_type(&guest)==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC&&descriptor_type(&driver)==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC&&descriptor_type(&handles)==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC);
    assert(descriptor_type(&constant)==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER&&descriptor_type_uniform(VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC));
    memset(&state,0,sizeof state);state.ubo[1][0]=(p_bind_buf){.addr=(uintptr_t)bytes,.size=65536};
    mtl_sub_begin();VkDescriptorBufferInfo full=uniform_test_position(&fragment,&guest);assert(full.range==65536);assert(!memcmp(uniform_test_mapping(full),bytes,65536));
    state.ubo[1][0].size=16;VkDescriptorBufferInfo small=uniform_test_position(&fragment,&guest);assert(full.buffer!=small.buffer||full.offset!=small.offset);
    uint8_t *mapped=uniform_test_mapping(small);assert(!memcmp(mapped,bytes,16));for(unsigned i=16;i<65536;i++)assert(!mapped[i]);assert(!memcmp(uniform_test_mapping(full),bytes,65536));
    // 同一份内容重复读：uniform 页是**按内容寻址**的（同一 commit 引入的 per-draw 优化），内容不变就复用同一页，
    // descriptor 指向的字节也就不会变 —— 这里要保的是"读到的永远是当前内容"，不是"每次都换页"。
    // Reading the same bytes again: uniform pages are content-addressed (the per-draw optimization introduced in
    // the same commit), so unchanged content reuses the same page and the descriptor keeps pointing at valid
    // bytes. What matters here is "the read always yields the current content", not "every read gets a new page".
    VkDescriptorBufferInfo previous[20];for(unsigned i=0;i<20;i++){previous[i]=uniform_test_position(&fragment,&guest);assert(!memcmp(uniform_test_mapping(previous[i]),bytes,16));}
    // 内容变了必须换新页，而且**旧页的字节在本批 fence 完成前不能变**（旧 descriptor 还指着它）。
    // When the content changes a new page is required, and the bytes of the old page must not change before this
    // batch's fence completes (older descriptors still point at it).
    bytes[0]=0x5a;VkDescriptorBufferInfo changed=uniform_test_position(&fragment,&guest);
    assert(changed.buffer!=previous[0].buffer||changed.offset!=previous[0].offset);
    assert(uniform_test_mapping(changed)[0]==0x5a);
    assert(uniform_test_mapping(previous[0])[0]==(uint8_t)(0*37+13));
    bytes[0]=(uint8_t)(0*37+13);
    uint64_t hits=uniform_driver_hits;uint32_t first_offset=0,second_offset=0;
    VkDescriptorBufferInfo first=uniform_buffer(&compute_shader,&driver,&first_offset),second=uniform_buffer(&compute_shader,&driver,&second_offset);
    assert(first_offset==second_offset&&first.buffer==second.buffer&&first.offset==second.offset&&uniform_driver_hits==hits+1);
    VkDescriptorBufferInfo a=uniform_test_combine(first,first_offset);
    // c[0] 的 UBO 地址表只随**重新绑定**而变；直接改 state 绕过了绑定路径，缓存也就不会失效。
    // 真实游戏总是走绑定路径，所以这里也走绑定路径（OP_BIND_UBO）。
    // The c[0] UBO address table only changes on a re-bind; poking state directly bypasses the binding path and
    // therefore the cache invalidation. A real game always binds, so this test binds too (OP_BIND_UBO).
    p_bind_buf rebound={.stage=5,.index=0,.addr=(uintptr_t)bytes,.size=16};
    used=0;packet(OP_BIND_UBO,&rebound,sizeof rebound);packet(OP_END,NULL,0);mtl_exec(packets);
    uint32_t changed_offset=0;
    VkDescriptorBufferInfo c=uniform_test_combine(uniform_buffer(&compute_shader,&driver,&changed_offset),changed_offset);
    assert(c.buffer!=a.buffer||c.offset!=a.offset);
    assert(!memcmp(uniform_test_mapping(c)+0x210,&state.ubo[5][0].addr,8));for(unsigned i=0x210;i<0x220;i++)assert(!uniform_test_mapping(a)[i]);
    uint32_t before_offset=0,after_offset=0;
    VkDescriptorBufferInfo before=uniform_test_combine(uniform_buffer(&fragment,&handles,&before_offset),before_offset);
    // 贴图句柄同理：c[2] 的句柄表只随**重新绑定**而变，所以走绑定路径。
    // The same for texture handles: the c[2] handle table only changes on a re-bind, so bind for real.
    p_bind_handles rebound_texture={.stage=1,.first=0,.n=1};rebound_texture.h[0]=123;
    used=0;packet(OP_BIND_TEX,&rebound_texture,sizeof rebound_texture);packet(OP_END,NULL,0);mtl_exec(packets);
    VkDescriptorBufferInfo after=uniform_test_combine(uniform_buffer(&fragment,&handles,&after_offset),after_offset);
    assert(before.buffer!=after.buffer||before.offset!=after.offset);
    uint32_t value;memcpy(&value,uniform_test_mapping(after)+0x168,4);assert(value==123);memcpy(&value,uniform_test_mapping(before)+0x168,4);assert(value==0);mtl_sub_commit();
    // 前一轮写满的页重用为未绑定槽时，全部 64 KiB 必须回到零。
    // A page written in full in the previous batch must become entirely zero when reused for an unbound slot.
    memset(&state,0,sizeof state);for(unsigned i=1;i<DM_VK_BATCH_SLOTS;i++){mtl_sub_begin();mtl_sub_commit();}mtl_sub_begin();VkDescriptorBufferInfo zero=uniform_allocate(0,&mapped);assert(zero.buffer==full.buffer&&zero.offset==full.offset);
    mapped=uniform_test_mapping(zero);for(unsigned i=0;i<65536;i++)assert(!mapped[i]);mtl_sub_commit();
    // 独立计算 shader 把 c0 的 UBO 地址/大小读到 SSBO；这条路径也让 GPU 真正消费动态偏移，
    // 而不是只验证 CPU 构造函数。
    // An independent compute shader copies c0's UBO address/size to an SSBO; this also makes the GPU consume the
    // dynamic offsets for real, rather than only checking the CPU constructor.
    uint32_t result[4]={0};uint8_t control[0x880]={10};prog_t program={.nstage=1,.sd={{.control=control}}};
    state.program=&program;state.ubo[5][0]=(p_bind_buf){.addr=(uintptr_t)bytes,.size=12};state.ssbo[5][0]=(p_bind_buf){.addr=(uintptr_t)result,.size=sizeof result};
    mtl_sub_begin();p_dispatch one={1,1,1,0};dispatch_compute(&one);mtl_sub_commit();uint64_t address;memcpy(&address,result,8);assert(address==(uintptr_t)bytes&&result[2]==12&&result[3]==0);
    free(bytes);printf("Vulkan uniform arena: zero padding, independent versions, driver reuse, compute UBO table passed; arena=%llu KiB\n",(unsigned long long)(uniform_arena_bytes/1024));
}
