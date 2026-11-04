// Tests du Worker avec une base D1 simulée (aucun accès réseau).
import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../cloudflare-prototype/worker.js';

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

test('category=M1 filtre sur les bonnes années de naissance', async () => {
  const DB = mockDb();
  await worker.fetch(req('/ranking?distance=10k&category=M1'), { DB });
  const count = DB.calls.find((c) => /COUNT\(\*\)/.test(c.sql));
  const season = new Date().getMonth() >= 8 ? new Date().getFullYear() + 1 : new Date().getFullYear();
  assert.deepEqual(count.binds, ['10k', season - 44, season - 40]);
});

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
