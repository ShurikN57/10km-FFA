// Test d'intégration : exécute les vraies requêtes SQL du Worker sur une base
// SQLite en mémoire construite avec le schéma de production
// (api/schema.sql). Détecte les fautes de colonnes,
// de jointures ou de syntaxe que la base simulée de worker.test.mjs ne voit pas.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import worker from '../api/worker.js';

const ORIGIN = 'https://shurikn57.github.io';
const db = new DatabaseSync(':memory:');
db.exec(fs.readFileSync(new URL('../api/schema.sql', import.meta.url), 'utf8'));

// Adaptateur minimal reproduisant l'API D1 utilisée par le Worker.
const DB = {
  prepare(sql) {
    const stmt = db.prepare(sql);
    let binds = [];
    const api = {
      bind(...a) { binds = a; return api; },
      async all() { return { results: stmt.all(...binds) }; },
      async first() { return stmt.get(...binds) ?? null; }
    };
    return api;
  },
  async batch(list) { return Promise.all(list.map((s) => s.all())); }
};

// --- Jeu de données -------------------------------------------------------
const athletes = [
  // distance, full_name, birth_year, sex, pb_sec, pb_date, club, ffa_id, league, dept
  ['10k', 'DUPONT Jean', 1985, 'M', 1900, '12/10/25', 'Club A', 'A1', 'I-F', '077'],
  ['10k', 'MARTIN Paul', 1990, 'M', 1850, '03/12/23', 'Club B', 'B1', 'PCA', '013'],
  ['10k', 'MARTIN Paul', 1970, 'M', 2400, '15/05/24', 'Club A', 'B2', 'I-F', '077'],
  ['10k', 'DURAND Lucie', 1995, 'F', 2100, '20/04/26', 'Club B', 'C1', 'PCA', '013'],
  ['10k', 'SMITH John (GBR)', 1988, 'M', 1800, '01/09/25', 'Club C', '', 'N-A', '033'],
  ['10k', 'PETIT Marie', 2000, 'F', 2300, '', 'Club A', 'D1', 'I-F', '077'],
  ['5k', 'DUPONT Jean', 1985, 'M', 900, '10/10/25', 'Club A', 'A1', 'I-F', '077']
];
const ins = db.prepare(`INSERT INTO athletes(distance,full_name,name_key,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id)
  VALUES(?,?,?,?,?,?,?,?,?,?)`);
const nameKey = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase()
  .replace(/[^A-Z0-9]+/g, ' ').trim();
for (const a of athletes) {
  const { lastInsertRowid: id } = ins.run(a[0], a[1], nameKey(a[1]), a[2], a[3], a[4], 'Course', a[5], a[6], a[7]);
  db.prepare('INSERT INTO athlete_fts(rowid,name_key,distance) VALUES(?,?,?)').run(id, nameKey(a[1]), a[0]);
  db.prepare('INSERT INTO athlete_scope VALUES(?,?,?,?,?)').run(id, a[0], a[8], a[9], 2025);
}
// Rangs approximatifs (le calcul exact de production n'est pas versionné).
db.exec(`
  INSERT INTO athlete_general_rank
    SELECT id, distance, RANK() OVER w, ROW_NUMBER() OVER w FROM athletes
    WINDOW w AS (PARTITION BY distance ORDER BY pb_sec);
  INSERT INTO athlete_french_rank
    SELECT id, distance, RANK() OVER (PARTITION BY distance ORDER BY pb_sec)
    FROM athletes WHERE full_name NOT GLOB '* ([A-Z][A-Z][A-Z])';
  INSERT INTO athlete_search_rank
    SELECT id, RANK() OVER (PARTITION BY distance ORDER BY pb_sec),
           RANK() OVER (PARTITION BY distance, sex ORDER BY pb_sec), 1, 1 FROM athletes;
  INSERT INTO athlete_rank_cat_before SELECT id, 1 FROM athletes;
  INSERT INTO athlete_rank_cat_after SELECT id, 1 FROM athletes;
  INSERT INTO athlete_rank_year
    SELECT id, RANK() OVER (PARTITION BY distance, birth_year ORDER BY pb_sec),
           RANK() OVER (PARTITION BY distance, birth_year, sex ORDER BY pb_sec) FROM athletes;
  INSERT INTO ffa_distance_stats SELECT distance, COUNT(*) FROM athletes GROUP BY distance;
  INSERT INTO ffa_french_stats SELECT distance, COUNT(*) FROM athletes
    WHERE full_name NOT GLOB '* ([A-Z][A-Z][A-Z])' GROUP BY distance;
  INSERT INTO ffa_scope_options SELECT DISTINCT a.distance, s.league, s.department, a.club, s.race_year
    FROM athletes a JOIN athlete_scope s ON s.athlete_id = a.id;
`);

