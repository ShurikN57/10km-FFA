from pathlib import Path

for path in [Path('mobile.html'), Path('app base.html')]:
    t = path.read_text(encoding='utf-8')

    # Preserve all current column widths; harmonize only heights/margins/vertical rhythm.
    old_css = '''.rank-filter-grid select,.rank-filter-grid input{width:100%;min-width:0;padding:11px}\n.rank-filter-grid-pb input{height:48px;min-height:48px;margin:0}\n.rank-filter-grid select{font-size:14px!important;padding:11px 24px 11px 10px}'''
    new_css = '''.rank-filter-grid select,.rank-filter-grid input{width:100%;min-width:0;height:48px;min-height:48px;margin:0;padding:11px}\n.rank-filter-grid select{font-size:14px!important;padding:11px 24px 11px 10px}'''
    if old_css not in t:
        raise SystemExit(f'Filter sizing CSS block not found in {path}')
    t = t.replace(old_css, new_css, 1)

    # Shorter placeholder requested by the user.
    if 'placeholder="Année naissance"' not in t:
        raise SystemExit(f'Year placeholder not found in {path}')
    t = t.replace('placeholder="Année naissance"', 'placeholder="Année"', 1)

    path.write_text(t, encoding='utf-8')
