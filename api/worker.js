const ALLOWED_ORIGIN = 'https://shurikn57.github.io';

function corsHeaders(request) {
  const origin = request.headers.get('Origin');
  return {
    'Access-Control-Allow-Origin': origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
    'Cache-Control': 'no-store'
  };
}

function json(request, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders(request) }
  });
}

function normalizeDistance(value) {
  return ['5k','10k','semi','marathon'].includes(value) ? value : null;
}

function normalizeName(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function ftsQueryFromName(value) {
  const q = normalizeName(value);
  const tokens = q.split(' ').filter((t) => t.length >= 3);
  if (!tokens.length) return '';
  return tokens.map((t) => `"${t.replace(/"/g, '""')}"`).join(' AND ');
}

// Catégories FFA : l'âge se calcule sur l'année de fin de saison.
// La saison N commence le 1er septembre N-1 (heure de Paris).
const CATEGORY_AGES = [
  ['CA', 16, 17], ['JU', 18, 19], ['ES', 20, 22], ['SE', 23, 34],
  ['M0', 35, 39], ['M1', 40, 44], ['M2', 45, 49], ['M3', 50, 54],
  ['M4', 55, 59], ['M5', 60, 64], ['M6', 65, 69], ['M7', 70, 74],
  ['M8', 75, 79], ['M9', 80, 84], ['M10', 85, null]
];

// Les rangs par catégorie sont précalculés dans D1 pour deux saisons :
// rank_cat_before_sep = saison 2026, rank_cat_after_sep = saison 2027.
// À chaque nouvelle saison, il faut recalculer ces colonnes dans D1.
const RANK_CAT_AFTER_SEASON = 2027;

function parisDateParts(date = new Date()) {
  const [y, m] = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit'
  }).format(date).split('-').map(Number);
  return { year: y, month: m };
}

function currentSeasonYear(date = new Date()) {
  const { year, month } = parisDateParts(date);
  return month >= 9 ? year + 1 : year;
}

function useAfterSepRankColumns() {
  return currentSeasonYear() >= RANK_CAT_AFTER_SEASON;
}

// Saison utilisée pour les catégories : la saison en cours, mais jamais au-delà
// de la dernière saison dont les rangs sont précalculés dans D1. Sinon, à partir
// du 1er septembre 2027, les tranches d'âge avanceraient alors que les rangs
// resteraient ceux de 2027. Après recalcul des rangs, augmenter
// RANK_CAT_AFTER_SEASON (et FFA_LATEST_RANKED_SEASON dans core.js).
function categorySeasonYear() {
  return Math.min(currentSeasonYear(), RANK_CAT_AFTER_SEASON);
}

function categoryYears(category, seasonYear = categorySeasonYear()) {
  const cat = String(category || '').toUpperCase();
  const entry = CATEGORY_AGES.find(([code]) => code === cat);
  if (!entry) return null;
  const [, minAge, maxAge] = entry;
  return [maxAge == null ? null : seasonYear - maxAge, seasonYear - minAge];
}

function categoryBounds(birthYear, seasonYear = categorySeasonYear()) {
  const y = Number(birthYear);
  if (!Number.isFinite(y) || y <= 0) return null;
  const age = seasonYear - y;
  for (const [code, minAge, maxAge] of CATEGORY_AGES) {
    if (age >= minAge && (maxAge == null || age <= maxAge)) {
      return [maxAge == null ? null : seasonYear - maxAge, seasonYear - minAge, code];
    }
  }
  return null;
}

// Première saison des bilans collectés.
const FIRST_SEASON = 2024;
const MAX_PAGE = 10000;

// Saison FFA d'une perf (pb_date au format JJ/MM/AA) : la saison N va du
// 01/09/N-1 au 31/08/N. Doit rester identique à l'expression des index
// idx_athletes_season_pb et idx_athletes_sex_season_pb (api/schema.sql).
const SEASON_SQL = '(2000 + CAST(substr(a.pb_date, 7, 2) AS INTEGER) + (CAST(substr(a.pb_date, 4, 2) AS INTEGER) >= 9))';
// Part de la distance au-delà de laquelle une catégorie est parcourue par temps
// (mesuré sur la base complète : gain jusqu'à ×90 au-dessus, perte en dessous).
const LARGE_CATEGORY_SHARE = 0.04;