async function get(path, init) {
  const res = await worker.fetch(new Request('https://api.test' + path, { ...init, headers: { Origin: ORIGIN, 'Content-Type': 'application/json' } }), { DB });
  const body = await res.json();
  assert.equal(res.status, 200, `${path} → ${res.status} ${JSON.stringify(body)}`);
  return body;
}
const names = (rows) => rows.map((r) => r.full_name);

test('/health', async () => {
  assert.equal((await get('/health')).athletes, 7);
});

for (const mode of ['general', 'sex', 'category']) {
  test(`/search mode=${mode}`, async () => {
    const { rows } = await get(`/search?distance=10k&q=martin&mode=${mode}`);
    assert.deepEqual(names(rows), ['MARTIN Paul', 'MARTIN Paul']);
    assert.ok(rows.every((r) => r.rank > 0));
    if (mode === 'category') assert.deepEqual(rows.map((r) => r.category), ['M6', 'M0'].map((c, i) => rows[i].category));
  });
}

test('/search : le nom exact passe en premier', async () => {
  const { rows } = await get('/search?distance=10k&q=jean%20dupont');
  assert.equal(rows[0].full_name, 'DUPONT Jean');
});

test('/ranking général (chemin précalculé)', async () => {
  const r = await get('/ranking?distance=10k');
  assert.equal(r.total, 6);
  assert.deepEqual(names(r.rows).slice(0, 2), ['SMITH John (GBR)', 'MARTIN Paul']);
});

test('/ranking général trié par nom décroissant', async () => {
  const r = await get('/ranking?distance=10k&sort=name&dir=desc');
  assert.equal(r.rows[0].full_name, 'SMITH John (GBR)');
});

test('/ranking français seulement (chemin précalculé)', async () => {
  const r = await get('/ranking?distance=10k&french=1');
  assert.equal(r.total, 5);
  assert.ok(!names(r.rows).includes('SMITH John (GBR)'));
});

test('/ranking filtré : sexe', async () => {
  const r = await get('/ranking?distance=10k&sex=F');
  assert.deepEqual(names(r.rows), ['DURAND Lucie', 'PETIT Marie']);
  assert.equal(r.total, 2);
});

test('/ranking filtré : catégorie avec et sans sexe', async () => {
  for (const q of ['category=SE', 'category=SE&sex=F']) {
    const r = await get(`/ranking?distance=10k&${q}`);
    assert.ok(r.rows.length > 0, q);
  }
});

test('/ranking filtré : année de naissance, temps, nom', async () => {
  assert.deepEqual(names((await get('/ranking?distance=10k&year=1985')).rows), ['DUPONT Jean']);
  assert.equal((await get('/ranking?distance=10k&minPb=1850&maxPb=2100')).total, 3);
  assert.equal((await get('/ranking?distance=10k&q=martin&sex=M')).total, 2);
  assert.equal((await get('/ranking?distance=10k&q=du&sex=M')).total, 1); // < 3 lettres : LIKE
});

test('/ranking par périmètre : ligue, département, club', async () => {
  assert.equal((await get('/ranking?distance=10k&league=I-F')).total, 3);
  assert.equal((await get('/ranking?distance=10k&department=013&sex=F')).total, 1);
  const club = await get('/ranking?distance=10k&club=' + encodeURIComponent('Club A'));
  assert.deepEqual(names(club.rows), ['DUPONT Jean', 'PETIT Marie', 'MARTIN Paul']);
  assert.deepEqual(club.rows.map((r) => r.rank), [1, 2, 3]);
});

test('/ranking par saison (pb_date JJ/MM/AA, date vide exclue)', async () => {
  // Saison 2024 : 01/09/23 → 31/08/24.
  assert.deepEqual(names((await get('/ranking?distance=10k&seasonYear=2024')).rows), ['MARTIN Paul', 'MARTIN Paul']);
  // Saison 2026 : SMITH (01/09/25), DUPONT (12/10/25), DURAND (20/04/26).
  assert.equal((await get('/ranking?distance=10k&seasonYear=2026')).total, 3);
});

test('/ranking par périmètre + français + recherche', async () => {
  const r = await get('/ranking?distance=10k&seasonYear=2026&french=1&q=dupont');
  assert.deepEqual(names(r.rows), ['DUPONT Jean']);
});

test('/ranking-options', async () => {
  const { rows } = await get('/ranking-options?distance=10k');
  assert.ok(rows.some((r) => r.league === 'I-F' && r.club === 'Club A'));
});

test('/match', async () => {
  const { rows } = await get('/match?distance=10k', { method: 'POST', body: JSON.stringify({ names: ['Jean Dupont', 'MARTIN Paul', 'Inconnu Total'] }) });
  // name_key de production = nom normalisé dans l'ordre d'origine
  assert.deepEqual(names(rows).sort(), ['MARTIN Paul', 'MARTIN Paul']);
});
