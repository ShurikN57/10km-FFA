// core.js — logique partagée entre app_base.html (desktop) et mobile.html.
// Aucune référence au DOM ici : uniquement du parsing et du matching pur.

function chronoFromSec(sec) {
  sec=Math.round(Number(sec)||0);
  const h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), ss=sec%60;
  return h ? h+"h"+String(m).padStart(2,"0")+"'"+String(ss).padStart(2,"0")+"''"
           : m+"'"+String(ss).padStart(2,"0")+"''";
}
function buildFfaFromCompact(rows){
  return rows.map(r=>({
    full_name:r[0],
    name_key:nameKey(r[0]),
    annee_naissance:r[1]||"",
    sexe:r[2]||"",
    club:r[6]||"",
    pb_sec:r[3],
    pb_chrono:chronoFromSec(r[3]),
    pb_course:r[4]||"",
    pb_date:r[5]||"",
    nb_performances:1,
    source:"",
    athlete_ffa_id:r[7]||"",
    ffa_url:r[7] ? "https://www.athle.fr/athletes/"+r[7]+"/resultats" : ""
  }));
}

function getFfaProfileUrl(p){
  if(!p) return "";
  if(p.ffa_url) return p.ffa_url;
  if(p.athlete_ffa_id) return "https://www.athle.fr/athletes/"+p.athlete_ffa_id+"/resultats";
  return "";
}

function norm(s) {
  return (s ?? "").toString().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .toUpperCase().replace(/[^A-Z0-9]+/g," ").trim().replace(/\s+/g," ");
}
function clean(s) { return (s ?? "").toString().replace(/\s+/g," ").trim(); }
function key(nom, prenom) { return norm(nom) + "|" + norm(prenom); }
function nameKey(s) {
  return norm(s).split(" ").filter(Boolean).sort().join(" ");
}

