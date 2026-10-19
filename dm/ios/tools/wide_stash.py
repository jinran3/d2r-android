#!/usr/bin/env python3
# 储藏箱加宽：个人 / 共享页 10 → 14 列。
# 数据：两份 inventory.bin（excel/ 与 excel/base/）的大储藏箱页两行（第 10、25 行，+16 字节 = 列数）10 → 14，个人页与共享页都用这两行；服务端按它判格子是否合法（实测 x=12 放得进、存读档不丢）。
# 画面：储藏箱底图（个人 / 共享 / 通用）在格子区插 4 列、下段金币框居中；宝石 / 材料 / 符文三页的底图两侧本来透明，左右各补 98 像素透明 = 居中。
# 外框是 14 个面板共用的一张图（ControllerOverlay 的 Background），不改它，另加一个 WideBackground（原双面板帧左半插宽 196 像素），
# 平时放屏幕外，储藏箱开着时由宿主挪进来（dm_cursor.c ui_widestash_pump）。贴图都由 gen_widestash_art.py 预先做成原包同款 DXT5 块线性，放在 NativeHUD/widestash/，这里只拷。
# 面板矩形的左移 / 加宽、物品栏右移、标题条也在宿主做（各档位的面板矩形不同，不写死在这里）。
# 1 像素 = 2 布局单位；加宽 392 单位 = 196 像素 = 4 格。
# Stash widening: personal / shared pages 10 → 14 columns.
# Data: in the two inventory.bin copies (excel/ and excel/base/) the two large-stash page rows (rows 10 and 25, +16 bytes = column count) go 10 → 14, and both the personal and shared pages use these two rows; the server uses it to judge whether a cell is legal (measured: an item fits at x=12 and is not lost across save and load).
# Picture: the stash background images (personal / shared / generic) get 4 columns inserted in the cell area and the gold box in the lower section centered; the background images of the three gem / material / rune pages are transparent on both sides anyway, so 98 transparent pixels are added on each side = centered.
# The outer frame is one image shared by 14 panels (the Background of ControllerOverlay); it is not changed, and a separate WideBackground is added (the left half of the original double-panel frame widened by inserting 196 pixels),
# normally kept off screen and moved in by the host while the stash is open (dm_cursor.c ui_widestash_pump). The textures are all prepared in advance by gen_widestash_art.py as DXT5 block-linear, the same kind as the original package, and placed in NativeHUD/widestash/; here they are only copied.
# Shifting left / widening of the panel rectangle, shifting the inventory right and the title bar are also done on the host (panel rectangles differ per profile and are not hard-coded here).
# 1 pixel = 2 layout units; widening of 392 units = 196 pixels = 4 cells.
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touch_layout

HERE = os.path.dirname(os.path.abspath(__file__)); ART = __import__('gen_paths').gen_dir('NativeHUD', 'widestash')   # 构建时由 gen_widestash_art.py 生成 | Generated at build time by gen_widestash_art.py
COLS = 14; EX = 392   # 加宽布局单位 | Widening in layout units
BANK = 'controller/bankexpansionlayouthd.json'; OVERLAY = 'controller/controlleroverlayhd.json'
SPRITES = {n: 'controller/panel/stash/v2/' + n.lower() for n in ('StashPanelBG', 'StashPanelBGPersonal', 'StashPanelBGShared')}   # NativeHUD/widestash/<名>_wide.sprite → 原路径 | NativeHUD/widestash/<name>_wide.sprite → original path
SPRITES.update({n: 'controller/panel/stash/v2/additionalstash/' + n.lower() for n in ('AdvancedStash_Gems_Console', 'AdvancedStash_Consumables_Console', 'AdvancedStash_Runes_Console')})
WIDE_FRAME = 'controller/panel/zswide/mainpanelbg_wide'   # 新增路径（casc_overlay 要求新增文件落在新子目录里） | Newly added path (casc_overlay requires newly added files to land in a new subdirectory)

def _entry(romfs, suffix):
    for line in open(os.path.join(romfs, 'data', 'build_manifest.psv'), encoding='utf-8'):
        f = line.rstrip('\n').split('|')
        if len(f) >= 11 and not line.startswith('#') and f[9].lower().endswith(suffix): return f[9].split(':', 1)[1].lower(), touch_layout._read_entry(romfs, f)
    raise SystemExit('wide_stash：包里没有 ' + suffix)

