// Vérifie les rangs du classement par périmètre (saison, ligue, français…),
// calculés à partir de comptages sur l'index, contre une référence calculée
// ici en JavaScript, sur des données aléatoires avec beaucoup d'ex aequo.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import worker from '../api/worker.js';

const db = new DatabaseSync(':memory:');
db.exec(fs.readFileSync(new URL('../api/schema.sql', import.meta.url), 'utf8'));
db.exec(fs.readFileSync(new URL('../api/migrations/0001_index_saison_francais.sql', import.meta.url), 'utf8'));
const DB = {
  prepare(sql) { const st = db.prepare(sql); let b = []; const api = { bind(...a) { b = a; return api; }, async all() { return { results: st.all(...b) }; }, async first() { return st.get(...b) ?? null; } }; return api; },
  async batch(list) { return Promise.all(list.map((s) => s.all())); }
};

// Générateur pseudo-aléatoire déterministe.
let seed = 42;
const rnd = (n) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
const leagues = ['I-F', 'PCA', 'OCC'];
const dates = ['15/10/23', '02/03/24', '20/09/24', '11/05/25', '01/09/25', '30/08/25', '14/02/26', ''];
const people = [];
const clubs = ['Club A', 'Club B'];
const insA = db.prepare('INSERT INTO athletes(distance,full_name,name_key,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id) VALUES(?,?,?,?,?,?,?,?,?,?)');
const insS = db.prepare('INSERT INTO athlete_scope VALUES(?,?,?,?,?)');
for (let i = 0; i < 600; i++) {
  const p = {
    name: `NOM${rnd(40)} P${i}${rnd(3) === 0 ? ' (GBR)' : ''}`,
    birth: 1960 + rnd(50), sex: rnd(2) ? 'M' : 'F',
    pb: 1800 + rnd(60) * 5, // beaucoup d'ex aequo
    date: dates[rnd(dates.length)], league: leagues[rnd(3)], dept: '0' + (10 + rnd(3))
  };
  const { lastInsertRowid: id } = insA.run('10k', p.name, p.name, p.birth, p.sex, p.pb, 'C', p.date || null, clubs[i % 2], 'X' + i);
  p.club = clubs[i % 2];
  insS.run(id, '10k', p.league, p.dept, 2025);
  db.prepare('INSERT INTO athlete_fts(rowid,name_key,distance) VALUES(?,?,?)').run(id, p.name, '10k');
  people.push({ ...p, id: Number(id) });
}

const season = (d) => (d ? 2000 + Number(d.slice(6, 8)) + (Number(d.slice(3, 5)) >= 9 ? 1 : 0) : 2000);
const french = (n) => !/ \([A-Z]{3}\)$/.test(n);

function reference(params) {
  const scope = people.filter((p) =>
    (!params.sex || p.sex === params.sex) &&
    (!params.league || p.league === params.league) &&
    (!params.department || p.dept === params.department) &&
    (!params.seasonYear || season(p.date) === params.seasonYear) &&
    (!params.french || french(p.name)) &&
    (!params.club || p.club === params.club) &&
    (!params.category || (p.birth >= params.catYears[0] && p.birth <= params.catYears[1])));
  const withRank = scope.map((p) => ({ ...p, rank: 1 + scope.filter((o) => o.pb < p.pb).length }));
  const filtered = withRank.filter((p) => (!params.minPb || p.pb >= params.minPb) && (!params.maxPb || p.pb <= params.maxPb) &&
    (!params.q || p.name.includes(params.q)));
  const desc = params.dir === 'desc';
  const byName = (a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
  if (params.sort === 'name') filtered.sort((a, b) => (desc ? -byName(a, b) : byName(a, b)) || a.pb - b.pb || a.id - b.id);
  else filtered.sort((a, b) => (desc ? b.pb - a.pb : a.pb - b.pb) || byName(a, b) || a.id - b.id);
  const page = params.page || 1;
  return { total: filtered.length, rows: filtered.slice((page - 1) * 100, page * 100).map((p) => [p.name, p.pb, p.rank]) };
}

const combos = [];
const thisSeason = (() => { const [y, m] = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit' }).format(new Date()).split('-').map(Number); return Math.min(m >= 9 ? y + 1 : y, 2027); })();
const SE = { category: 'SE', catYears: [thisSeason - 34, thisSeason - 23] };
const M2 = { category: 'M2', catYears: [thisSeason - 49, thisSeason - 45] };
for (const scope of [{ club: 'Club B' }, { club: 'Club A', ...SE, sex: 'M' }, { ...SE, french: 1 }, { ...M2, seasonYear: 2025, sex: 'F' }, { ...SE, league: 'OCC' }, { seasonYear: 2025 }, { seasonYear: 2024, sex: 'F' }, { league: 'PCA' }, { department: '011', sex: 'M' }, { french: 1, sex: 'F' }, { french: 1, seasonYear: 2026 }, { league: 'I-F', seasonYear: 2025, sex: 'M' }])
  for (const dir of ['asc', 'desc'])
    for (const range of [{}, { minPb: 1900 }, { maxPb: 1950 }, { minPb: 1850, maxPb: 2000 }])
      for (const extra of [{}, { sort: 'name' }, { q: 'NOM1' }, { q: 'P1', sort: 'name' }])
        for (const page of [1, 2])
          combos.push({ ...scope, ...range, ...extra, dir, page });

test(`rangs par périmètre identiques à la référence (${combos.length} combinaisons)`, async () => {
  for (const params of combos) {
    const qs = new URLSearchParams({ distance: '10k', ...Object.fromEntries(Object.entries(params).filter(([k]) => k !== 'catYears').map(([k, v]) => [k, String(v)])) });
    const res = await worker.fetch(new Request('https://api.test/ranking?' + qs), { DB });
    const body = await res.json();
    const ref = reference(params);
    assert.equal(body.total, ref.total, qs.toString());
    assert.deepEqual(body.rows.map((r) => [r.full_name, r.pb_sec, r.rank]), ref.rows, qs.toString());
  }
});
