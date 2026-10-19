#include "dm_touch_game_state.h"
#include "dm_touch_controls.h"
#include "../../host/dm_input.h"
#include <stdio.h>
#include <stdlib.h>
uint64_t dm_tg_portal_mask(const dm_tg_snapshot *,uint64_t);
#ifdef RED_BASELINE
/* v1旧策略的测试替身：valid永久复用，故意不检查时间。 | Test double for the old v1 policy: valid is reused forever, deliberately not checking time. */
uint64_t dm_tg_portal_mask(const dm_tg_snapshot *s,uint64_t n){(void)n;return s->valid?s->portal.buttons:0;}
#endif
static int checks;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"FAIL line=%d %s\n",__LINE__,#x);exit(1);}}while(0)
int main(void){
 dm_tg_snapshot s={.supported=1,.valid=1,.ready=1,.captured_ns=1000000000,.portal={.valid=1,.buttons=258}};
 CHECK(dm_tg_portal_mask(&s,1250000001)==0);
 CHECK(dm_tg_portal_mask(&s,1250000000)==258);CHECK(dm_tg_portal_mask(&s,1000000000)==258);
 CHECK(dm_tg_portal_mask(&s,999999999)==0);s.captured_ns=0;CHECK(dm_tg_portal_mask(&s,1)==0);
 s.captured_ns=1000000000;s.valid=0;CHECK(dm_tg_portal_mask(&s,1000000000)==0);
 s.valid=1;s.supported=0;CHECK(dm_tg_portal_mask(&s,1000000000)==0);
 s.supported=1;s.portal.valid=0;CHECK(dm_tg_portal_mask(&s,1000000000)==0);s.portal.valid=1;
 printf("PASS synthetic host-clock freshness+held-map-change %d/%d checks\n",checks,checks);return 0;
}