function secFromTime(s) {
  s = clean(s);
  if(!s) return null;
  if(/ABANDON|DNF|DNS|DISQUAL/i.test(s)) return null;

  let m = s.match(/(?:(\d{1,2})h)?\s*(\d{1,3})[’']\s*(\d{1,2})/);
  if(m) return +(m[1]||0)*3600 + +m[2]*60 + +m[3];

  // H:MM:SS (ex. 1:13:26)
  m = s.match(/^(\d{1,2}):(\d{2}):(\d{2})$/);
  if(m) return +m[1]*3600 + +m[2]*60 + +m[3];

  // MM:SS
  m = s.match(/^(\d{1,3}):(\d{2})$/);
  if(m) return +m[1]*60 + +m[2];

  return null;
}
function fmtDelta(sec) {
  if(sec == null || isNaN(sec)) return "";
  const sign = sec >= 0 ? "+" : "-";
  sec = Math.abs(Math.round(sec));
  const m = Math.floor(sec/60), s=sec%60;
  return sign + (m ? m+"'" : "") + String(s).padStart(2,"0")+"''";
}
function splitFullName(s) {
  s = clean(s);
  const parts=s.split(" ");
  if(parts.length<2) return [s,""];
  let upper=[];
  let i=0;
  for(;i<parts.length;i++) {
    const p=parts[i].replace(/[^A-Za-zÀ-ÿ'-]/g,"");
    if(p && p === p.toUpperCase()) upper.push(parts[i]); else break;
  }
  if(upper.length && i<parts.length) return [upper.join(" "), parts.slice(i).join(" ")];
  return [parts[0], parts.slice(1).join(" ")];
}

// --- Catégories d'âge -> fourchette d'années de naissance plausible ---
// Sert uniquement de garde-fou contre les faux positifs (homonymes d'âges
// très différents) : une fourchette ratée ne bloque jamais un match, elle
// ne fait que le rétrograder en "ambigu" pour vérification manuelle.

function utmbCategoryToYearRange(cat) {
  const c = clean(cat);
  const refYear = new Date().getFullYear();
  // Les catégories se calculent sur l'âge atteint dans l'année civile (pas
  // la date exacte de naissance) : pas de marge nécessaire pour cette
  // incertitude-là. La seule incertitude restante est l'année réelle de la
  // course si elle diffère de l'année en cours — voir la remarque plus bas.
  let m = c.match(/^(\d{2})\s*-\s*(\d{2})$/);
  if(m) {
    const minAge = +m[1], maxAge = +m[2];
    return { min: refYear - maxAge, max: refYear - minAge };
  }
  m = c.match(/^(\d{2})\s*\+$/);
  if(m) {
    const minAge = +m[1];
    return { min: 1900, max: refYear - minAge };
  }
  return null;
}

// Codes catégories FFA (ex. "M1H", "ESH", "SEF", "CAH"...). Table
// approximative (les bornes exactes varient selon les saisons) avec une
// marge de 2 ans ; un code non reconnu renvoie null (aucune vérification,
// jamais de faux "ambigu" pour un code qu'on ne comprend pas).
const FFA_CATEGORY_AGE_TABLE = {
  EA:[0,8], PO:[9,10], BE:[11,12], MI:[13,14], CA:[15,16], JU:[17,18],
  U18:[16,17], U20:[18,19], ES:[19,22], U23:[19,22],
  SE:[23,34],
  M0:[35,39], M1:[40,44], M2:[45,49], M3:[50,54], M4:[55,59],
  M5:[60,64], M6:[65,69], M7:[70,74], M8:[75,79], M9:[80,84], M10:[85,120]
};
const FFA_CATEGORY_VERBOSE = {
  "EVEIL ATHLETIQUE":"EA",
  "POUSSIN":"PO","POUSSINS":"PO",
  "BENJAMIN":"BE","BENJAMINS":"BE",
  "MINIME":"MI","MINIMES":"MI",
  "CADET":"CA","CADETS":"CA",
  "JUNIOR":"JU","JUNIORS":"JU",
  "ESPOIR":"ES","ESPOIRS":"ES",
  "SENIOR":"SE","SENIORS":"SE",
  "MASTERS 0":"M0","MASTERS 1":"M1","MASTERS 2":"M2","MASTERS 3":"M3","MASTERS 4":"M4",
  "MASTERS 5":"M5","MASTERS 6":"M6","MASTERS 7":"M7","MASTERS 8":"M8","MASTERS 9":"M9","MASTERS 10":"M10",
  "VETERAN 0":"M0","VETERAN 1":"M1","VETERAN 2":"M2","VETERAN 3":"M3","VETERAN 4":"M4",
  "VETERAN 5":"M5","VETERAN 6":"M6","VETERAN 7":"M7","VETERAN 8":"M8","VETERAN 9":"M9","VETERAN 10":"M10"
};
function ffaCategoryToYearRange(cat) {
  const refYear = new Date().getFullYear();
  let c = clean(cat);

  // Code compact FFA (ex: "M1H", "SEF"...)
  const compact = c.toUpperCase().match(/^(U\d{1,2}|ES|SE|JU|CA|MI|BE|PO|EA|M\d{1,2})(?=[HF]?$)/);
  if(compact && FFA_CATEGORY_AGE_TABLE[compact[1]]) {
    const [minAge,maxAge] = FFA_CATEGORY_AGE_TABLE[compact[1]];
    return { min: refYear - maxAge, max: refYear - minAge };
  }

  // Libellé complet tel qu'affiché par GoTiming (ex: "7° Masters 0 Homme")
  c = c.replace(/^\d+\s*°?\s*/,"").replace(/\s*(Homme|Femme|Hommes|Femmes)\s*$/i,"").trim();
  const code = FFA_CATEGORY_VERBOSE[norm(c)];
  if(code && FFA_CATEGORY_AGE_TABLE[code]) {
    const [minAge,maxAge] = FFA_CATEGORY_AGE_TABLE[code];
    return { min: refYear - maxAge, max: refYear - minAge };
  }

  return null;
}

function parseCSV(text) {
  text = text.replace(/^\uFEFF/,"");
  const lines = text.split(/\r?\n/).filter(x=>x.trim());
  if(!lines.length) return [];
  const candidates=[";","\t",","];
  let delim=";";
  let best=-1;
  for(const d of candidates) {
    const needle = d === "\t" ? "\t" : d;
    const n = lines[0].split(needle).length - 1;
    if(n>best) {best=n;delim=d;}
  }
  const parseLine = line => {
    let out=[],cur="",q=false;
    for(let i=0;i<line.length;i++) {
      const c=line[i];
      if(c==='"') {
        if(q && line[i+1]==='"') {cur+='"';i++;}
        else q=!q;
      } else if(c===delim && !q) {out.push(cur);cur="";}
      else cur+=c;
    }
    out.push(cur); return out.map(clean);
  };
  const headers=parseLine(lines[0]).map(norm);
  return lines.slice(1).map(l => {
    const vals=parseLine(l), o={};
    headers.forEach((h,i)=>o[h]=vals[i]??"");
    return o;
  });
}
function val(o, names) {
  for(const n of names) {
    const k=norm(n);
    if(o[k] != null && clean(o[k])) return clean(o[k]);
  }
  return "";
}
function rowsToRace(rows) {
  const out=[];
  for(const r of rows) {
    let nom=val(r,["NOM","LAST NAME","LASTNAME"]);
    let prenom=val(r,["PRENOM","PRÉNOM","FIRST NAME","FIRSTNAME"]);
    let full=val(r,["NOM COMPLET","ATHLETE","ATHLÈTE","COUREUR","PARTICIPANT","NAME"]);

    // GoTiming : la colonne "Nom" contient en réalité "NOM Prénom".
    // Si aucune colonne prénom n'existe, on découpe donc la cellule Nom.
    if(nom && !prenom && !full) {
      full = nom;
      [nom,prenom] = splitFullName(full);
    } else if(!nom && full) {
      [nom,prenom] = splitFullName(full);
    }

    const temps=val(r,["TEMPS","TIME","CHRONO","RESULTAT","RÉSULTAT","TEMPS OFFICIEL"]);
    const pos=val(r,["PLACE","POSITION","RANG","CLASSEMENT","POS","PL"]);
    const cat=val(r,["CATEGORIE","CATÉGORIE","CAT"]);
    const annee=val(r,["ANNEE NAISSANCE","ANNÉE NAISSANCE","ANNEE","YEAR","YOB"]);

    if(nom && prenom && temps) out.push({pos,nom,prenom,temps,cat,annee,anneeRange:cat?ffaCategoryToYearRange(cat):null});
  }
  return out;
}

function excelCellText(v) {
  if(v == null) return "";
  if(typeof v === "number") return String(v);
  if(v instanceof Date && !isNaN(v)) return v.toISOString();
  return clean(v);
}
function excelTimeToText(v) {
  if(v == null || v === "") return "";
  if(typeof v === "number") {
    let sec = Math.round(v * 86400);
    if(sec >= 0 && sec <= 6*3600) {
      const h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), ss=sec%60;
      return h ? `${h}h${String(m).padStart(2,"0")}'${String(ss).padStart(2,"0")}''`
               : `${m}'${String(ss).padStart(2,"0")}''`;
    }
  }
  return clean(v);
}
function headerScore(labels) {
  let score=0;
  const joined=labels.join("|");
  if(/NOM|NAME|ATHLETE|ATHLÈTE|COUREUR/.test(joined)) score+=4;
  if(/PRENOM|PRÉNOM|FIRST/.test(joined)) score+=2;
  if(/TEMPS|TIME|CHRONO|RESULTAT|RÉSULTAT/.test(joined)) score+=4;
  if(/PLACE|POS|POSITION|RANG|CLASSEMENT/.test(joined)) score+=2;
  if(/DOSSARD|BIB/.test(joined)) score+=1;
  return score;
}
function parseExcelArray(rows) {
  if(!rows || !rows.length) return [];
  let bestHeader=-1, bestScore=-1, headers=[];
  for(let i=0;i<Math.min(rows.length,50);i++) {
    const labels=(rows[i]||[]).map(v=>norm(excelCellText(v)));
    const sc=headerScore(labels);
    if(sc>bestScore) { bestScore=sc; bestHeader=i; headers=labels; }
  }
  if(bestHeader<0 || bestScore<6) return [];

  const out=[];
  for(const rr of rows.slice(bestHeader+1)) {
    if(!rr || !rr.some(v=>clean(v)!=="")) continue;
    const o={};
    headers.forEach((h,i)=>{ if(h) o[h]=rr[i] ?? ""; });

    let nom=val(o,["NOM","LAST NAME","LASTNAME"]);
    let prenom=val(o,["PRENOM","PRÉNOM","FIRST NAME","FIRSTNAME"]);
    let full=val(o,["NOM COMPLET","ATHLETE","ATHLÈTE","COUREUR","PARTICIPANT","NAME"]);
    if(!nom && full) [nom,prenom]=splitFullName(full);

    let rawTime = null;
    for(const alias of ["TEMPS","TIME","CHRONO","RESULTAT","RÉSULTAT","TEMPS OFFICIEL","OFFICIEL"]) {
      const k=norm(alias);
      if(o[k]!=null && o[k]!=="") { rawTime=o[k]; break; }
    }
    const temps=excelTimeToText(rawTime);
    const pos=val(o,["PLACE","POSITION","RANG","CLASSEMENT","POS"]);
    const cat=val(o,["CATEGORIE","CATÉGORIE","CAT"]);
    const annee=val(o,["ANNEE NAISSANCE","ANNÉE NAISSANCE","ANNEE","YEAR","YOB"]);

    if(nom && (prenom || full) && temps) out.push({pos,nom,prenom,temps,cat,annee,anneeRange:cat?ffaCategoryToYearRange(cat):null});
  }
  return out;
}
async function parseExcelFile(file) {
  // GoTiming exporte actuellement certains ".xls" sous forme de HTML
  // (table id="tabres") avec une extension Excel.
  // On détecte d'abord ce cas avant d'utiliser SheetJS.
  const buf = await file.arrayBuffer();

  let text = "";
  try {
    text = new TextDecoder("utf-8").decode(buf);
  } catch(e) {}

  const head = text.slice(0, 4096).trim().toLowerCase();
  if(head.startsWith("<table") || head.startsWith("<html") ||
     head.includes('<table id="tabres"') || head.includes("<thead")) {
    const parsed = parseHTML(text);
    if(parsed.length) return parsed;
  }

  // Vrai fichier XLS/XLSX : fallback SheetJS.
  if(typeof XLSX === "undefined") {
    throw new Error("Ce fichier semble être un vrai Excel mais la bibliothèque XLSX n'est pas chargée.");
  }

  const wb = XLSX.read(buf, {type:"array", cellDates:true});
  let best=[];
  for(const sheetName of wb.SheetNames) {
    const ws=wb.Sheets[sheetName];
    const rows=XLSX.utils.sheet_to_json(ws,{header:1,raw:true,defval:""});
    const parsed=parseExcelArray(rows);
    if(parsed.length>best.length) best=parsed;
  }
  return best;
}

function splitUtmbName(full) {
  full=clean(full);
  const parts=full.split(/\s+/).filter(Boolean);
  if(parts.length<2) return [full,""];

  let i=parts.length-1;
  const surname=[];
  for(;i>=0;i--) {
    const p=parts[i].replace(/[^A-Za-zÀ-ÿ'-]/g,"");
    if(p && p===p.toUpperCase()) surname.unshift(parts[i]);
    else break;
  }
  if(surname.length && i>=0) return [surname.join(" "), parts.slice(0,i+1).join(" ")];

  return [parts[parts.length-1], parts.slice(0,-1).join(" ")];
}
function parseUtmbJSON(text) {
  let d;
  try { d=JSON.parse(text); } catch(e) { return []; }
  const arr = Array.isArray(d.results) ? d.results : [];
  return arr.map(x=>{
    const [nom,prenom]=splitUtmbName(x.name||"");
    return {
      pos:String(x.rank||""),
      nom, prenom,
      temps:String(x.time||""),
      cat:String(x.age_category||""),
      annee:"",
      anneeRange:utmbCategoryToYearRange(x.age_category),
      source:"UTMB",
      nationality:String(x.nationality||""),
      gender:String(x.gender||""),
      runner_url:String(x.runner_url||""),
      runner_id:String(x.runner_id||""),
      race:String(x.race||""),
      race_date:String(x.race_date||""),
      distance:String(x.distance||"")
    };
  }).filter(x=>x.nom && x.temps);
}
function parseHTML(text) {
  const doc = new DOMParser().parseFromString(text,"text/html");
  const tables=[...doc.querySelectorAll("table")];
  let best=[];

  for(const table of tables) {
    const trs=[...table.querySelectorAll("tr")];
    if(trs.length<2) continue;

    let headerRow=-1, headers=[];
    for(let i=0;i<Math.min(20,trs.length);i++) {
      const cells=[...trs[i].querySelectorAll("th,td")].map(c=>norm(c.textContent));
      const joined=cells.join("|");
      if(/NOM|ATHLETE|ATHLÈTE|COUREUR|NAME/.test(joined) &&
         /TEMPS|CHRONO|RESULTAT|RÉSULTAT|TIME/.test(joined)) {
        headerRow=i;
        headers=cells;
        break;
      }
    }
    if(headerRow<0) continue;

    const objs=[];
    for(const tr of trs.slice(headerRow+1)) {
      // Important : enfants directs uniquement, pour éviter les sous-tableaux.
      const vals=[...tr.children]
        .filter(c=>c.tagName==="TD" || c.tagName==="TH")
        .map(c=>clean(c.textContent));

      if(!vals.length) continue;
      const o={};
      headers.forEach((h,i)=>o[h]=vals[i]??"");
      objs.push(o);
    }

    const parsed=rowsToRace(objs).filter(r=>{
      const t=norm(r.temps);
      return t && !/ABANDON|DNF|DNS|DISQUAL/.test(t);
    });

    if(parsed.length>best.length) best=parsed;
  }
  return best;
}

function parseUtmbPastedText(text) {
  const rawLines = text
    .split(/\r?\n/)
    .map(x=>x.trim())
    .filter(Boolean);

  const headerWords = new Set([
    "CLT","TEMPS","NOM","NATIONALITÉ","NATIONALITE","GENRE",
    "CATÉGORIE D'ÂGE","CATEGORIE D'AGE","SCORE"
  ]);

  const lines = rawLines.filter(x=>!headerWords.has(norm(x)));
  const out=[];

  for(let i=0;i<lines.length;i++) {
    if(!/^\d+$/.test(lines[i])) continue;

    const rank=lines[i];
    const time=lines[i+1] || "";
    if(!/^\d{1,2}:\d{2}:\d{2}$/.test(time)) continue;

    let full=lines[i+2] || "";
    let runner_url="", runner_id="";

    const md=full.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if(md) {
      full=md[1].trim();
      runner_url=md[2].trim();
    }

    let offset=3;
    if(!runner_url && /^https?:\/\/(?:www\.)?utmb\.world\/.+\/runner\//i.test(lines[i+3]||"")) {
      runner_url=lines[i+3];
      offset=4;
    }

    const im=runner_url.match(/\/runner\/(\d+)/);
    if(im) runner_id=im[1];

    const nationality=lines[i+offset] || "";
    const gender=lines[i+offset+1] || "";
    const age_category=lines[i+offset+2] || "";
    const score=lines[i+offset+3] || "";

    if(!full || !/^(HOMME|FEMME|MALE|FEMALE)$/i.test(gender)) continue;

    const [nom,prenom]=splitUtmbName(full);

    out.push({
      pos:rank,
      nom,
      prenom,
      temps:time,
      cat:age_category,
      annee:"",
      anneeRange:utmbCategoryToYearRange(age_category),
      source:"UTMB",
      nationality,
      gender,
      runner_url,
      runner_id,
      score,
      full_name_utmb:full
    });

    i += offset + 3;
  }
  return out;
}
function parsePlainText(text) {
  const lines=text.split(/\r?\n/).map(clean).filter(Boolean);
  const out=[];
  for(const line of lines) {
    const tm=line.match(/(?:(\d{1,2})h)?\s*\d{1,3}[’']\s*\d{1,2}|(?:(\d{1,2}):)?\d{1,2}:\d{2}/);
    if(!tm) continue;
    const temps=tm[0];
    const before=clean(line.slice(0,tm.index));
    const after=clean(line.slice(tm.index+tm[0].length));
    const parts=before.split(/\t|\s{2,}/).filter(Boolean);
    let name=parts.length?parts[parts.length-1]:before;
    const posMatch=before.match(/^(\d+)\.?\s+/);
    const pos=posMatch?posMatch[1]:"";
    name=name.replace(/^\d+\.?\s+/,"");
    const [nom,prenom]=splitFullName(name);
    // Notre propre format (raccourci mobile) ajoute le code catégorie FFA
    // après le temps, ex: "12  DUPONT Jean  0:42:12  M1H". Reconnu ici s'il
    // matche un vrai code FFA ; sinon ignoré (pas de faux positif).
    const cat = after || "";
    if(nom && prenom) out.push({pos,nom,prenom,temps,cat,annee:"",anneeRange:cat?ffaCategoryToYearRange(cat):null});
  }
  return out;
}

function preferFfaProfile(a,b){
  const pa=Number(a?.pb_sec ?? Infinity), pb=Number(b?.pb_sec ?? Infinity);
  if(pa!==pb) return pa-pb;
  const ia=a?.athlete_ffa_id ? 1 : 0, ib=b?.athlete_ffa_id ? 1 : 0;
  if(ia!==ib) return ib-ia;
  const ya=a?.annee_naissance ? 1 : 0, yb=b?.annee_naissance ? 1 : 0;
  if(ya!==yb) return yb-ya;
  const ua=getFfaProfileUrl(a) ? 1 : 0, ub=getFfaProfileUrl(b) ? 1 : 0;
  return ub-ua;
}

function buildIndex(ffa) {
  const map = new Map();
  for(const p of ffa) {
    const nk = p.name_key || nameKey(p.full_name || ((p.nom||"")+" "+(p.prenom||"")));
    if(!nk) continue;
    if(!map.has(nk)) map.set(nk, []);
    map.get(nk).push(p);
  }
  return map;
}

// Fonction pure : prend le classement et la base FFA, renvoie le résultat
// complet (statut, profil retenu, écart...). Ni l'une ni l'autre version
// (desktop/mobile) ne doit réimplémenter cette logique.
function computeResults(race, ffa) {
  const idx = buildIndex(ffa);
  return race.map(r => {
    const nk = nameKey((r.nom||"")+" "+(r.prenom||""));
    let arr = idx.get(nk) || [];
    let status = "none", p = null, matchDetail = "";

    if(arr.length === 1) {
      p = arr[0];
      status = "exact";
      matchDetail = p.athlete_ffa_id ? "ID FFA disponible" : "Nom unique";
    } else if(arr.length > 1) {
      const raceYear = String(r.annee||"").trim();

      if(raceYear) {
        const sameYear = arr.filter(x => String(x.annee_naissance||"").trim() === raceYear);

        if(sameYear.length === 1) {
          p = sameYear[0];
          status = "exact";
          matchDetail = p.athlete_ffa_id ? "Nom + année + ID FFA" : "Nom + année";
        } else if(sameYear.length > 1) {
          const ids = [...new Set(sameYear.map(x=>x.athlete_ffa_id).filter(Boolean))];
          if(ids.length === 1) {
            p = sameYear.slice().sort(preferFfaProfile)[0];
            status = "exact";
            matchDetail = "Nom + année + même ID FFA";
          } else {
            status = "ambiguous";
            matchDetail = "Plusieurs homonymes même année";
          }
        } else {
          status = "ambiguous";
          matchDetail = "Nom trouvé mais année incompatible";
        }
      } else {
        const years = [...new Set(arr.map(x=>String(x.annee_naissance||"").trim()).filter(Boolean))];
        const ids = [...new Set(arr.map(x=>x.athlete_ffa_id).filter(Boolean))];

        if(ids.length === 1 && ids[0]) {
          p = arr.slice().sort(preferFfaProfile)[0];
          status = "exact";
          matchDetail = "Même ID FFA";
        } else if(years.length <= 1) {
          p = arr.slice().sort(preferFfaProfile)[0];
          status = "exact";
          matchDetail = "Nom unique dans une même année";
        } else {
          status = "ambiguous";
          matchDetail = "Homonymes : année requise";
        }
      }
    }

    // Garde-fou : la fourchette d'âge déduite de la catégorie (UTMB ou FFA)
    // s'applique quelle que soit la méthode de matching ci-dessus, y compris
    // le cas "nom unique" qui autrement n'est jamais vérifié.
    if(p && r.anneeRange) {
      const by = Number(p.annee_naissance);
      if(by && (by < r.anneeRange.min || by > r.anneeRange.max)) {
        if(status === "exact") {
          status = "ambiguous";
          matchDetail = "Âge FFA (" + p.annee_naissance + ") incompatible avec la catégorie (" + (r.cat||"") + ")";
        } else if(matchDetail) {
          matchDetail += " — âge incompatible avec la catégorie";
        }
      }
    }

    const raceSec = secFromTime(r.temps);
    const pbSec = p ? Number(p.pb_sec) : null;
    return {
      ...r, status, p, matchDetail, raceSec, pbSec,
      delta:(raceSec!=null && pbSec!=null) ? raceSec-pbSec : null
    };
  });
}

function esc(s) {
  return (s??"").toString().replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function exportResultCSV(result, filename) {
  const headers=["position","nom","prenom","temps_course","pb_10km_ffa","ecart_sec","ecart","course_pb","date_pb","club","match"];
  const lines=[headers.join(";")];
  for(const x of result) {
    const p=x.p||{};
    const vals=[x.pos,x.nom,x.prenom,x.temps,p.pb_chrono||"",x.delta??"",fmtDelta(x.delta),p.pb_course||"",p.pb_date||"",p.club||"",x.status];
    lines.push(vals.map(v=>'"'+String(v??"").replace(/"/g,'""')+'"').join(";"));
  }
  const blob=new Blob(["\ufeff"+lines.join("\r\n")],{type:"text/csv;charset=utf-8"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download=filename||"comparaison_ffa_10km.csv"; a.click();
  URL.revokeObjectURL(a.href);
}
