const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('./load-core')();

test('chronoFromSec formate minutes et heures', () => {
  assert.equal(core.chronoFromSec(1985), "33'05");
  assert.equal(core.chronoFromSec(4406), "1h13'26");
  assert.equal(core.chronoFromSec(0), "0'00");
  assert.equal(core.chronoFromSec('abc'), "0'00");
});

test('secFromTime lit les formats courants', () => {
  assert.equal(core.secFromTime("33'05"), 1985);
  assert.equal(core.secFromTime("1h13'26"), 4406);
  assert.equal(core.secFromTime('1:13:26'), 4406);
  assert.equal(core.secFromTime('33:05'), 1985);
  assert.equal(core.secFromTime('33’05'), 1985);
  assert.equal(core.secFromTime('DNF'), null);
  assert.equal(core.secFromTime('Abandon'), null);
  assert.equal(core.secFromTime(''), null);
});

test('chronoFromSec et secFromTime sont réciproques', () => {
  for (const s of [59, 600, 1985, 3599, 3600, 4406, 10799]) {
    assert.equal(core.secFromTime(core.chronoFromSec(s)), s);
  }
});

test('nameKey ignore accents, casse, ponctuation et ordre des mots', () => {
  assert.equal(core.nameKey('DUPONT Jean'), core.nameKey('jean dupont'));
  assert.equal(core.nameKey('ÉLODIE Lefèvre'), core.nameKey('Lefevre Elodie'));
  assert.equal(core.nameKey("D'ARTAGNAN Jean-Pierre"), core.nameKey('jean pierre d artagnan'));
  assert.equal(core.nameKey(''), '');
});

test('fmtDelta', () => {
  assert.equal(core.fmtDelta(65), "+1'05");
  assert.equal(core.fmtDelta(-5), '-05');
  assert.equal(core.fmtDelta(0), '+00');
  assert.equal(core.fmtDelta(null), '');
});

test('splitFullName sépare NOM en majuscules et prénom', () => {
  assert.deepEqual([...core.splitFullName('DUPONT Jean')], ['DUPONT', 'Jean']);
  assert.deepEqual([...core.splitFullName('DE LA FONTAINE Jean Marie')], ['DE LA FONTAINE', 'Jean Marie']);
  assert.deepEqual([...core.splitFullName('Dupont Jean')], ['Dupont', 'Jean']);
  assert.deepEqual([...core.splitFullName('DUPONT')], ['DUPONT', '']);
});

test('ffaSeasonYear bascule au 1er septembre (heure de Paris)', () => {
  assert.equal(core.ffaSeasonYear(new Date('2026-08-31T12:00:00Z')), 2026);
  assert.equal(core.ffaSeasonYear(new Date('2026-09-01T12:00:00Z')), 2027);
  // 31 août 23h30 UTC = 1er septembre 1h30 à Paris
  assert.equal(core.ffaSeasonYear(new Date('2026-08-31T23:30:00Z')), 2027);
  assert.equal(core.ffaSeasonYear(new Date('2027-01-15T12:00:00Z')), 2027);
});

test('ffaCategoryFromBirthYear : saison 2027', () => {
  const cat = (y) => core.ffaCategoryFromBirthYear(y, 2027);
  assert.equal(cat(2011), 'CA');
  assert.equal(cat(2010), 'CA');
  assert.equal(cat(2009), 'JU');
  assert.equal(cat(2007), 'ES');
  assert.equal(cat(2004), 'SE');
  assert.equal(cat(1993), 'SE');
  assert.equal(cat(1992), 'M0');
  assert.equal(cat(1983), 'M1');
  assert.equal(cat(1943), 'M9');
  assert.equal(cat(1942), 'M10');
  assert.equal(cat(1920), 'M10');
  assert.equal(cat(2015), '');
  assert.equal(cat(''), '');
  assert.equal(cat(null), '');
});

test('ffaCategoryFromBirthYear : saison 2026 (avant septembre)', () => {
  const cat = (y) => core.ffaCategoryFromBirthYear(y, 2026);
  assert.equal(cat(2003), 'SE');
  assert.equal(cat(1992), 'SE');
  assert.equal(cat(1991), 'M0');
  assert.equal(cat(1941), 'M10');
});

test('les tranches de catégories sont contiguës et sans trou', () => {
  const t = core.FFA_SEASON_CATEGORY_AGES;
  for (let i = 1; i < t.length; i++) assert.equal(t[i][1], t[i - 1][2] + 1, t[i][0]);
  assert.equal(t[t.length - 1][2], null);
});

