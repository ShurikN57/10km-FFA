from pathlib import Path
import subprocess

# Restore the last known-good app files from immediately before the PWA/ranking patch.
for fname in ['mobile.html', 'app base.html']:
    good = subprocess.check_output(['git','show','51151e699b2e2caeb9a4a9d65226d888e31ea786^:'+fname])
    Path(fname).write_bytes(good)

for path in [Path('mobile.html'), Path('app base.html')]:
    t=path.read_text(encoding='utf-8')

    # Keep the validated fix for the white strip on short PWA screens.
    t=t.replace('html { -webkit-text-size-adjust:100%; }',
                'html { -webkit-text-size-adjust:100%; background:#05070b; min-height:100%; }',1)
    t=t.replace('''body{\n  background:radial-gradient(circle at 50% -12%,#121a27 0,#080b11 28%,#05070b 55%);\n  padding-bottom:calc(106px + env(safe-area-inset-bottom));\n}''',
                '''body{\n  background:radial-gradient(circle at 50% -12%,#121a27 0,#080b11 28%,#05070b 55%);\n  min-height:100vh;\n  min-height:100dvh;\n  padding-bottom:calc(106px + env(safe-area-inset-bottom));\n}''',1)

    # Hide Analyse in installed PWA with CSS only: no JS can break navigation/search.
    marker='''@media(max-width:390px){'''
    css='''@media (display-mode: standalone){\n  [data-app-tab="analyse"],[data-app-panel="analyse"]{display:none!important}\n  .app-tabbar{grid-template-columns:repeat(2,1fr)!important}\n}\n\n@media(max-width:390px){'''
    if marker in t:
        t=t.replace(marker,css,1)

    path.write_text(t,encoding='utf-8')