def _shift(s, name, dx, start=0):
    """控件 name 的 rect x 加 dx（按文本改：布局带注释与尾逗号）。返回新文本。 | Add dx to the rect x of the widget named name (edited as text: layouts carry comments and trailing commas). Returns the new text."""
    m = re.search(r'"name"\s*:\s*"%s"' % re.escape(name), s[start:])
    if not m: raise SystemExit('wide_stash：储藏箱布局里没有控件 ' + name)
    i = start + m.end(); r = re.compile(r'"rect"\s*:\s*\{\s*"x"\s*:\s*(-?\d+)').search(s, i)
    if not r or s.find('"name"', i, r.start()) != -1: raise SystemExit('wide_stash：控件 %s 的 rect 不在它自己的字段里' % name)
    return s[:r.start(1)] + str(int(r.group(1)) + dx) + s[r.end(1):]

def _container_x(s, name, dx):
    """无 rect 的容器（高级页三个）加 rect；有 rect 的（魔盒）加 dx。 | Containers without a rect (the three on the advanced pages) get a rect added; those with a rect (the cube) get dx added."""
    m = re.search(r'"name"\s*:\s*"%s"' % re.escape(name), s); i = m.end()
    nxt = s.find('"children"', i); f = s.find('"fields"', i)
    if f != -1 and f < nxt: return _shift(s, name, dx)
    return s[:i] + ',\n            "fields": { "rect": { "x": %d, "y": 0 } }' % dx + s[i:]

# 珍宝匣：宝石 / 符文 / 材料三页的格位合到宝石页那一页（底图 gen_trove_art.py）。原版按物品码认格位（槽控件字段 itemCode），与控件挂在哪个容器、摆在哪里无关（实测）：
# 三个容器里的槽控件全部拿掉，按珍宝匣的几何重写进宝石容器；材料、符文两个容器留空壳（原版按名字找它们）
# Trove: the slots of the gems / runes / materials pages are merged into the gems page (background gen_trove_art.py). The game identifies slots by item code (slot widget field itemCode), regardless of which container the widget is in or where it sits (measured):
# all slot widgets in the three containers are removed and rewritten into the gem container with the Trove geometry; the materials and runes containers are left as empty shells (the game looks them up by name)
def trove_slots(s):
    import gen_trove_art as T
    pat = re.compile(r'\{\s*"type"\s*:\s*"AdvancedStashSlotWidget"\s*,\s*"name"\s*:\s*"(\w+)"\s*,\s*"fields"\s*:\s*\{\s*"rect"\s*:\s*\{[^}]*\}\s*,\s*"itemCode"\s*:\s*"(\w+)"\s*,?\s*\}\s*,?\s*\}\s*,?')
    codes = [m.group(2) for m in pat.finditer(s)]; want = T.slots()
    if sorted(codes) != sorted(want) or any(m.group(1) != m.group(2) for m in pat.finditer(s)): raise SystemExit('wide_stash：高级仓库槽控件不是原版那 91 个（找到 %d 个；原版布局变了？）' % len(codes))
    s = pat.sub('', s); i = s.index('"children"', s.index('"name": "advancedstash_gems"')); i = s.index('[', i) + 1
    new = ',\n'.join('                { "type": "AdvancedStashSlotWidget", "name": "%s", "fields": { "rect": { "width": %d, "height": %d, "x": %d, "y": %d }, "itemCode": "%s" } }' % (c, w, h, x, y, c) for c, (x, y, w, h) in sorted(want.items()))
    return s[:i] + '\n' + new + '\n            ' + s[i:]

