from pathlib import Path
p=Path('mobile.html')
s=p.read_text(encoding='utf-8')
old='''.distance-switch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:2px;margin:0 0 14px;padding:4px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px;overflow:hidden}\n.distance-btn{min-width:0;min-height:44px;border:0!important;background:transparent!important;color:#c8ced8!important;border-radius:13px!important;font-size:13px!important;font-weight:800!important;padding:8px 4px!important;white-space:nowrap}\n.distance-btn.active{background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;box-shadow:0 5px 14px rgba(76,145,255,.20)}'''
new='''.distance-switch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:0 0 14px;padding:4px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px;overflow:hidden}\n.distance-btn{position:relative;min-width:0;min-height:44px;border:0!important;background:transparent!important;color:#c8ced8!important;border-radius:13px!important;font-size:13px!important;font-weight:800!important;padding:8px 4px!important;white-space:nowrap}\n.distance-btn+ .distance-btn::before{content:\"\";position:absolute;left:0;top:9px;bottom:9px;width:1px;background:rgba(148,163,184,.24);box-shadow:0 0 1px rgba(255,255,255,.08)}\n.distance-btn.active{background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;box-shadow:0 5px 14px rgba(76,145,255,.20);z-index:1}\n.distance-btn.active::before,.distance-btn.active+ .distance-btn::before{opacity:0}'''
if old not in s:
    raise SystemExit('distance CSS anchor not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched separators')
