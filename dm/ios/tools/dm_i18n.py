#!/usr/bin/env python3
"""我们自己加的界面文字的中英表（英文版）：唯一来源 dm/i18n/ui_text.tsv（键 / 中文 / English / 用在哪）。
做法 = 把每一行作为新条目追加进原版字符串表 ui.json（RomFS 覆盖层，与 touch_strings 同一套机制）：zhCN / zhTW 列 = 中文（繁体玩家读简体比读英文顺），其余 11 种语言列 = English。
这样布局里写「@键」、宿主用原版取串 main+0x7f5630 取，语言切换由原版自己重装字符串表完成（SetLanguage，r34 起不剪），不用我们另跟语言。
Chinese-English string table for the UI text we added ourselves (English version): single source dm/i18n/ui_text.tsv (key / Chinese / English / where used).
Approach = append each row as a new entry to the original string table ui.json (RomFS overlay, same mechanism as touch_strings): zhCN / zhTW columns = Chinese (Traditional Chinese players read Simplified more easily than English), the other 11 language columns = English.
This way layouts write "@key", the host fetches through the original string lookup at main+0x7f5630, and language switching is done by the original game reloading its string tables itself (SetLanguage, no longer patched out as of r34), so we do not have to follow the language separately."""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, '..', '..', 'i18n', 'ui_text.tsv')
LANGS = ('enUS', 'zhTW', 'deDE', 'esES', 'frFR', 'itIT', 'koKR', 'plPL', 'esMX', 'jaJP', 'ptBR', 'ruRU', 'zhCN')   # 原版条目的列序 | column order of the original entries
ID0 = 300000   # 原版全部字符串表最大 id 251780；我们的条目从这里起按表序编号 | the largest id across all original string tables is 251780; our entries are numbered from here in table order

PROPER = '老机型补充包|D2R Mobile Resources|D2R Mobile'   # 英文里唯一许可的中文：App 显示名与资源文件夹名（玩家在桌面 /「文件」里看到的就是这几个字，改名另案，见盘点待定 6、7） | the only Chinese allowed in English text: the App display name and the asset folder name (these are the very characters the player sees on the home screen / in "Files"; renaming is a separate matter, see open items 6 and 7 of the inventory)
FMT = re.compile(r'%[-+ #0-9.]*(?:ll|l|h|z)?[a-zA-Z@%]')   # printf / strftime / NSString 占位符：中英两列必须同序同类（运行时拿英文串当格式串用） | printf / strftime / NSString placeholders: the Chinese and English columns must match in order and type (at run time the English string is used as a format string)