TOUCH_ONLY = {'TouchStashLeft', 'TouchStashRight', 'close'}   # 触屏版插回的控件（touch_layout INGAME）：手柄版布局（原版 + 功能改动，gen_romfs_overlay.py）里没有，没有就不挪 | Widgets re-inserted for the touch version (touch_layout INGAME): absent from the controller layouts (original + feature changes, gen_romfs_overlay.py); if absent, nothing is moved
def _has(s, nm): return re.search(r'"name"\s*:\s*"%s"' % re.escape(nm), s) is not None
def bank_layout(text):
    s = text; n0 = s.count('"cellCount": { "x": 10, "y": 10 }')
    if n0 != 1: raise SystemExit('wide_stash：储藏箱格子 cellCount 10×10 应为 1 处，找到 %d 处（原版布局变了？）' % n0)
    s = s.replace('"cellCount": { "x": 10, "y": 10 }', '"cellCount": { "x": %d, "y": 10 }' % COLS)
    half = EX // 2
    for nm in ('gold_amount', 'gold_withdraw', 'StashNavigation', 'TouchStashLeft', 'TouchStashRight'):   # 下段居中的那排 | The centered row in the lower section
        if nm in TOUCH_ONLY and not _has(s, nm): continue
        s = _shift(s, nm, half)
    for nm in ('ShowPreviousLadderSeasonToggle', 'close'):
        if nm in TOUCH_ONLY and not _has(s, nm): continue
        s = _shift(s, nm, EX)   # 靠右的：赛季开关；关闭钮落在宽外框右上角凹槽（外框右边比原来多出 196，面板左移 196 ⇒ 面板内 +392） | Right-aligned ones: the season toggle; the close button lands in the notch at the top-right corner of the wide outer frame (the right side of the outer frame extends 196 more than before and the panel shifts left 196 ⇒ +392 within the panel)
    s = trove_slots(s)
    for nm in ('advancedstash_gems', 'advancedstash_materials', 'advancedstash_runes', 'advancedstash_horadriccube'): s = _container_x(s, nm, half)
    s = _shift(s, 'advancedstash_horadriccube', -2 * __import__('gen_trove_art').SHIFT)   # 合成格（连同转化钮）跟着底图里的台座左移 | the crafting slot (with its Transmute button) shifts left with the pedestal in the background
    s = trove_tabs(s)
    return s

def _vt_text(name, x, y, w, h, color, size, align='left', text='', trunc=True):
    return {'type': 'TextBoxWidget', 'name': name, 'fields': {'rect': {'x': x, 'y': y, 'width': w, 'height': h}, 'text': text,
            'style': {'fontColor': color, 'pointSize': size, 'alignment': {'h': align, 'v': 'center'}}, 'truncateWithEllipsis': trunc}}
def trove_tabs(s):
    # 页签条：原版五个页签（个人 / 共享 / 宝石 / 材料 / 符文），第三个（宝石）改叫「珍宝匣」（dmTroveTab）；材料、符文两个页签由宿主挪出屏（dm_cursor.c ui_trove_tabs_pump）
    # Tab strip: the original five tabs (personal / shared / gems / materials / runes), the third one (gems) is renamed to 「珍宝匣」(dmTroveTab); the materials and runes tab images are moved off screen by the host (dm_cursor.c ui_trove_tabs_pump)
    for a, b in (('"textStrings": [ "@personal", "@shared", "@gems", "@materials", "@runes" ],', '"textStrings": [ "@personal", "@shared", "@dmTroveTab", "@materials", "@runes" ],'),):
        if s.count(a) != 1: raise SystemExit('wide_stash：储藏箱布局 %s 不是原样（原版布局变了？）' % a.strip())
        s = s.replace(a, b)
    # 页签条右端的手柄键帽（ZR）：原版按五个页签摆在 x 1135（= 五个页签的右沿 1075 再往外 60）。
    # 屏上只有三个页签（珍宝匣把材料 / 符文两个页签收掉了，dm_cursor.c ui_trove_tabs_pump）：键帽放在第三个页签右沿（860）外 60；左端的 ZL 不动。只改 BankTabs 这一条（同文件里另外几条页签条不动）；触屏版键帽是透明图，位置无所谓
    # Controller keycap (ZR) at the right end of the tab bar: the game places it at x 1135 for five tabs (= the right edge of five tabs, 1075, plus 60).
    # There are now only three tabs on screen (the Trove removed the materials / runes tabs, dm_cursor.c ui_trove_tabs_pump): the keycap goes 60 beyond the right edge of the third tab (860); ZL at the left end is untouched. Only the BankTabs entry is changed (the other tab strips in the same file are not); on the touch build the keycap is a transparent image, so its position does not matter
    i = s.index('"name": "BankTabs"'); k = '"tabRightIndicatorPosition": "$HalfPanelRightTabButtonPromptPosition",'; j = s.find(k, i)
    if j < 0 or j - i > 2500: raise SystemExit('wide_stash：BankTabs 的右端键帽位置不是原样（原版布局变了？）')
    s = s[:j] + '"tabRightIndicatorPosition": { "x": 920, "y": -2 },' + s[j + len(k):]
    return s

