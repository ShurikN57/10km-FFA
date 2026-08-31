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
      const q = String(url.searchParams.get('q') || '').trim().toUpperCase();
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);
      if (q.length < 3) return json(request, { rows: [] });

      const stmt = env.DB.prepare(`
        SELECT full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id
        FROM athletes
        WHERE distance = ? AND name_key LIKE ?
        ORDER BY birth_year ASC, full_name ASC
        LIMIT 100
      `).bind(distance, `%${q}%`);
      const res = await stmt.all();
      return json(request, { rows: res.results || [] });
    }

    if (url.pathname === '/ranking') {
      const distance = normalizeDistance(url.searchParams.get('distance'));
      if (!distance) return json(request, { error: 'invalid_distance' }, 400);
      const sex = String(url.searchParams.get('sex') || '').toUpperCase();
      const year = Number(url.searchParams.get('year') || 0);
      const minPb = Number(url.searchParams.get('minPb') || 0);
      const maxPb = Number(url.searchParams.get('maxPb') || 0);
      const page = Math.max(1, Number(url.searchParams.get('page') || 1));
      const pageSize = 100;
      const offset = (page - 1) * pageSize;

      const where = ['distance = ?'];
      const binds = [distance];
      if (sex === 'M' || sex === 'F') { where.push('sex = ?'); binds.push(sex); }
      if (Number.isFinite(year) && year > 0) { where.push('birth_year = ?'); binds.push(year); }
      if (Number.isFinite(minPb) && minPb > 0) { where.push('pb_sec >= ?'); binds.push(minPb); }
      if (Number.isFinite(maxPb) && maxPb > 0) { where.push('pb_sec <= ?'); binds.push(maxPb); }

      const sql = `SELECT full_name,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id
                   FROM athletes WHERE ${where.join(' AND ')}
                   ORDER BY pb_sec ASC, full_name ASC LIMIT ? OFFSET ?`;
      const res = await env.DB.prepare(sql).bind(...binds, pageSize, offset).all();
      return json(request, { page, pageSize, rows: res.results || [] });
    }

    return json(request, { error: 'not_found' }, 404);
  }
};