// Cache des réponses en lecture. Les données ne changent qu'à chaque réimport
// des bilans : une même page n'a pas besoin de relire la base à chaque fois.
// Incrémenter CACHE_VERSION après un réimport pour invalider tout le cache.
const CACHE_VERSION = 2;
const CACHEABLE_PATHS = new Set(['/search', '/ranking', '/ranking-options']);
const EDGE_TTL_SECONDS = 3600;   // cache Cloudflare
const BROWSER_TTL_SECONDS = 300; // cache du navigateur

function cacheKey(url) {
  const params = [...url.searchParams.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  const key = new URL(url.origin + url.pathname);
  for (const [k, v] of params) key.searchParams.append(k, v);
  key.searchParams.set('__v', String(CACHE_VERSION));
  return new Request(key.toString(), { method: 'GET' });
}

async function cachedHandle(request, env, ctx) {
  const url = new URL(request.url);
  const cache = request.method === 'GET' && CACHEABLE_PATHS.has(url.pathname) && typeof caches !== 'undefined'
    ? caches.default : null;
  if (!cache) return handle(request, env);

  const key = cacheKey(url);
  const hit = await cache.match(key);
  if (hit) return hit;

  const res = await handle(request, env);
  if (res.status !== 200) return res;
  res.headers.set('Cache-Control', `public, max-age=${BROWSER_TTL_SECONDS}, s-maxage=${EDGE_TTL_SECONDS}`);
  const put = cache.put(key, res.clone()).catch(() => {});
  if (ctx && ctx.waitUntil) ctx.waitUntil(put);
  return res;
}

export default {
  async fetch(request, env, ctx) {
    try {
      if (request.method !== 'OPTIONS' && env.RATE_LIMITER) {
        const key = request.headers.get('CF-Connecting-IP') || 'unknown';
        const { success } = await env.RATE_LIMITER.limit({ key });
        if (!success) {
          const res = json(request, { error: 'rate_limited' }, 429);
          res.headers.set('Retry-After', '60');
          return res;
        }
      }
      return await cachedHandle(request, env, ctx);
    } catch (err) {
      console.error('Unhandled error', err && err.stack ? err.stack : err);
      return json(request, { error: 'internal_error' }, 500);
    }
  }
};

async function handle(request, env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders(request) });

    const url = new URL(request.url);
    if (url.pathname === '/match' && request.method === 'POST') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);

      let body;
      try { body = await request.json(); }
      catch { return json(request, { error: 'invalid_json' }, 400); }

      const names = [...new Set((Array.isArray(body?.names) ? body.names : [])
        .map(normalizeName).filter((name) => name.length >= 3))].slice(0, 1000);
      if (!names.length) return json(request, { rows: [] });

      const statements = [];
      for (let i = 0; i < names.length; i += 80) {
        const chunk = names.slice(i, i + 80);
        const placeholders = chunk.map(() => '?').join(',');
        statements.push(env.DB.prepare(`
          SELECT full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id
          FROM athletes
          WHERE distance = ? AND name_key IN (${placeholders})
        `).bind(distance, ...chunk));
      }

      const batches = await env.DB.batch(statements);
      const rows = batches.flatMap((batch) => batch.results || []);
      return json(request, { rows });
    }

    if (request.method !== 'GET') return json(request, { error: 'method_not_allowed' }, 405);

    if (url.pathname === '/health') {
      const row = await env.DB.prepare('SELECT COUNT(*) AS n FROM athletes').first();
      return json(request, { ok: true, athletes: Number(row?.n || 0) });
    }

    if (url.pathname === '/search') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      const q = normalizeName(url.searchParams.get('q'));
      const modeRaw = String(url.searchParams.get('mode') || 'sex');
      const mode = ['general','sex','category'].includes(modeRaw) ? modeRaw : 'sex';
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);
      if (q.length < 3) return json(request, { rows: [] });

      const ftsQuery = ftsQueryFromName(q);
      if (!ftsQuery) return json(request, { rows: [] });
      const afterSep2026 = useAfterSepRankColumns();
      const rankColumn = mode === 'general'
        ? 'rank_general'
        : mode === 'category'
          ? (afterSep2026 ? 'rank_cat_after_sep' : 'rank_cat_before_sep')
          : 'rank_sex';

      const stmt = env.DB.prepare(`
        SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
               sr.${rankColumn} AS rank
        FROM athlete_fts
        JOIN athletes a ON a.id = athlete_fts.rowid
        JOIN athlete_search_rank sr ON sr.athlete_id = a.id
        WHERE athlete_fts MATCH ? AND a.distance = ?
        ORDER BY CASE WHEN a.name_key = ? THEN 0 ELSE 1 END, a.birth_year ASC, a.full_name ASC
        LIMIT 100
      `).bind(ftsQuery, distance, q);
      const res = await stmt.all();
      const rows = (res.results || []).map((row) => {
        const bounds = mode === 'category' ? categoryBounds(row.birth_year) : null;
        return { ...row, rank: Number(row.rank || 0), category: bounds?.[2] || '' };
      });
      return json(request, { rows });
    }

    if (url.pathname === '/ranking-options') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);
      const res = await env.DB.prepare(`
        SELECT league,department,club,race_year
        FROM ffa_scope_options
        WHERE distance = ?
        ORDER BY league,department,club,race_year
      `).bind(distance).all();
      return json(request, { rows: res.results || [] });
    }

    if (url.pathname === '/ranking') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);

      const sexRaw = String(url.searchParams.get('sex') || '').toUpperCase();
      const sex = sexRaw === 'M' || sexRaw === 'F' ? sexRaw : '';
      const category = String(url.searchParams.get('category') || '').toUpperCase();
      const yearRaw = String(url.searchParams.get('year') || '').trim();
      const year = /^\d{4}$/.test(yearRaw) ? Number(yearRaw) : 0;
      const leagueRaw = String(url.searchParams.get('league') || '').trim().toUpperCase();
      const league = /^[A-Z0-9-]{1,5}$/.test(leagueRaw) ? leagueRaw : '';
      const departmentRaw = String(url.searchParams.get('department') || '').trim().toUpperCase();
      const department = /^[A-Z0-9-]{1,5}$/.test(departmentRaw) ? departmentRaw : '';
      const club = String(url.searchParams.get('club') || '').trim().slice(0, 180);
      const seasonYearRaw = String(url.searchParams.get('seasonYear') || '').trim();
      // Saisons disponibles : de la première saison collectée à la saison en cours.
      const seasonYear = /^\d{4}$/.test(seasonYearRaw) && Number(seasonYearRaw) >= FIRST_SEASON && Number(seasonYearRaw) <= currentSeasonYear()
        ? Number(seasonYearRaw) : 0;
      const minPb = Number(url.searchParams.get('minPb') || 0);
      const maxPb = Number(url.searchParams.get('maxPb') || 0);
      const q = normalizeName(url.searchParams.get('q'));
      const frenchOnly = url.searchParams.get('french') === '1';
      const ftsQuery = q.length >= 3 ? ftsQueryFromName(q) : '';
      const pageRaw = Number.parseInt(url.searchParams.get('page') || '1', 10);
      const page = Number.isFinite(pageRaw) ? Math.min(Math.max(1, pageRaw), MAX_PAGE) : 1;
      const pageSize = 100;
      const offset = (page - 1) * pageSize;
      const sortRaw = String(url.searchParams.get('sort') || 'rank').toLowerCase();
      const sort = ['rank','name','time'].includes(sortRaw) ? sortRaw : 'rank';
      const dir = String(url.searchParams.get('dir') || 'asc').toLowerCase() === 'desc' ? 'DESC' : 'ASC';
      const scopedRanking = Boolean(league || department || club || seasonYear);

      const plainGeneral = !scopedRanking && !sex && !category && !year && !q && !frenchOnly &&
        !(Number.isFinite(minPb) && minPb > 0) &&
        !(Number.isFinite(maxPb) && maxPb > 0);

      const plainFrench = !scopedRanking && frenchOnly && !sex && !category && !year && !q &&
        !(Number.isFinite(minPb) && minPb > 0) &&
        !(Number.isFinite(maxPb) && maxPb > 0);

      if (plainGeneral) {
        // Le rang suit le temps : trier par temps revient à trier par rang, ce qui
        // parcourt l'index (distance, rank) au lieu de trier toute la distance.
        // Le tri par nom part de l'index (distance, full_name) d'athletes.
        const rowsSql = sort === 'name'
          ? `SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,r.rank
             FROM athletes a
             JOIN athlete_general_rank r ON r.athlete_id = a.id
             WHERE a.distance = ?
             ORDER BY a.full_name ${dir}, a.pb_sec ASC, a.id ASC
             LIMIT ? OFFSET ?`
          : `SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,r.rank
             FROM athlete_general_rank r
             JOIN athletes a ON a.id = r.athlete_id
             WHERE r.distance = ?
             ORDER BY r.rank ${dir}, a.pb_sec ${dir}, a.full_name ASC, a.id ASC
             LIMIT ? OFFSET ?`;
        const [rowsRes, statsRes] = await env.DB.batch([
          env.DB.prepare(rowsSql).bind(distance, pageSize, offset),
          env.DB.prepare('SELECT total FROM ffa_distance_stats WHERE distance = ?').bind(distance)
        ]);
        const total = Number(statsRes?.results?.[0]?.total || 0);
        const pages = Math.max(1, Math.ceil(total / pageSize));
        return json(request, {
          page: Math.min(page, pages),
          pageSize,
          total,
          pages,
          rows: rowsRes?.results || []
        });
      }

      if (plainFrench) {
        const rowsSql = sort === 'name'
          ? `SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
                    fr.rank_general AS rank
             FROM athletes a
             JOIN athlete_french_rank fr ON fr.athlete_id = a.id
             WHERE a.distance = ?
             ORDER BY a.full_name ${dir}, a.pb_sec ASC, a.id ASC
             LIMIT ? OFFSET ?`
          : `SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
                    fr.rank_general AS rank
             FROM athlete_french_rank fr
             JOIN athletes a ON a.id = fr.athlete_id
             WHERE fr.distance = ?
             ORDER BY fr.rank_general ${dir}, a.pb_sec ${dir}, a.full_name ASC, a.id ASC
             LIMIT ? OFFSET ?`;
        const [rowsRes, statsRes] = await env.DB.batch([
          env.DB.prepare(rowsSql).bind(distance, pageSize, offset),
          env.DB.prepare('SELECT total FROM ffa_french_stats WHERE distance = ?').bind(distance)
        ]);
        const total = Number(statsRes?.results?.[0]?.total || 0);
        const pages = Math.max(1, Math.ceil(total / pageSize));
        return json(request, {
          page: Math.min(page, pages),
          pageSize,
          total,
          pages,
          rows: rowsRes?.results || []
        });
      }

      if (scopedRanking || frenchOnly) {
        const needsScopeTable = Boolean(league || department);
        const scopeWhere = ['a.distance = ?'];
        const scopeBinds = [distance];
        if (sex) { scopeWhere.push('a.sex = ?'); scopeBinds.push(sex); }
        if (category) {
          const bounds = categoryYears(category);
          if (!bounds) return json(request, { error: 'invalid_category' }, 400);
          const [minYear, maxYear] = bounds;
          if (minYear == null) { scopeWhere.push('a.birth_year <= ?'); scopeBinds.push(maxYear); }
          else { scopeWhere.push('a.birth_year BETWEEN ? AND ?'); scopeBinds.push(minYear, maxYear); }
        }
        if (year) { scopeWhere.push('a.birth_year = ?'); scopeBinds.push(year); }
        // sc.distance permet d'utiliser les index (distance, league|department) d'athlete_scope.
        if (needsScopeTable) { scopeWhere.push('sc.distance = ?'); scopeBinds.push(distance); }
        if (league) { scopeWhere.push('sc.league = ?'); scopeBinds.push(league); }
        if (department) { scopeWhere.push('sc.department = ?'); scopeBinds.push(department); }
        if (club) { scopeWhere.push('a.club = ?'); scopeBinds.push(club); }
        if (frenchOnly) scopeWhere.push("a.full_name NOT GLOB '* ([A-Z][A-Z][A-Z])'");
        if (seasonYear) {
          // pb_date est au format JJ/MM/AA ; la saison N va du 01/09/N-1 au 31/08/N.
          // SEASON_SQL doit rester identique à l'expression des index de saison.
          // Une date vide donne la saison 2000, jamais égale à seasonYear
          // (2024 ou plus) : pas besoin de garde sur le format, ce qui permet à
          // SQLite de répondre depuis l'index sans relire les lignes.
          scopeWhere.push(`${SEASON_SQL} = ?`);
          scopeBinds.push(seasonYear);
        }

        const scopeFrom = needsScopeTable
          // CROSS JOIN : partir de l'index ligue/département d'athlete_scope
          // (mesuré ×9 plus rapide que de parcourir toute la distance).
          ? 'FROM athlete_scope sc CROSS JOIN athletes a ON a.id = sc.athlete_id'
          : 'FROM athletes a';
        const scopeSql = scopeWhere.join(' AND ');

        // Filtres appliqués après le classement : ils réduisent la liste mais ne
        // changent pas le rang (rang dans le périmètre complet).
        const postWhere = [];
        const postBinds = [];
        if (Number.isFinite(minPb) && minPb > 0) { postWhere.push('a.pb_sec >= ?'); postBinds.push(minPb); }
        if (Number.isFinite(maxPb) && maxPb > 0) { postWhere.push('a.pb_sec <= ?'); postBinds.push(maxPb); }
        if (ftsQuery) { postWhere.push('a.id IN (SELECT rowid FROM athlete_fts WHERE athlete_fts MATCH ?)'); postBinds.push(ftsQuery); }
        else if (q) { postWhere.push('a.name_key LIKE ?'); postBinds.push(`%${q}%`); }
        const filteredSql = [scopeSql, ...postWhere].join(' AND ');
        const scopedOrder = sort === 'name'
          ? `a.full_name ${dir}, a.pb_sec ASC, a.id ASC`
          : `a.pb_sec ${dir}, a.full_name ASC, a.id ASC`;

        if (category || club) {
          // Catégorie (tranche d'années) : aucun index ne permet de s'arrêter tôt,
          // le périmètre doit être lu en entier. Club : périmètre petit, lu
          // directement par l'index (distance, club). Dans les deux cas, on le lit
          // une seule fois (MATERIALIZED) et on en tire la page, le total et les rangs.
          const unq = (sql) => sql.replace(/\ba\./g, '');
          const res = await env.DB.prepare(`
            WITH scoped AS MATERIALIZED (
              SELECT a.id,a.full_name,a.name_key,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id
              ${scopeFrom}
              WHERE ${scopeSql}
            ), filtered AS (
              SELECT * FROM scoped ${postWhere.length ? `WHERE ${unq(postWhere.join(' AND '))}` : ''}
            ), page AS (
              SELECT * FROM filtered ORDER BY ${unq(scopedOrder)} LIMIT ? OFFSET ?
            ), h AS (
              SELECT pb_sec AS pb, COUNT(*) AS n FROM scoped
              WHERE pb_sec <= (SELECT MAX(pb_sec) FROM page) GROUP BY pb_sec
            ), c AS (
              SELECT pb, SUM(n) OVER (ORDER BY pb ROWS UNBOUNDED PRECEDING) - n AS faster FROM h
            )
            SELECT page.full_name,page.birth_year,page.sex,page.pb_sec,page.pb_course,page.pb_date,page.club,page.athlete_ffa_id,
                   1 + c.faster AS rank, (SELECT COUNT(*) FROM filtered) AS filtered_total
            FROM page LEFT JOIN c ON c.pb = page.pb_sec
            ORDER BY ${unq(scopedOrder).replace(/(full_name|pb_sec|id)/g, 'page.$1')}`)
            .bind(...scopeBinds, ...postBinds, pageSize, offset).all();
          const raw = res?.results || [];
          let total = Number(raw[0]?.filtered_total || 0);
          if (!raw.length && offset > 0) {
            // Page au-delà de la fin : le total vient d'un comptage séparé.
            const t = await env.DB.prepare(`SELECT COUNT(*) AS n ${scopeFrom} WHERE ${filteredSql}`).bind(...scopeBinds, ...postBinds).first();
            total = Number(t?.n || 0);
          }
          const rows = raw.map(({ filtered_total, ...row }) => row);
          const pages = Math.max(1, Math.ceil(total / pageSize));
          return json(request, { page: Math.min(page, pages), pageSize, total, pages, rows });
        }

        // 1) La page et le total, sans calculer le rang de tout le périmètre.
        const [pageRes, totalRes] = await env.DB.batch([
          env.DB.prepare(`
            SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id
            ${scopeFrom}
            WHERE ${filteredSql}
            ORDER BY ${scopedOrder}
            LIMIT ? OFFSET ?`).bind(...scopeBinds, ...postBinds, pageSize, offset),
          env.DB.prepare(`SELECT COUNT(*) AS n ${scopeFrom} WHERE ${filteredSql}`).bind(...scopeBinds, ...postBinds)
        ]);
        const pageRows = pageRes?.results || [];
        const total = Number(totalRes?.results?.[0]?.n || 0);

        // 2) Rang des seuls temps présents sur la page, comme RANK() :
        //    rang = 1 + nombre d'athlètes du périmètre strictement plus rapides.
        //    Comptage groupé par temps sur l'index, limité au temps le plus lent
        //    de la page, puis somme cumulée.
        let rankByPb = new Map();
        if (pageRows.length) {
          const pagePbs = [...new Set(pageRows.map((r) => Number(r.pb_sec)))];
          const maxPagePb = Math.max(...pagePbs);
          const rankRes = await env.DB.prepare(`
            WITH h AS (
              SELECT a.pb_sec AS pb, COUNT(*) AS n
              ${scopeFrom}
              WHERE ${scopeSql} AND a.pb_sec <= ?
              GROUP BY a.pb_sec
            ), c AS (
              SELECT pb, SUM(n) OVER (ORDER BY pb ROWS UNBOUNDED PRECEDING) - n AS faster FROM h
            )
            SELECT pb, faster FROM c WHERE pb IN (SELECT value FROM json_each(?))`)
            .bind(...scopeBinds, maxPagePb, JSON.stringify(pagePbs)).all();
          rankByPb = new Map((rankRes?.results || []).map((r) => [Number(r.pb), 1 + Number(r.faster)]));
        }
        const rows = pageRows.map((row) => ({ ...row, rank: rankByPb.get(Number(row.pb_sec)) ?? null }));
        const pages = Math.max(1, Math.ceil(total / pageSize));
        return json(request, { page: Math.min(page, pages), pageSize, total, pages, rows });
      }

      const where = ['a.distance = ?'];
      const binds = [distance];
      if (frenchOnly) where.push("a.full_name NOT GLOB '* ([A-Z][A-Z][A-Z])'");
      if (sex) { where.push('a.sex = ?'); binds.push(sex); }
      if (category) {
        const bounds = categoryYears(category);
        if (!bounds) return json(request, { error: 'invalid_category' }, 400);
        const [minYear, maxYear] = bounds;
        if (minYear == null) { where.push('a.birth_year <= ?'); binds.push(maxYear); }
        else { where.push('a.birth_year BETWEEN ? AND ?'); binds.push(minYear, maxYear); }
      }
      if (year) { where.push('a.birth_year = ?'); binds.push(year); }
      if (Number.isFinite(minPb) && minPb > 0) { where.push('a.pb_sec >= ?'); binds.push(minPb); }
      if (Number.isFinite(maxPb) && maxPb > 0) { where.push('a.pb_sec <= ?'); binds.push(maxPb); }
      if (ftsQuery) { where.push('a.id IN (SELECT rowid FROM athlete_fts WHERE athlete_fts MATCH ?)'); binds.push(ftsQuery); }
      else if (q) { where.push('a.name_key LIKE ?'); binds.push(`%${q}%`); }

      const afterSep2026 = useAfterSepRankColumns();
      let rankExpr = 'sr.rank_general';
      if (year) rankExpr = sex ? 'yr.rank_sex_year' : 'yr.rank_year';
      else if (category) {
        if (sex) rankExpr = afterSep2026 ? 'sr.rank_cat_after_sep' : 'sr.rank_cat_before_sep';
        else rankExpr = afterSep2026 ? 'ca.rank_category' : 'cb.rank_category';
      } else if (sex) rankExpr = 'sr.rank_sex';

      const finalWhere = where.join(' AND ');
      // Chaque colonne de rang est un RANK() par temps sur un ensemble qui contient
      // le filtre courant : à l'intérieur du filtre, l'ordre du rang est celui du
      // temps. Trier par temps donne donc le même ordre, mais en suivant les index
      // (distance, sexe, temps) au lieu de trier toutes les lignes du filtre.
      const filteredOrder = sort === 'name'
        ? `a.full_name ${dir}, a.pb_sec ASC, a.id ASC`
        : `a.pb_sec ${dir}, a.full_name ASC, a.id ASC`;
      const rankJoin = rankExpr.startsWith('yr.') ? 'JOIN athlete_rank_year yr ON yr.athlete_id = a.id'
        : rankExpr.startsWith('ca.') ? 'JOIN athlete_rank_cat_after ca ON ca.athlete_id = a.id'
          : rankExpr.startsWith('cb.') ? 'JOIN athlete_rank_cat_before cb ON cb.athlete_id = a.id'
            : 'JOIN athlete_search_rank sr ON sr.athlete_id = a.id';
      const rowsSqlFor = (whereSql) => `
        SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
               ${rankExpr} AS rank
        FROM athletes a
        ${rankJoin}
        WHERE ${whereSql}
        ORDER BY ${filteredOrder}
        LIMIT ? OFFSET ?`;
      const countSql = `SELECT COUNT(*) AS n FROM athletes a WHERE ${finalWhere}`;

      let total;
      let rowsRes;
      if (category && !year && !q && sort !== 'name') {
        // Catégorie : pour une grosse catégorie (SE, M0…), parcourir l'index par
        // temps et s'arrêter à la page demandée est bien plus rapide que trier
        // toute la catégorie ; pour une petite (M9, M10, cadets…), c'est l'inverse.
        // Le « + » devant birth_year empêche SQLite d'utiliser l'index par année.
        const [countRes, statsRes] = await env.DB.batch([
          env.DB.prepare(countSql).bind(...binds),
          env.DB.prepare('SELECT total FROM ffa_distance_stats WHERE distance = ?').bind(distance)
        ]);
        total = Number(countRes?.results?.[0]?.n || 0);
        const distanceTotal = Number(statsRes?.results?.[0]?.total || 0);
        const largeCategory = distanceTotal > 0 && total >= distanceTotal * LARGE_CATEGORY_SHARE;
        const whereSql = largeCategory ? finalWhere.replace(/\ba\.birth_year (BETWEEN|<=)/, '+a.birth_year $1') : finalWhere;
        rowsRes = await env.DB.prepare(rowsSqlFor(whereSql)).bind(...binds, pageSize, offset).all();
      } else {
        const [r, countRes] = await env.DB.batch([
          env.DB.prepare(rowsSqlFor(finalWhere)).bind(...binds, pageSize, offset),
          env.DB.prepare(countSql).bind(...binds)
        ]);
        rowsRes = r;
        total = Number(countRes?.results?.[0]?.n || 0);
      }
      const pages = Math.max(1, Math.ceil(total / pageSize));
      return json(request, {
        page: Math.min(page, pages),
        pageSize,
        total,
        pages,
        rows: rowsRes?.results || []
      });
    }

    return json(request, { error: 'not_found' }, 404);
}