def overlay_layout(text):
    i = text.find('"name": "Background"'); j = text.find('"TabBarWidget", "name": "Tabs"')
    if i < 0 or j < 0: raise SystemExit('wide_stash：外框布局里没有 Background / Tabs（原版布局变了？）')
    k = text.rfind('{', 0, j)
    add = ('{\n                    "type": "ImageWidget", "name": "WideBackground",\n                    "fields": {\n'
           '                        "rect": { "x": 99999, "y": 0 },\n                        "filename": "Controller/Panel/zswide/MainPanelBG_Wide",\n                    },\n                },\n                ')
    text = text[:k] + add + text[k:]
    # 魔盒并排时的两个标题（dm_cursor.c 魔盒并排那段）：原版标题条此时写的是「赫拉迪克方块 | 物品栏」（魔盒面板在原版里占左边那一位），
    # 并排后左边其实是储藏箱、右边是魔盒。原版那两个字挪出屏（位置守卫），换成我们自己的两个文字控件：字用原版串（@stash / @box）、样式照面板标题，
    # 位置照储藏箱加宽后原版两个标题字的矩形（左 -196 宽 1832、右 1636 宽 1440，见 dm_cursor.c ui_wide_pump），缺省在屏外
    # The two titles while the cube is side by side (the cube side-by-side section of dm_cursor.c): the original title bar then reads 「赫拉迪克方块 | 物品栏」(Horadric Cube | Inventory) (in the original game the cube panel occupies the left position),
    # but once side by side the left is actually the stash and the right is the cube. The two original title texts are moved off screen (position guard) and replaced with two text widgets of our own: the text uses the original strings (@stash / @box), the style follows the panel title,
    # and the positions follow the rects of the two original title texts after the stash is widened (left -196 width 1832, right 1636 width 1440, see dm_cursor.c ui_wide_pump); off screen by default
    st = {'type': 'Widget', 'name': 'TouchSideTitle', 'fields': {'rect': {'x': 99999, 'y': 0, 'width': 3272, 'height': 103}}, 'children': [
        _vt_text('TouchSideTitle_L', 0, 0, 1832, 103, '$FontColorWhite', '$MediumFontSize', 'center', '@stash'),
        _vt_text('TouchSideTitle_R', 1832, 0, 1440, 103, '$FontColorWhite', '$MediumFontSize', 'center', '@box')]}
    # 插在标题条 Tabs 这个控件的后面、同一个父控件里（同一套缩放与原点，各种屏幕档位都跟着原版标题走；画在标题条之上）
    # Inserted right after the title bar's Tabs widget, in the same parent widget (same scaling and origin, so it follows the original title on every screen profile; drawn above the title bar)
    j = text.find('"TabBarWidget", "name": "Tabs"'); k = text.rfind('{', 0, j); d = 0; e = k
    while e < len(text):
        c = text[e]
        if c == '{': d += 1
        elif c == '}':
            d -= 1
            if d == 0: break
        e += 1
    if d != 0: raise SystemExit('wide_stash：外框布局里 Tabs 控件的括号没配上（原版布局变了？）')
    return text[:e + 1] + ',\n                ' + json.dumps(st, ensure_ascii=False) + text[e + 1:]