test('ffaCategoryToYearRange : codes compacts et libellés GoTiming', () => {
  const y = new Date().getFullYear();
  assert.deepEqual({ ...core.ffaCategoryToYearRange('M1H') }, { min: y - 44, max: y - 40 });
  assert.deepEqual({ ...core.ffaCategoryToYearRange('SEF') }, { min: y - 34, max: y - 23 });
  assert.deepEqual({ ...core.ffaCategoryToYearRange('7° Masters 0 Homme') }, { min: y - 39, max: y - 35 });
  assert.equal(core.ffaCategoryToYearRange('XYZ'), null);
});

test('utmbCategoryToYearRange', () => {
  const y = new Date().getFullYear();
  assert.deepEqual({ ...core.utmbCategoryToYearRange('40-44') }, { min: y - 44, max: y - 40 });
  assert.deepEqual({ ...core.utmbCategoryToYearRange('70+') }, { min: 1900, max: y - 70 });
  assert.equal(core.utmbCategoryToYearRange('V1'), null);
});

test('parseCSV détecte le séparateur et gère les guillemets', () => {
  const rows = core.parseCSV('﻿Place;Nom;Temps\n1;"DUPONT; Jean";33:05\n2;MARTIN Paul;34:10\n');
  assert.equal(rows.length, 2);
  assert.equal(rows[0].NOM, 'DUPONT; Jean');
  assert.equal(rows[1].TEMPS, '34:10');
  const tab = core.parseCSV('Nom\tTemps\nDUPONT Jean\t33:05');
  assert.equal(tab[0].NOM, 'DUPONT Jean');
});

test('rowsToRace découpe la colonne Nom GoTiming', () => {
  const race = core.rowsToRace(core.parseCSV('Place;Nom;Temps;Cat\n1;DUPONT Jean;33:05;M1H'));
  assert.equal(race.length, 1);
  assert.equal(race[0].nom, 'DUPONT');
  assert.equal(race[0].prenom, 'Jean');
  assert.ok(race[0].anneeRange);
});

test('esc échappe le HTML', () => {
  assert.equal(core.esc('<a href="x">\'&'), '&lt;a href=&quot;x&quot;&gt;&#39;&amp;');
  assert.equal(core.esc(null), '');
});

// --- Matching -----------------------------------------------------------
const ffa = [
  { full_name: 'DUPONT Jean', annee_naissance: '1985', pb_sec: 2100, athlete_ffa_id: 'A1' },
  { full_name: 'MARTIN Paul', annee_naissance: '1990', pb_sec: 2000, athlete_ffa_id: 'B1' },
  { full_name: 'MARTIN Paul', annee_naissance: '1970', pb_sec: 2500, athlete_ffa_id: 'B2' },
  { full_name: 'DURAND Luc', annee_naissance: '1980', pb_sec: 2200, athlete_ffa_id: 'C1' },
  { full_name: 'DURAND Luc', annee_naissance: '1980', pb_sec: 2150, athlete_ffa_id: 'C1' }
];
const runner = (nom, prenom, temps, extra = {}) => ({ pos: '1', nom, prenom, temps, cat: '', annee: '', anneeRange: null, ...extra });

test('computeResults : nom unique → exact avec écart', () => {
  const [r] = core.computeResults([runner('Dupont', 'Jean', '34:00')], ffa);
  assert.equal(r.status, 'exact');
  assert.equal(r.p.athlete_ffa_id, 'A1');
  assert.equal(r.delta, 2040 - 2100);
});

test('computeResults : homonymes sans année → ambigu', () => {
  const [r] = core.computeResults([runner('MARTIN', 'Paul', '35:00')], ffa);
  assert.equal(r.status, 'ambiguous');
  assert.equal(r.p, null);
  assert.equal(r.delta, null);
});

test('computeResults : homonymes départagés par l\'année', () => {
  const [r] = core.computeResults([runner('MARTIN', 'Paul', '35:00', { annee: '1970' })], ffa);
  assert.equal(r.status, 'exact');
  assert.equal(r.p.athlete_ffa_id, 'B2');
});

test('computeResults : doublons même ID → meilleur PB retenu', () => {
  const [r] = core.computeResults([runner('DURAND', 'Luc', '36:00')], ffa);
  assert.equal(r.status, 'exact');
  assert.equal(r.p.pb_sec, 2150);
});

test('computeResults : catégorie incompatible → rétrogradé en ambigu', () => {
  const [r] = core.computeResults([runner('DUPONT', 'Jean', '34:00', { anneeRange: { min: 2000, max: 2005 }, cat: 'ESH' })], ffa);
  assert.equal(r.status, 'ambiguous');
  assert.match(r.matchDetail, /incompatible/);
});

test('computeResults : inconnu → none', () => {
  const [r] = core.computeResults([runner('INCONNU', 'Personne', '40:00')], ffa);
  assert.equal(r.status, 'none');
});
