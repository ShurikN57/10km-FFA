from pathlib import Path

FILES=[Path('mobile.html'),Path('app base.html')]
for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')
    text=text.replace(
        '.rank-filter-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:9px}',
        '.rank-filter-grid{display:grid;grid-template-columns:.88fr 1.12fr;gap:8px;margin-bottom:9px}',
        1
    )
    text=text.replace(
        '.rank-filter-grid select{font-size:14px!important;padding:11px 30px 11px 10px}',
        '.rank-filter-grid select{font-size:14px!important;padding:11px 24px 11px 10px}',
        1
    )
    path.write_text(text,encoding='utf-8')
