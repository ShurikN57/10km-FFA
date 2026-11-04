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

function categoryYears(category, seasonYear = currentSeasonYear()) {
  const cat = String(category || '').toUpperCase();
  const entry = CATEGORY_AGES.find(([code]) => code === cat);
  if (!entry) return null;
  const [, minAge, maxAge] = entry;
  return [maxAge == null ? null : seasonYear - maxAge, seasonYear - minAge];
}

function categoryBounds(birthYear, seasonYear = currentSeasonYear()) {
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

const MAX_PAGE = 10000;

export default {
  async fetch(request, env) {
    try {
      return await handle(request, env);
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
      const seasonYear = /^(2024|2025|2026)$/.test(seasonYearRaw) ? Number(seasonYearRaw) : 0;
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
        const frenchOrder = sort === 'name'
          ? `a.full_name ${dir}, a.pb_sec ASC, a.id ASC`
          : sort === 'time'
            ? `a.pb_sec ${dir}, a.full_name ASC, a.id ASC`
            : `fr.rank_general ${dir}, a.pb_sec ${dir}, a.full_name ASC, a.id ASC`;
        const [rowsRes, statsRes] = await env.DB.batch([
          env.DB.prepare(`
            SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
                   fr.rank_general AS rank
            FROM athlete_french_rank fr
            JOIN athletes a ON a.id = fr.athlete_id
            WHERE fr.distance = ?
            ORDER BY ${frenchOrder}
            LIMIT ? OFFSET ?
          `).bind(distance, pageSize, offset),
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
        if (league) { scopeWhere.push('sc.league = ?'); scopeBinds.push(league); }
        if (department) { scopeWhere.push('sc.department = ?'); scopeBinds.push(department); }
        if (club) { scopeWhere.push('a.club = ?'); scopeBinds.push(club); }
        if (frenchOnly) scopeWhere.push("a.full_name NOT GLOB '* ([A-Z][A-Z][A-Z])'");
        if (seasonYear) {
          scopeWhere.push("2000 + CAST(substr(a.pb_date, 7, 2) AS INTEGER) + CASE WHEN CAST(substr(a.pb_date, 4, 2) AS INTEGER) >= 9 THEN 1 ELSE 0 END = ?");
          scopeBinds.push(seasonYear);
        }

        const postWhere = [];
        const postBinds = [];
        if (Number.isFinite(minPb) && minPb > 0) { postWhere.push('pb_sec >= ?'); postBinds.push(minPb); }
        if (Number.isFinite(maxPb) && maxPb > 0) { postWhere.push('pb_sec <= ?'); postBinds.push(maxPb); }
        if (ftsQuery) { postWhere.push('id IN (SELECT rowid FROM athlete_fts WHERE athlete_fts MATCH ?)'); postBinds.push(ftsQuery); }
        else if (q) { postWhere.push('name_key LIKE ?'); postBinds.push(`%${q}%`); }

        const scopedOrder = sort === 'name'
          ? `full_name ${dir}, pb_sec ASC, id ASC`
          : sort === 'time'
            ? `pb_sec ${dir}, full_name ASC, id ASC`
            : `rank ${dir}, pb_sec ${dir}, full_name ASC, id ASC`;
        const sql = `
          WITH scoped AS (
            SELECT a.id,a.full_name,a.name_key,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id,
                   RANK() OVER (ORDER BY a.pb_sec ASC) AS rank
            FROM athletes a
            ${needsScopeTable ? 'JOIN athlete_scope sc ON sc.athlete_id = a.id' : ''}
            WHERE ${scopeWhere.join(' AND ')}
          ), filtered AS (
            SELECT * FROM scoped ${postWhere.length ? `WHERE ${postWhere.join(' AND ')}` : ''}
          )
          SELECT full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id,rank,
                 COUNT(*) OVER () AS filtered_total
          FROM filtered
          ORDER BY ${scopedOrder}
          LIMIT ? OFFSET ?`;
        const res = await env.DB.prepare(sql).bind(...scopeBinds, ...postBinds, pageSize, offset).all();
        const rawRows = res.results || [];
        const total = Number(rawRows[0]?.filtered_total || 0);
        const rows = rawRows.map(({ filtered_total, ...row }) => row);
        const pages = Math.max(1, Math.ceil(total / pageSize));
        return json(request, {
          page: Math.min(page, pages),
          pageSize,
          total,
          pages,
          rows
        });
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
      const countSql = `SELECT COUNT(*) AS n FROM athletes a WHERE ${finalWhere}`;

      const [rowsRes, countRes] = await env.DB.batch([
        env.DB.prepare(rowsSql).bind(...binds, pageSize, offset),
        env.DB.prepare(countSql).bind(...binds)
      ]);
      const total = Number(countRes?.results?.[0]?.n || 0);
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
