// Tests du Worker avec une base D1 simulée (aucun accès réseau).
import test, { mock } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../api/worker.js';

const ORIGIN = 'https://shurikn57.github.io';

function mockDb() {
  const calls = [];
  const stmt = (sql) => {
    const s = {
      sql, binds: [],
      bind(...a) { s.binds = a; return s; },
      all: async () => ({ results: [] }),
      first: async () => ({ n: 42 })
    };
    calls.push(s);
    return s;
  };
  return {
    calls,
    prepare: stmt,
    batch: async (list) => list.map(() => ({ results: [] }))
  };
}

const req = (path, init = {}) =>
  new Request('https://api.test' + path, { ...init, headers: { Origin: ORIGIN, ...(init.headers || {}) } });

test('/health renvoie le nombre d\'athlètes', async () => {
  const res = await worker.fetch(req('/health'), { DB: mockDb() });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, athletes: 42 });
  assert.equal(res.headers.get('access-control-allow-origin'), ORIGIN);
});

test('une erreur D1 donne un 500 JSON avec CORS', async () => {
  const DB = { prepare() { throw new Error('D1 down'); } };
  const orig = console.error; console.error = () => {};
  try {
    const res = await worker.fetch(req('/health'), { DB });
    assert.equal(res.status, 500);
    assert.equal(res.headers.get('access-control-allow-origin'), ORIGIN);
    assert.deepEqual(await res.json(), { error: 'internal_error' });
  } finally { console.error = orig; }
});

test('distance invalide → 400', async () => {
  const res = await worker.fetch(req('/ranking?distance=42k'), { DB: mockDb() });
  assert.equal(res.status, 400);
});

test('route inconnue → 404', async () => {
  const res = await worker.fetch(req('/nope'), { DB: mockDb() });
  assert.equal(res.status, 404);
});

for (const [raw, expected] of [['abc', 0], ['-5', 0], ['3', 200], ['99999999', 999900]]) {
  test(`page=${raw} donne un OFFSET valide (${expected})`, async () => {
    const DB = mockDb();
    const res = await worker.fetch(req(`/ranking?distance=10k&sex=M&page=${raw}`), { DB });
    assert.equal(res.status, 200);
    const rows = DB.calls.find((c) => /LIMIT \? OFFSET \?/.test(c.sql));
    assert.equal(rows.binds.at(-1), expected);
  });
}

async function categoryCall(isoDate, path) {
  mock.timers.enable({ apis: ['Date'], now: new Date(isoDate) });
  try {
    const DB = mockDb();
    const res = await worker.fetch(req(path), { DB });
    return { DB, res };
  } finally { mock.timers.reset(); }
}

for (const [date, years, rankCol] of [
  ['2026-03-01T12:00:00Z', [1982, 1986], 'cb.rank_category'],   // saison 2026
  ['2026-10-01T12:00:00Z', [1983, 1987], 'ca.rank_category'],   // saison 2027
  ['2027-10-01T12:00:00Z', [1983, 1987], 'ca.rank_category']    // reste 2027 : rangs D1 non recalculés
]) {
  test(`category=M1 le ${date.slice(0, 10)} → ${years.join('-')} avec ${rankCol}`, async () => {
    const { DB } = await categoryCall(date, '/ranking?distance=10k&category=M1');
    const count = DB.calls.find((c) => /COUNT\(\*\)/.test(c.sql));
    assert.deepEqual(count.binds, ['10k', ...years]);
    const rows = DB.calls.find((c) => /LIMIT \? OFFSET \?/.test(c.sql));
    assert.match(rows.sql, new RegExp(rankCol.replace('.', '\\.') + ' AS rank'));
  });
}

test('catégorie inconnue → 400', async () => {
  const res = await worker.fetch(req('/ranking?distance=10k&category=ZZ'), { DB: mockDb() });
  assert.equal(res.status, 400);
});

test('le tri accepte seulement des valeurs connues (pas d\'injection)', async () => {
  const DB = mockDb();
  await worker.fetch(req('/ranking?distance=10k&sort=pb_sec;DROP&dir=x'), { DB });
  const rows = DB.calls.find((c) => /LIMIT \? OFFSET \?/.test(c.sql));
  assert.ok(!/DROP/.test(rows.sql));
  assert.match(rows.sql, /ORDER BY r\.rank ASC/);
});

