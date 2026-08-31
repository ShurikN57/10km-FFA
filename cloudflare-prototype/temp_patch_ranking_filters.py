from pathlib import Path

p=Path('cloudflare-prototype/worker.js')
s=p.read_text(encoding='utf-8')
start=s.index("      const scopeWhere = ['distance = ?'];")
end=s.index("      return json(request, {\n        page: Math.min(page, pages),\n        pageSize,\n        total,\n        pages,\n        rows: rowsRes?.results || []\n      });", start)
end += len("      return json(request, {\n        page: Math.min(page, pages),\n        pageSize,\n        total,\n        pages,\n        rows: rowsRes?.results || []\n      });")
new='''      const where = ['a.distance = ?'];
      const binds = [distance];
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

      const afterSep2026 = new Date() >= new Date('2026-09-01T00:00:00Z');
      let rankExpr = 'sr.rank_general';
      if (year) rankExpr = sex ? 'yr.rank_sex_year' : 'yr.rank_year';
      else if (category) {
        if (sex) rankExpr = afterSep2026 ? 'sr.rank_cat_after_sep' : 'sr.rank_cat_before_sep';
        else rankExpr = afterSep2026 ? 'ca.rank_category' : 'cb.rank_category';
      } else if (sex) rankExpr = 'sr.rank_sex';

      const finalWhere = where.join(' AND ');
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
      });'''
s=s[:start]+new+s[end:]
assert 'WITH scoped AS' not in s
assert 'athlete_rank_year' in s
assert 'rank_cat_after_sep' in s
p.write_text(s,encoding='utf-8')
