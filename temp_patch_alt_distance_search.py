from pathlib import Path

p=Path('mobile.html')
s=p.read_text(encoding='utf-8')
old='''    if(!found.length){ msg.textContent="Aucun athlète trouvé."; return; }
    msg.textContent=found.length+(found.length===100?"+":"")+" profil"+(found.length>1?"s":"")+" trouvé"+(found.length>1?"s":"")+".";'''
new='''    if(!found.length){
      const otherDistances=Object.keys(FFA_DISTANCES).filter(d=>d!==currentDistance);
      const alternatives=[];
      for(const distance of otherDistances){
        const altParams=new URLSearchParams({distance,q:raw,mode:ffaRankMode});
        const altResponse=await fetch(FFA_API+"/search?"+altParams.toString(),{cache:"no-store"});
        if(!altResponse.ok) continue;
        const altData=await altResponse.json();
        if(token!==ffaApiSearchToken) return;
        const count=Array.isArray(altData.rows)?altData.rows.length:0;
        if(count) alternatives.push({distance,count});
      }
      if(token!==ffaApiSearchToken) return;
      if(!alternatives.length){ msg.textContent="Aucun athlète trouvé sur les distances disponibles."; return; }
      msg.textContent="Aucun athlète trouvé sur "+FFA_DISTANCES[currentDistance].label+".";
      box.style.display="block";
      box.innerHTML=alternatives.map(a=>`<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 11px;border-bottom:1px solid var(--line)"><div><div style="font-weight:700">Profil trouvé sur ${esc(FFA_DISTANCES[a.distance].label)}</div><div class="small">${a.count}${a.count===100?"+":""} profil${a.count>1?"s":""}</div></div><button type="button" data-alt-distance="${esc(a.distance)}" style="padding:9px 11px;min-height:40px;white-space:nowrap">Voir ${esc(FFA_DISTANCES[a.distance].label)}</button></div>`).join("");
      box.querySelectorAll("[data-alt-distance]").forEach(btn=>btn.addEventListener("click",()=>{
        const distance=btn.getAttribute("data-alt-distance");
        const distanceBtn=document.querySelector(`[data-distance="${distance}"]`);
        if(distanceBtn) distanceBtn.click();
      }));
      return;
    }
    msg.textContent=found.length+(found.length===100?"+":"")+" profil"+(found.length>1?"s":"")+" trouvé"+(found.length>1?"s":"")+".";'''
if old not in s:
    raise SystemExit('target block not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