def build(romfs, outdir, repl):
    out = {}
    # 表有两份：excel/inventory.bin 与 excel/base/inventory.bin，游戏按角色所属的模式选一套数据表（取格函数 main+0x560b80 按 [单位+0x1bd] 选）。
    # 只改一份时，用另一套的角色（如 88 级法师这类老角色）界面画 14 列、游戏按 10 宽取格，指到第 10 列越界读崩 main+0x560c6c
    # There are two copies of the table: excel/inventory.bin and excel/base/inventory.bin; the game picks one set of data tables by the mode the character belongs to (the cell lookup function main+0x560b80 selects by [unit+0x1bd]).
    # If only one copy is changed, for characters using the other set (old characters such as the level 88 sorceress) the UI draws 14 columns while the game looks up cells at width 10, and pointing at column 10 reads out of bounds and crashes at main+0x560c6c
    for sub in ('', 'base_'):
        path, inv = _entry(romfs, '/global/excel/' + sub.replace('_', '/') + 'inventory.bin'); inv = bytearray(inv)
        for row in (10, 25):
            o = 4 + row * 240 + 16
            if inv[o:o + 2] != b'\x0a\x0a': raise SystemExit('wide_stash：%s 第 %d 行不是 10×10（原版表变了？）' % (path, row))
            inv[o] = COLS
        # 佣兵加装备位（秘境 10 层解锁，产物 r39 起配服务端那道门）：佣兵行（第 11 行，第二套第 26 行）原版只定义了右手 / 身 / 左手 / 头四个部位的格子，
        # 项链 / 右戒 / 左戒 / 腰带 / 鞋 / 手套（格序 4–9）全是 −1；服务端放置校验 main+0x65032c 对非玩家主人固定读第 11 行，四个坐标全负就拒。
        # 这里照玩家行（第 0 行）的相对位置补上：玩家面板原点在 x = 320，佣兵面板在 0；第二套整体再偏 (+80, +60)（两行已有四格的差）。每格 20 字节：左 右 上 下 + 1 个整数
        # Extra mercenary equipment slots (unlocked at rift level 10; paired with the server-side gate from build output r39): the mercenary row (row 11, row 26 in the second set) in the original only defines cells for the four body locations right hand / torso / left hand / head,
        # while amulet / right ring / left ring / belt / boots / gloves (cell order 4–9) are all −1; the server placement check main+0x65032c always reads row 11 for non-player owners and rejects when all four coordinates are negative.
        # Here they are filled in following the relative positions in the player row (row 0): the player panel's origin is at x = 320 and the mercenary panel's at 0; the second set is offset by a further (+80, +60) overall (the difference of the four existing cells between the two rows). 20 bytes per cell: left right top bottom + 1 integer
        import struct
        for row, dx, dy in ((11, -320, 0), (26, -240, 60)):
            base = 4 + row * 240 + 0x28
            if struct.unpack_from('<4i', inv, base + 4 * 0x14) != (-1, -1, -1, -1): raise SystemExit('wide_stash：%s 第 %d 行的项链格不是空的（原版表变了？）' % (path, row))
            for k in range(4, 10):
                l, r, t, b_, x = struct.unpack_from('<5i', inv, 4 + 0x28 + k * 0x14)
                struct.pack_into('<5i', inv, base + k * 0x14, l + dx, r + dx, t + dy, b_ + dy, x)
        p = os.path.join(outdir, 'ws_' + sub + 'inventory.bin'); open(p, 'wb').write(inv); out[path] = p
    for n, rel in SPRITES.items():
        p = os.path.join(outdir, 'ws_' + n + '.sprite'); shutil.copyfile(os.path.join(ART, n + '_wide.sprite'), p); out['data/hd/global/ui/' + rel + '.sprite'] = p
    p = os.path.join(outdir, 'ws_mainpanelbg_wide.sprite'); shutil.copyfile(os.path.join(ART, 'MainPanelBG_Wide.sprite'), p); out['+data/hd/global/ui/' + WIDE_FRAME + '.sprite'] = p
    for rel, fn in ((BANK, bank_layout), (OVERLAY, overlay_layout)):
        logical = touch_layout.read_layout(romfs, rel)[0].lower(); src = repl.get(logical)
        text = open(src, encoding='utf-8').read() if src else touch_layout.read_layout(romfs, rel)[1]   # 叠在触摸布局已改的那份上 | Stacked on top of the copy already modified by the touch layout
        p = os.path.join(outdir, 'ws_' + os.path.basename(rel)); open(p, 'w', encoding='utf-8').write(fn(text)); out[logical] = p
    return out, {'cols': COLS, 'files': len(out)}
