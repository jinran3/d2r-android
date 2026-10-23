// R1 自检：把三个模块读进来、解析 MOD0/动态段、按 DT_RELR + 显式表做重定位，**只打印计数**。
// 这一层刻意不执行任何客体代码、不解析符号名 —— 先把「文件读对、重定位算对」钉死，再去 R2 碰内核垫片。
// R1 self-check: read the three modules, parse MOD0/dynamic, apply DT_RELR and the explicit tables, and only print
// counters. It deliberately runs no guest code and resolves no symbol names -- first pin down "the file is read right and
// the relocations add up", and only then move to the kernel shim in R2.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int64_t tag; uint64_t val; } dyn_t;
typedef struct { uint64_t off, info; int64_t addend; } rela_t;

static uint32_t rd32(const void *p) { uint32_t v; memcpy(&v, p, 4); return v; }
static uint64_t rd64(const void *p) { uint64_t v; memcpy(&v, p, 8); return v; }

enum { DT_RELA = 7, DT_RELASZ = 8, DT_SYMTAB = 6, DT_STRTAB = 5, DT_JMPREL = 23, DT_PLTRELSZ = 2,
       DT_INIT_ARRAY = 25, DT_INIT_ARRAYSZ = 27, DT_RELR = 36, DT_RELRSZ = 35, DT_RELRENT = 37 };

typedef struct {
    const char *name;
    uint8_t *img;
    size_t size;
    uint64_t rela, relasz, jmprel, jmprelsz, init_array, init_arraysz;
    uint64_t n_relr, n_abs, n_jump;
} mod_t;

static uint8_t *slurp(const char *path, size_t *out_size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (n <= 0) { fclose(f); return NULL; }
    uint8_t *p = malloc((size_t)n);
    if (!p || fread(p, 1, (size_t)n, f) != (size_t)n) { free(p); fclose(f); return NULL; }
    fclose(f);
    *out_size = (size_t)n;
    return p;
}

// DT_RELR：偶数项给出新游标槽，奇数项是位图（覆盖随后 63 槽），位图之后游标**无条件**推进 63 槽；
// 槽值一律 `*槽 += 基址`，值为 0 的槽表示「指向模块基址」，不能当空哨兵跳过。
// DT_RELR: an even entry sets a new cursor slot, an odd entry is a bitmap covering the next 63 slots, and after a
// bitmap the cursor advances 63 slots unconditionally; every slot is `*slot += base`, and a zero slot means "points at
// the module base" rather than a null sentinel to skip.
static int walk_relr(mod_t *m, uint64_t off, uint64_t size, uint64_t ent) {
    if (!off || !size) return 0;
    if (ent != 8 || size % 8 || off > m->size || size > m->size - off) return -1;
    uint64_t base = (uint64_t)(uintptr_t)m->img, cursor = 0, n = 0;
    int anchored = 0;
    for (uint64_t i = 0; i < size / 8; i++) {
        uint64_t e = rd64(m->img + off + i * 8);
        if (!(e & 1)) {
            if (e & 7) return -1;
            cursor = e;
            anchored = 1;
        } else {
            if (!anchored) return -1;
            for (unsigned bit = 1; bit < 64; bit++)
                if ((e >> bit) & 1) {
                    uint64_t t = cursor + (uint64_t)(bit - 1) * 8;
                    if (t > m->size || 8 > m->size - t) return -1;
                    *(uint64_t *)(m->img + t) += base;
                    n++;
                }
            cursor += 63 * 8;
            continue;
        }
        if (cursor > m->size || 8 > m->size - cursor) return -1;
        *(uint64_t *)(m->img + cursor) += base;
        n++;
        cursor += 8;
    }
    return (int)n;
}

static int load_one(mod_t *m, const char *dir) {
    char path[1024];
    snprintf(path, sizeof path, "%s/%s.patched.bin", dir, m->name);
    m->img = slurp(path, &m->size);
    if (!m->img) return -1;
    uint32_t mod0 = rd32(m->img + 4);
    if (memcmp(m->img + mod0, "MOD0", 4)) return -2;
    const dyn_t *d = (const dyn_t *)(m->img + mod0 + (int32_t)rd32(m->img + mod0 + 4));
    uint64_t relr = 0, relrsz = 0, relrent = 0;
    for (; d->tag; d++) switch (d->tag) {
        case DT_RELA: m->rela = d->val; break;
        case DT_RELASZ: m->relasz = d->val; break;
        case DT_JMPREL: m->jmprel = d->val; break;
        case DT_PLTRELSZ: m->jmprelsz = d->val; break;
        case DT_INIT_ARRAY: m->init_array = d->val; break;
        case DT_INIT_ARRAYSZ: m->init_arraysz = d->val; break;
        case DT_RELR: relr = d->val; break;
        case DT_RELRSZ: relrsz = d->val; break;
        case DT_RELRENT: relrent = d->val; break;
    }
    int n = walk_relr(m, relr, relrsz, relrent);
    if (n < 0) return -3;
    m->n_relr = (uint64_t)n;
    m->n_abs = m->relasz / sizeof(rela_t);
    m->n_jump = m->jmprelsz / sizeof(rela_t);
    return 0;
}

// 返回写好的报告（调用方是 JNI，用 malloc 的缓冲，外面 free）
// Returns a malloc'd report (the JNI caller frees it)
char *totk_selfcheck(const char *dir) {
    static const char *names[] = {"main", "sdk", "subsdk0"};
    char *out = calloc(1, 8192);
    if (!out) return NULL;
    size_t used = 0;
    for (int i = 0; i < 3; i++) {
        mod_t m;
        memset(&m, 0, sizeof m);
        m.name = names[i];
        int rc = load_one(&m, dir);
        if (rc) {
            used += (size_t)snprintf(out + used, 8192 - used, "%s: 装载失败 rc=%d（目录 %s）\n", names[i], rc, dir);
            continue;
        }
        used += (size_t)snprintf(out + used, 8192 - used,
                                 "%s: relr=%llu abs/glob=%llu jump=%llu init_array=%llu 项（镜像 %zu 字节）\n",
                                 names[i], (unsigned long long)m.n_relr, (unsigned long long)m.n_abs,
                                 (unsigned long long)m.n_jump, (unsigned long long)(m.init_arraysz / 8), m.size);
        if (m.init_array && m.init_arraysz >= 24 && m.init_array + m.init_arraysz <= m.size) {
            const uint64_t *a = (const uint64_t *)(m.img + m.init_array);
            used += (size_t)snprintf(out + used, 8192 - used, "%s: init_array 首三项 %#llx %#llx %#llx（基址 %p）\n",
                                     names[i], (unsigned long long)a[0], (unsigned long long)a[1],
                                     (unsigned long long)a[2], (void *)m.img);
        }
        free(m.img);   // R1 不执行代码，读完就释放；R2 起要常驻
    }
    return out;
}
