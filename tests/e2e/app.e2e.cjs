// Test de bout en bout de l'app (mobile.html) dans Chromium, avec l'API
// Cloudflare simulée. Lancer : npm run test:e2e  (nécessite Playwright).
const { chromium, devices } = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const ROOT = path.join(__dirname, '..', '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png' };

function serve() {
  const server = http.createServer((req, res) => {
    const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
    if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
    fs.createReadStream(p).pipe(res);
  });
  return new Promise((ok) => server.listen(0, () => ok(server)));
}

const athlete = (name, i, distance) => ({ full_name: name, birth_year: 1980 + (i % 20), sex: i % 2 ? 'F' : 'M', pb_sec: 1800 + i * 7, pb_course: 'Course ' + distance, pb_date: '12/10/25', club: 'Club ' + (i % 3), athlete_ffa_id: 'ID' + i, rank: i + 1 });

async function main() {
  const server = await serve();
  const base = `http://localhost:${server.address().port}`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ ...devices['iPhone 13'] });
  const errors = [];
  const api = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.route(/workers\.dev/, async (route) => {
    const u = new URL(route.request().url());
    const d = u.searchParams.get('distance');
    api.push(u.pathname + ' ' + d);
    let body;
    if (u.pathname === '/search') body = { rows: [athlete('DUPONT Jean', 0, d), athlete('DUPONT Marie', 1, d)] };
    else if (u.pathname === '/ranking') body = { page: 1, pageSize: 100, total: 3, pages: 1, rows: [0, 1, 2].map((i) => athlete('COUREUR ' + d + ' ' + i, i, d)) };
    else if (u.pathname === '/ranking-options') body = { rows: [{ league: 'I-F', department: '077', club: 'Club 0', race_year: 2025 }] };
    else if (u.pathname === '/match') {
      const { names } = JSON.parse(route.request().postData());
      body = { rows: names.filter((n) => /^DUPONT JEAN$/.test(n)).map(() => ({ ...athlete('DUPONT Jean', 0, d), birth_year: 1984, pb_sec: d === '5k' ? 900 : 2000 })) };
    } else body = { error: 'not_found' };
    await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(body) });
  });

  await page.goto(base + '/mobile.html');

  // 1. Recherche
  await page.fill('#ffaAthleteSearch', 'dupont');
  await page.waitForFunction(() => /profils? trouvés?/.test(document.getElementById('ffaAthleteSearchMsg').textContent));
  assert.match(await page.textContent('#ffaAthleteSearchResults'), /DUPONT Jean/);

  // 2. Changement de distance dans Recherche : nouvelle requête, sans rechargement
  await page.click('[data-distance="semi"]');
  await page.waitForFunction(() => location.search.includes('distance=semi'));
  await page.waitForTimeout(400);
  assert.ok(api.includes('/search semi'), 'recherche relancée sur le semi');

  // 3. Classement
  await page.click('[data-app-tab="classement"]');
  await page.waitForFunction(() => /COUREUR semi/.test(document.getElementById('ffaFullResults').textContent));
  await page.click('[data-distance="marathon"]');
  await page.waitForFunction(() => /COUREUR marathon/.test(document.getElementById('ffaFullResults').textContent));
  await page.click('[data-ffa-sex="F"]');
  await page.waitForTimeout(500);

  // 4. Analyse par import (hash #import64 du userscript), puis changement de distance
  const text = '1  DUPONT Jean  0:35:00  M1H\n2  INCONNU Paul  0:36:00';
  const b64 = Buffer.from(unescape(encodeURIComponent(text)), 'binary').toString('base64');
  await page.evaluate((h) => { location.hash = 'import64=' + h; dispatchEvent(new HashChangeEvent('hashchange')); }, b64);
  await page.waitForFunction(() => /correspondances FFA/.test(document.getElementById('raceMsg').textContent), null, { timeout: 5000 }).catch(async () => {
    // certaines versions ne réagissent qu'au chargement : on recharge avec le hash
    await page.goto(base + '/mobile.html?distance=marathon#import64=' + b64);
    await page.waitForFunction(() => /correspondances FFA/.test(document.getElementById('raceMsg').textContent));
  });
  assert.equal(await page.textContent('#sTotal'), '2');
  assert.equal(await page.textContent('#sExact'), '1');
  // Un rechargement de page effacerait ce marqueur.
  await page.evaluate(() => { window.__noReload = true; });
  await page.click('[data-distance="5k"]');
  await page.waitForFunction(() => location.search.includes('distance=5k'));
  await page.waitForFunction(() => /15'00/.test(document.getElementById('tbody').textContent));
  assert.equal(await page.evaluate(() => window.__noReload), true, 'pas de rechargement de page en changeant de distance dans Analyse');
  assert.ok(api.includes('/match 5k'), 'course recomparée sur le 5 km');

  // 5. Import compressé (script v1.4) d'une grosse course : la compression est
  //    faite par la fonction du userscript lui-même, dans le navigateur.
  const script = fs.readFileSync(path.join(ROOT, 'tools', 'import_comparateur_user.js'), 'utf8');
  const deflateSrc = script.slice(script.indexOf('async function deflateBase64Url'), script.indexOf('// ---------- Interface'));
  const bigRace = Array.from({ length: 3000 }, (_, i) => `${i + 1}  COUREUR${i} Prénom${i}  0:${String(30 + (i % 29)).padStart(2, '0')}:${String(i % 60).padStart(2, '0')}  SEH`).join('\n')
    + '\n3001  DUPONT Jean  0:35:00  M1H';
  const packed = await page.evaluate(async ({ src, text }) => { const f = new Function(src + '; return deflateBase64Url;')(); return f(text); }, { src: deflateSrc, text: bigRace });
  assert.ok(packed && packed.length < bigRace.length / 2, 'classement compressé (' + (packed && packed.length) + ' car. pour ' + bigRace.length + ')');
  await page.goto(base + '/mobile.html?distance=10k#importz=' + packed);
  await page.waitForFunction(() => /3001 participants détectés/.test(document.getElementById('raceMsg').textContent));
  await page.waitForFunction(() => /correspondances FFA\./.test(document.getElementById('raceMsg').textContent));
  assert.equal(await page.textContent('#sTotal'), '3001');
  assert.equal(await page.evaluate(() => location.hash), '', 'hash nettoyé après import');

  // 6. Restaurer le dernier classement après rechargement
  await page.goto(base + '/mobile.html');
  await page.click('[data-app-tab="analyse"]');
  await page.click('#restoreBtn');
  await page.waitForFunction(() => document.getElementById('sTotal').textContent === '3001');

  assert.deepEqual(errors, [], 'aucune erreur JavaScript');
  console.log('OK — e2e : recherche, classement, filtres, distances, import, import compressé de 3001 coureurs, restauration (' + api.length + ' appels API simulés)');
  await browser.close();
  server.close();
}
main().catch((e) => { console.error(e); process.exit(1); });