test('limitation de débit → 429 avec CORS', async () => {
  const RATE_LIMITER = { limit: async () => ({ success: false }) };
  const res = await worker.fetch(req('/health'), { DB: mockDb(), RATE_LIMITER });
  assert.equal(res.status, 429);
  assert.equal(res.headers.get('retry-after'), '60');
  assert.equal(res.headers.get('access-control-allow-origin'), ORIGIN);
});

test('preflight OPTIONS non limité', async () => {
  let called = false;
  const RATE_LIMITER = { limit: async () => { called = true; return { success: false }; } };
  const res = await worker.fetch(req('/search', { method: 'OPTIONS' }), { DB: mockDb(), RATE_LIMITER });
  assert.equal(res.status, 200);
  assert.equal(called, false);
});

test('/match plafonne à 1000 noms par paquets de 80', async () => {
  const DB = mockDb();
  const names = Array.from({ length: 1500 }, (_, i) => 'NOM' + i + ' PRENOM');
  const res = await worker.fetch(req('/match?distance=10k', {
    method: 'POST', body: JSON.stringify({ names }), headers: { 'Content-Type': 'application/json' }
  }), { DB });
  assert.equal(res.status, 200);
  assert.equal(DB.calls.length, Math.ceil(1000 / 80));
  assert.ok(DB.calls.every((c) => c.binds.length <= 81));
});

test('/match avec JSON invalide → 400', async () => {
  const res = await worker.fetch(req('/match?distance=10k', { method: 'POST', body: '{oops' }), { DB: mockDb() });
  assert.equal(res.status, 400);
});

// --- Cache des réponses -----------------------------------------------------
function withFakeCache(fn) {
  const store = new Map();
  globalThis.caches = { default: {
    async match(req) { const r = store.get(req.url); return r ? r.clone() : undefined; },
    async put(req, res) { store.set(req.url, res); }
  } };
  return fn(store).finally(() => { delete globalThis.caches; });
}
const ctx = { waitUntil() {} };

test('cache : la 2e requête identique ne touche pas la base, même avec les paramètres dans un autre ordre', () => withFakeCache(async (store) => {
  const DB = mockDb();
  const r1 = await worker.fetch(req('/ranking?distance=10k&sex=F&page=2'), { DB }, ctx);
  assert.equal(r1.status, 200);
  assert.match(r1.headers.get('cache-control'), /max-age=300/);
  const calls = DB.calls.length;
  const r2 = await worker.fetch(req('/ranking?page=2&sex=F&distance=10k'), { DB }, ctx);
  assert.equal(r2.status, 200);
  assert.equal(DB.calls.length, calls);
  assert.equal(r2.headers.get('access-control-allow-origin'), ORIGIN);
  assert.equal(store.size, 1);
}));

test('cache : erreurs, /health et /match ne sont pas mis en cache', () => withFakeCache(async (store) => {
  const DB = mockDb();
  await worker.fetch(req('/ranking?distance=42k'), { DB }, ctx);
  await worker.fetch(req('/health'), { DB }, ctx);
  await worker.fetch(req('/match?distance=10k', { method: 'POST', body: JSON.stringify({ names: ['DUPONT JEAN'] }) }), { DB }, ctx);
  assert.equal(store.size, 0);
}));

test('filtre saison : de 2024 à la saison en cours', async () => {
  const seasonBind = async (iso, season) => {
    mock.timers.enable({ apis: ['Date'], now: new Date(iso) });
    try {
      const DB = mockDb();
      await worker.fetch(req(`/ranking?distance=10k&seasonYear=${season}`), { DB });
      return DB.calls.some((c) => /substr\(a\.pb_date/.test(c.sql) && c.binds.includes(season));
    } finally { mock.timers.reset(); }
  };
  assert.equal(await seasonBind('2026-11-04T12:00:00Z', 2027), true);   // saison en cours
  assert.equal(await seasonBind('2026-11-04T12:00:00Z', 2024), true);
  assert.equal(await seasonBind('2026-11-04T12:00:00Z', 2023), false);  // avant la collecte
  assert.equal(await seasonBind('2026-11-04T12:00:00Z', 2028), false);  // future
  assert.equal(await seasonBind('2027-10-01T12:00:00Z', 2028), true);
});
