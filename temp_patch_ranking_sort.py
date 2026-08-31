from pathlib import Path

# Patch Worker
p=Path('cloudflare-prototype/worker.js')
s=p.read_text(encoding='utf-8')
old="""      const page = Math.max(1, Number(url.searchParams.get('page') || 1));
      const pageSize = 100;
      const offset = (page - 1) * pageSize;

      const plainGeneral = !sex && !category && !year && !q &&
"""
new="""      const page = Math.max(1, Number(url.searchParams.get('page') || 1));
      const pageSize = 100;
      const offset = (page - 1) * pageSize;
      const sortRaw = String(url.searchParams.get('sort') || 'rank').toLowerCase();
      const sort = ['rank','name','time'].includes(sortRaw) ? sortRaw : 'rank';
      const dir = String(url.searchParams.get('dir') || 'asc').toLowerCase() === 'desc' ? 'DESC' : 'ASC';

      const plainGeneral = !sex && !category && !year && !q &&
"""
assert old in s
s=s.replace(old,new,1)

old="""      if (plainGeneral) {
        const [rowsRes, statsRes] = await env.DB.batch([
          env.DB.prepare(`
            SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,r.rank
            FROM athlete_general_rank r
            JOIN athletes a ON a.id = r.athlete_id
            WHERE r.distance = ?
            ORDER BY r.display_order ASC
            LIMIT ? OFFSET ?
          `).bind(distance, pageSize, offset),
          env.DB.prepare('SELECT total FROM ffa_distance_stats WHERE distance = ?').bind(distance)
        ]);
"""
new="""      if (plainGeneral) {
        const generalOrder = sort === 'name'
          ? `a.full_name ${dir}, a.pb_sec ASC, a.id ASC`
          : sort === 'time'
            ? `a.pb_sec ${dir}, a.full_name ASC, a.id ASC`
            : `r.rank ${dir}, a.pb_sec ${dir}, a.full_name ASC, a.id ASC`;
        const [rowsRes, statsRes] = await env.DB.batch([
          env.DB.prepare(`
            SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,r.rank
            FROM athlete_general_rank r
            JOIN athletes a ON a.id = r.athlete_id
            WHERE r.distance = ?
            ORDER BY ${generalOrder}
            LIMIT ? OFFSET ?
          `).bind(distance, pageSize, offset),
          env.DB.prepare('SELECT total FROM ffa_distance_stats WHERE distance = ?').bind(distance)
        ]);
"""
assert old in s
s=s.replace(old,new,1)

old="""      const finalWhere = where.join(' AND ');
      const rowsSql = `
        SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
               ${rankExpr} AS rank
        FROM athletes a
        JOIN athlete_search_rank sr ON sr.athlete_id = a.id
        LEFT JOIN athlete_rank_year yr ON yr.athlete_id = a.id
        LEFT JOIN athlete_rank_cat_before cb ON cb.athlete_id = a.id
        LEFT JOIN athlete_rank_cat_after ca ON ca.athlete_id = a.id
        WHERE ${finalWhere}
        ORDER BY rank ASC, a.pb_sec ASC, a.full_name ASC
        LIMIT ? OFFSET ?`;
"""
new="""      const finalWhere = where.join(' AND ');
      const filteredOrder = sort === 'name'
        ? `a.full_name ${dir}, a.pb_sec ASC, a.id ASC`
        : sort === 'time'
          ? `a.pb_sec ${dir}, a.full_name ASC, a.id ASC`
          : `rank ${dir}, a.pb_sec ${dir}, a.full_name ASC, a.id ASC`;
      const rowsSql = `
        SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
               ${rankExpr} AS rank
        FROM athletes a
        JOIN athlete_search_rank sr ON sr.athlete_id = a.id
        LEFT JOIN athlete_rank_year yr ON yr.athlete_id = a.id
        LEFT JOIN athlete_rank_cat_before cb ON cb.athlete_id = a.id
        LEFT JOIN athlete_rank_cat_after ca ON ca.athlete_id = a.id
        WHERE ${finalWhere}
        ORDER BY ${filteredOrder}
        LIMIT ? OFFSET ?`;
"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Patch mobile
p=Path('mobile.html')
s=p.read_text(encoding='utf-8')
old="""let ffaRankingToken=0;
let ffaFullTimer=null;
async function renderFullFfaRanking(resetPage=false){
"""
new="""let ffaRankingToken=0;
let ffaFullTimer=null;
let ffaFullSort='rank';
let ffaFullSortDir='asc';
function ffaFullSortHeader(){
  const cols=[['rank','Position'],['name','Nom'],['time','Temps']];
  return `<div style="display:grid;grid-template-columns:68px minmax(0,1fr) 72px;gap:6px;align-items:center;padding:7px 10px;border-bottom:1px solid var(--line);background:#141922">${cols.map(([key,label])=>{
    const active=ffaFullSort===key;
    const arrow=active?(ffaFullSortDir==='asc'?'▲':'▼'):'↕';
    const align=key==='rank'?'center':key==='time'?'right':'left';
    return `<button type="button" data-ffa-full-sort="${key}" style="min-height:34px;padding:5px 3px;border:0;background:transparent;color:${active?'var(--accent)':'#c8d0dc'};font-size:11px;text-align:${align};box-shadow:none">${label} ${arrow}</button>`;
  }).join('')}</div>`;
}
function bindFfaFullSortButtons(){
  document.querySelectorAll('[data-ffa-full-sort]').forEach(btn=>btn.addEventListener('click',()=>{
    const key=btn.getAttribute('data-ffa-full-sort');
    if(ffaFullSort===key) ffaFullSortDir=ffaFullSortDir==='asc'?'desc':'asc';
    else { ffaFullSort=key; ffaFullSortDir='asc'; }
    renderFullFfaRanking(true);
  }));
}
async function renderFullFfaRanking(resetPage=false){
"""
assert old in s
s=s.replace(old,new,1)

old="""  const params=new URLSearchParams({distance:currentDistance,page:String(ffaFullPage+1)});
"""
new="""  const params=new URLSearchParams({distance:currentDistance,page:String(ffaFullPage+1),sort:ffaFullSort,dir:ffaFullSortDir});
"""
assert old in s
s=s.replace(old,new,1)

old="""    box.innerHTML=rows.length ? rows.map(r=>{
"""
new="""    const sortHeader=ffaFullSortHeader();
    box.innerHTML=sortHeader+(rows.length ? rows.map(r=>{
"""
assert old in s
s=s.replace(old,new,1)
old="""    }).join(\"\") : `<div class=\"msg\" style=\"padding:12px\">Aucun athlète avec ces filtres.</div>`;
    $(\"ffaFullPrev\").disabled=ffaFullPage<=0;
"""
new="""    }).join(\"\") : `<div class=\"msg\" style=\"padding:12px\">Aucun athlète avec ces filtres.</div>`);
    bindFfaFullSortButtons();
    $(\"ffaFullPrev\").disabled=ffaFullPage<=0;
"""
assert old in s
s=s.replace(old,new,1)

old="""  $(\"ffaFullMinPb\").value=\"\";
  $(\"ffaFullMaxPb\").value=\"\";
  renderFullFfaRanking(true);
"""
new="""  $(\"ffaFullMinPb\").value=\"\";
  $(\"ffaFullMaxPb\").value=\"\";
  ffaFullSort='rank';
  ffaFullSortDir='asc';
  renderFullFfaRanking(true);
"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
