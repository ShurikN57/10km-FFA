const ALLOWED_ORIGIN = 'https://shurikn57.github.io';

function corsHeaders(request) {
  const origin = request.headers.get('Origin');
  return {
    'Access-Control-Allow-Origin': origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'GET,OPTIONS',
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

function categoryBounds(birthYear) {
  const y = Number(birthYear);
  if (!Number.isFinite(y)) return null;
  const afterSep2026 = new Date() >= new Date('2026-09-01T00:00:00Z');
  if (afterSep2026) {
    if (y >= 2010 && y <= 2011) return [2010, 2011, 'CA'];
    if (y >= 2008 && y <= 2009) return [2008, 2009, 'JU'];
    if (y >= 2005 && y <= 2007) return [2005, 2007, 'ES'];
    if (y >= 1993 && y <= 2004) return [1993, 2004, 'SE'];
    if (y >= 1988 && y <= 1992) return [1988, 1992, 'M0'];
    if (y >= 1983 && y <= 1987) return [1983, 1987, 'M1'];
    if (y >= 1978 && y <= 1982) return [1978, 1982, 'M2'];
    if (y >= 1973 && y <= 1977) return [1973, 1977, 'M3'];
    if (y >= 1968 && y <= 1972) return [1968, 1972, 'M4'];
    if (y >= 1963 && y <= 1967) return [1963, 1967, 'M5'];
    if (y >= 1958 && y <= 1962) return [1958, 1962, 'M6'];
    if (y >= 1953 && y <= 1957) return [1953, 1957, 'M7'];
    if (y >= 1948 && y <= 1952) return [1948, 1952, 'M8'];
    if (y >= 1943 && y <= 1947) return [1943, 1947, 'M9'];
    if (y <= 1942) return [null, 1942, 'M10'];
    return null;
  }
  if (y >= 2009 && y <= 2010) return [2009, 2010, 'CA'];
  if (y >= 2007 && y <= 2008) return [2007, 2008, 'JU'];
  if (y >= 2004 && y <= 2006) return [2004, 2006, 'ES'];
  if (y >= 1992 && y <= 2003) return [1992, 2003, 'SE'];
  if (y >= 1987 && y <= 1991) return [1987, 1991, 'M0'];
  if (y >= 1982 && y <= 1986) return [1982, 1986, 'M1'];
  if (y >= 1977 && y <= 1981) return [1977, 1981, 'M2'];
  if (y >= 1972 && y <= 1976) return [1972, 1976, 'M3'];
  if (y >= 1967 && y <= 1971) return [1967, 1971, 'M4'];
  if (y >= 1962 && y <= 1966) return [1962, 1966, 'M5'];
  if (y >= 1957 && y <= 1961) return [1957, 1961, 'M6'];
  if (y >= 1952 && y <= 1956) return [1952, 1956, 'M7'];
  if (y >= 1947 && y <= 1951) return [1947, 1951, 'M8'];
  if (y >= 1942 && y <= 1946) return [1942, 1946, 'M9'];
  if (y <= 1941) return [null, 1941, 'M10'];
  return null;
}

function categoryYears(category) {
  const cat = String(category || '').toUpperCase();
  const afterSep2026 = new Date() >= new Date('2026-09-01T00:00:00Z');
  const groups = afterSep2026 ? {
    CA:[2010,2011], JU:[2008,2009], ES:[2005,2007], SE:[1993,2004],
    M0:[1988,1992], M1:[1983,1987], M2:[1978,1982], M3:[1973,1977],
    M4:[1968,1972], M5:[1963,1967], M6:[1958,1962], M7:[1953,1957],
    M8:[1948,1952], M9:[1943,1947], M10:[null,1942]
  } : {
    CA:[2009,2010], JU:[2007,2008], ES:[2004,2006], SE:[1992,2003],
    M0:[1987,1991], M1:[1982,1986], M2:[1977,1981], M3:[1972,1976],
    M4:[1967,1971], M5:[1962,1966], M6:[1957,1961], M7:[1952,1956],
    M8:[1947,1951], M9:[1942,1946], M10:[null,1941]
  };
  return groups[cat] || null;
}

async function attachRanks(env, rows, distance, mode) {
  if (!rows.length) return rows;
  const statements = rows.map((row) => {
    if (mode === 'general') {
      return env.DB.prepare('SELECT COUNT(*) AS n FROM athletes WHERE distance = ? AND pb_sec < ?')
        .bind(distance, Number(row.pb_sec));
    }
    if (mode === 'category') {
      const bounds = categoryBounds(row.birth_year);
      if (!bounds || !row.sex) return env.DB.prepare('SELECT 0 AS n');
      const [minYear, maxYear] = bounds;
      if (minYear == null) {
        return env.DB.prepare('SELECT COUNT(*) AS n FROM athletes WHERE distance = ? AND sex = ? AND birth_year <= ? AND pb_sec < ?')
          .bind(distance, row.sex, maxYear, Number(row.pb_sec));
      }
      return env.DB.prepare('SELECT COUNT(*) AS n FROM athletes WHERE distance = ? AND sex = ? AND birth_year BETWEEN ? AND ? AND pb_sec < ?')
        .bind(distance, row.sex, minYear, maxYear, Number(row.pb_sec));
    }
    if (!row.sex) return env.DB.prepare('SELECT 0 AS n');
    return env.DB.prepare('SELECT COUNT(*) AS n FROM athletes WHERE distance = ? AND sex = ? AND pb_sec < ?')
      .bind(distance, row.sex, Number(row.pb_sec));
  });
  const rankResults = await env.DB.batch(statements);
  return rows.map((row, i) => {
    const n = Number(rankResults[i]?.results?.[0]?.n || 0);
    const bounds = mode === 'category' ? categoryBounds(row.birth_year) : null;
    return { ...row, rank: n + 1, category: bounds?.[2] || '' };
  });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders(request) });
    if (request.method !== 'GET') return json(request, { error: 'method_not_allowed' }, 405);

    const url = new URL(request.url);
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
      const stmt = env.DB.prepare(`
        SELECT a.full_name,a.birth_year,a.sex,a.pb_sec,a.pb_course,a.pb_date,a.club,a.athlete_ffa_id
        FROM athlete_fts
        JOIN athletes a ON a.id = athlete_fts.rowid
        WHERE athlete_fts MATCH ? AND a.distance = ?
        ORDER BY a.birth_year ASC, a.full_name ASC
        LIMIT 100
      `).bind(ftsQuery, distance);
      const res = await stmt.all();
      const rows = await attachRanks(env, res.results || [], distance, mode);
      return json(request, { rows });
    }

    if (url.pathname === '/ranking') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);

      const sexRaw = String(url.searchParams.get('sex') || '').toUpperCase();
      const sex = sexRaw === 'M' || sexRaw === 'F' ? sexRaw : '';
      const category = String(url.searchParams.get('category') || '').toUpperCase();
      const yearRaw = String(url.searchParams.get('year') || '').trim();
      const year = /^\d{4}$/.test(yearRaw) ? Number(yearRaw) : 0;
      const minPb = Number(url.searchParams.get('minPb') || 0);
      const maxPb = Number(url.searchParams.get('maxPb') || 0);
      const q = normalizeName(url.searchParams.get('q'));
      const ftsQuery = q.length >= 3 ? ftsQueryFromName(q) : '';
      const page = Math.max(1, Number(url.searchParams.get('page') || 1));
      const pageSize = 100;
      const offset = (page - 1) * pageSize;

      const plainGeneral = !sex && !category && !year && !q &&
        !(Number.isFinite(minPb) && minPb > 0) &&
        !(Number.isFinite(maxPb) && maxPb > 0);

      if (plainGeneral) {
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

      const scopeWhere = ['distance = ?'];
      const scopeBinds = [distance];
      if (sex) { scopeWhere.push('sex = ?'); scopeBinds.push(sex); }
      if (category) {
        const bounds = categoryYears(category);
        if (!bounds) return json(request, { error: 'invalid_category' }, 400);
        const [minYear, maxYear] = bounds;
        if (minYear == null) { scopeWhere.push('birth_year <= ?'); scopeBinds.push(maxYear); }
        else { scopeWhere.push('birth_year BETWEEN ? AND ?'); scopeBinds.push(minYear, maxYear); }
      }
      if (year) { scopeWhere.push('birth_year = ?'); scopeBinds.push(year); }

      const outerWhere = ['1=1'];
      const outerBinds = [];
      if (Number.isFinite(minPb) && minPb > 0) { outerWhere.push('pb_sec >= ?'); outerBinds.push(minPb); }
      if (Number.isFinite(maxPb) && maxPb > 0) { outerWhere.push('pb_sec <= ?'); outerBinds.push(maxPb); }
      if (ftsQuery) { outerWhere.push('id IN (SELECT rowid FROM athlete_fts WHERE athlete_fts MATCH ?)'); outerBinds.push(ftsQuery); }
      else if (q) { outerWhere.push('name_key LIKE ?'); outerBinds.push(`%${q}%`); }

      const cte = `WITH scoped AS (
        SELECT id,name_key,full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id,
               RANK() OVER (ORDER BY pb_sec ASC) AS rank
        FROM athletes
        WHERE ${scopeWhere.join(' AND ')}
      )`;
      const finalWhere = outerWhere.join(' AND ');
      const rowsSql = `${cte}
        SELECT full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id,rank
        FROM scoped
        WHERE ${finalWhere}
        ORDER BY rank ASC, pb_sec ASC, full_name ASC
        LIMIT ? OFFSET ?`;
      const countSql = `${cte} SELECT COUNT(*) AS n FROM scoped WHERE ${finalWhere}`;

      const [rowsRes, countRes] = await env.DB.batch([
        env.DB.prepare(rowsSql).bind(...scopeBinds, ...outerBinds, pageSize, offset),
        env.DB.prepare(countSql).bind(...scopeBinds, ...outerBinds)
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
};
