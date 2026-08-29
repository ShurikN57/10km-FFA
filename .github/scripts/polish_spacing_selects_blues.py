from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    # 1) Reserve a real safe zone above the floating bottom tab bar.
    text=text.replace('.tab-panel{display:none}\n.tab-panel.active{display:block}',
                      '.tab-panel{display:none;padding-bottom:calc(120px + env(safe-area-inset-bottom))}\n.tab-panel.active{display:block}',1)

    # 2) Make the ranking selects fit comfortably on iPhone.
    text=text.replace('.rank-filter-grid select,.rank-filter-grid input{width:100%;padding:11px}',
                      '.rank-filter-grid select,.rank-filter-grid input{width:100%;min-width:0;padding:11px}\n.rank-filter-grid select{font-size:14px!important;padding:11px 30px 11px 10px}',1)

    # 3) One blue family across primary actions, tabs and active filters.
    text=text.replace('background:linear-gradient(180deg,#347cf4,#2766d9)!important;\n  border-color:#4a91ff!important;color:white!important;\n  box-shadow:0 7px 18px rgba(39,102,217,.22)',
                      'background:linear-gradient(180deg,#4c91ff,#3178e8)!important;\n  border-color:#67a1ff!important;color:white!important;\n  box-shadow:0 7px 18px rgba(76,145,255,.22)',1)
    text=text.replace('button.primary:active{background:#2766d9!important}',
                      'button.primary:active{background:#3178e8!important}',1)
    text=text.replace('color:#5b9dff;', 'color:var(--accent);', 1)

    # Search rank mode active state + Analysis filters use same hue, slightly darker than primary.
    text=text.replace('btn.style.background="#2458a6"; btn.style.borderColor="#3973cf";',
                      'btn.style.background="#2f6fbe"; btn.style.borderColor="#4c91ff";',2)
    text=text.replace('found.style.background="#2458a6"; found.style.borderColor="#3973cf";',
                      'found.style.background="#2f6fbe"; found.style.borderColor="#4c91ff";',1)
    text=text.replace('no.style.background="#2458a6"; no.style.borderColor="#3973cf";',
                      'no.style.background="#2f6fbe"; no.style.borderColor="#4c91ff";',1)

    path.write_text(text,encoding='utf-8')