# The numbers are each field's pixel width measured from Mac screenshots ÷ the average English character width at that field's font size, less one
# character of margin. This is an approximation by character count, not a glyph-by-glyph width measurement;
# a string made of narrow letters only (i, l, 1) is actually shorter and one made of wide letters only (M, W) is longer, so new wording added to the
# table still needs a look at a screenshot
EN_LIMITS = (
)
# 键只许字母数字：布局里「@键」的解析遇到 _ 就断（@dmAuto_mana 显示成「丢失字符串_auto_mana」，Mac 上的 iOS 包实测）
# 英文界面下也要写汉字的键：当前没有此类键；若以后新增，只许用在指定了全球字体 BlizzardGlobal 的文字控件上（英文界面缺省字体没有汉字）。
# Keys may only contain letters and digits: the layout's "@key" parsing stops at _ (@dmAuto_mana was shown as "missing string_auto_mana", measured in the iOS package on a Mac)
# Keys that must show Chinese characters in the English UI as well: none currently; if one is added later, it is only allowed on text controls that specify the global font BlizzardGlobal (the default font of the English UI has no Chinese characters).
EN_HAS_ZH = set()
def rows():
    out = []
    with open(TABLE, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            k, zh, en = r['键'], r['中文'].replace('\\n', '\n'), r['English'].replace('\\n', '\n')
            if not re.fullmatch(r'dm[A-Za-z0-9]+', k) or not zh or not en: raise SystemExit('dm_i18n：表里这一行不对：%r' % r)
            if k not in EN_HAS_ZH and re.search(r'[　-鿿＀-￯]', re.sub(PROPER, '', en)): raise SystemExit('dm_i18n：%s 的英文里有中文字符：%r' % (k, en))
            if FMT.findall(zh) != FMT.findall(en): raise SystemExit('dm_i18n：%s 的中英占位符不一致：%s / %s' % (k, FMT.findall(zh), FMT.findall(en)))
            lim = next((n for pat, n in EN_LIMITS if re.fullmatch(pat, k)), None)   # 英文字数闸（见 EN_LIMITS） | English length gate (see EN_LIMITS)
            if lim is not None and len(FMT.sub('000', en).split('\n')[0]) > lim: raise SystemExit('dm_i18n：%s 的英文「%s」%d 个字符，超过这一栏的上限 %d（会顶框 / 被截断；压短，或给这一栏做英文专用的小字号控件后再改上限）' % (k, en, len(FMT.sub('000', en)), lim))
            out.append((k, zh, en))
    ks = [k for k, _, _ in out]
    if len(set(ks)) != len(ks): raise SystemExit('dm_i18n：键重复：%s' % sorted({k for k in ks if ks.count(k) > 1}))
    return out

def build(romfs, outdir, repl):
    """repl：前面步骤已换的 {包内逻辑路径: 本地文件}。返回 ({包内逻辑路径: 本地文件}, 条数)。 | repl: {logical path in the package: local file} already replaced by earlier steps. Returns ({logical path in the package: local file}, entry count)."""
    import touch_layout   # 用时再导，避免模块层互导留下半初始化状态 | imported at use time to avoid a half-initialized top-level mutual import
    path, text = touch_layout.read_layout(romfs, None, suffix='/lng/strings/ui.json')
    prev = repl.get(path.lower())
    if prev: text = open(prev, encoding='utf-8-sig').read()
    have = set(re.findall(r'"Key":\s*"((?:[^"\\]|\\.)*)"', text))
    rs = rows()
    clash = [k for k, _, _ in rs if k in have]
    if clash: raise SystemExit('dm_i18n：键和原版重名：%s' % clash)
    add = [{'id': ID0 + i, 'Key': k, **{l: (zh if l in ('zhCN', 'zhTW') else en) for l in LANGS}} for i, (k, zh, en) in enumerate(rs)]
    end = text.rstrip().rindex(']')
    body = ',\n'.join('  ' + json.dumps(e, ensure_ascii=False) for e in add)
    text = text[:end].rstrip() + ',\n' + body + '\n' + text[end:]
    json.loads(text)   # 拼完还是合法 JSON | still valid JSON after assembly
    o = os.path.join(outdir, 'i18n_ui.json'); open(o, 'w', encoding='utf-8-sig', newline='').write(text)
    return {path.lower(): o}, len(add)

def header():
    """dm/host/dm_i18n_tab.h 的内容（游戏外画的字用的编译期表）。 | Contents of dm/host/dm_i18n_tab.h (the compile-time table for text drawn outside the game)."""
    c = lambda s: json.dumps(s, ensure_ascii=False)   # JSON 串的转义在 C 里同样成立（\n \" \\） | JSON string escapes are equally valid in C (newline, double quote, backslash)
    out = ['// 生成文件，勿手改：python3 dm/ios/tools/dm_i18n.py --header > dm/host/dm_i18n_tab.h（表 dm/i18n/ui_text.tsv）', '#pragma once',
           'static const struct { const char *k, *zh, *en; } k_dm_i18n[] = {']
    out += ['    { %s, %s, %s },' % (c(k), c(zh), c(en)) for k, zh, en in rows()]
    return '\n'.join(out + ['};', ''])

if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--header']: sys.stdout.write(header())
    elif sys.argv[1:] == ['--check']:   # 单测：表与入库的头文件一致 | unit test: the table matches the checked-in header file
        h = os.path.join(HERE, '..', '..', 'host', 'dm_i18n_tab.h')
        if open(h, encoding='utf-8').read() != header(): raise SystemExit('dm_i18n：dm/host/dm_i18n_tab.h 过期，重跑 python3 dm/ios/tools/dm_i18n.py --header > dm/host/dm_i18n_tab.h')
        print('dm_i18n OK %d 条' % len(rows()))
    else: raise SystemExit('用法：dm_i18n.py --header | --check')
