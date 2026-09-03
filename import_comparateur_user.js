// ==UserScript==
// @name         Importer vers Comparateur 10km
// @namespace    comparateur-10km-ffa
// @version      1.1
// @description  Collecte un classement GoTiming ou UTMB complet et l'envoie vers RP.
// @match        https://*.gotiming.fr/*
// @match        https://gotiming.fr/*
// @match        https://*.utmb.world/*
// @match        https://utmb.world/*
// @run-at       document-idle
// @inject-into  page
// ==/UserScript==

(function () {
  'use strict';

  var C = function (s) { return (s || '').toString().replace(/\s+/g, ' ').trim(); };
  var norm = function (s) { return C(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase(); };
  var uniq = function (a) {
    var m = new Map();
    for (var i = 0; i < a.length; i++) {
      var x = a[i];
      if (!x || !x.name) continue;
      var k = [x.rank, x.name, x.time].join('|');
      if (!m.has(k)) m.set(k, x);
    }
    return [].concat.apply([], [[...m.values()]]);
  };

  // ---------- UTMB ----------
  function parseNextJSON(doc) {
    var scripts = [].slice.call(doc.querySelectorAll('script[type="application/json"]'));
    if (!scripts.length) throw new Error('UTMB : JSON interne introuvable.');
    var best = '', len = 0;
    for (var i = 0; i < scripts.length; i++) {
      var t = scripts[i].textContent || '';
      if (t.length > len) { best = t; len = t.length; }
    }
    if (!best) throw new Error('UTMB : JSON interne vide.');
    return JSON.parse(best);
  }
  function utmbRows(j) {
    var res = j && j.props && j.props.pageProps && j.props.pageProps.results;
    var arr = res && res.results;
    if (!Array.isArray(arr)) return [];
    var out = [];
    for (var i = 0; i < arr.length; i++) {
      var x = arr[i];
      var sx = x.gender === 'F' ? 'F' : (x.gender === 'H' ? 'M' : C(x.gender));
      var row = { rank: String(x.rank == null ? '' : x.rank), time: C(x.time), name: C(x.fullname), sex: sx, category: C(x.ageGroup), uri: C(x.runnerUri), nationality: C(x.nationality), score: (x.index == null ? '' : String(x.index)) };
      if (row.rank && row.name && row.time) out.push(row);
    }
    return out;
  }
  function cacheGet(key) { try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; } }
  function cacheSet(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {} }
  function rowsLookValid(rows, p, limit) {
    if (!rows || !rows.length) return false;
    var expected = (p - 1) * limit + 1;
    var firstRank = Number(rows[0].rank) || 0;
    return Math.abs(firstRank - expected) <= limit;
  }
  async function fetchUtmbPage(base, p, cacheBase, limit) {
    var key = cacheBase + '_p' + p;
    var cached = cacheGet(key);
    if (cached && rowsLookValid(cached, p, limit)) return cached;
    var u = new URL(base.href); if (p > 1) u.searchParams.set('page', String(p));
    for (var attempt = 1; attempt <= 3; attempt++) {
      var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 10000);
      try {
        var r = await fetch(u.href, { credentials: 'include', cache: 'no-store', signal: controller.signal });
        clearTimeout(timer);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        var d = new DOMParser().parseFromString(await r.text(), 'text/html');
        var rows = utmbRows(parseNextJSON(d));
        if (rowsLookValid(rows, p, limit)) { cacheSet(key, rows); return rows; }
        return rows;
      } catch (e) {
        clearTimeout(timer);
        await new Promise(function (res) { setTimeout(res, 500 * attempt); });
      }
    }
    return cached || [];
  }
  async function scanUTMB(setStatus) {
    var first = parseNextJSON(document);
    var res = (first.props && first.props.pageProps && first.props.pageProps.results) || {};
    var total = Number(res.nbHits || 0), limit = Number(res.limit || 25) || 25;
    var pages = Math.max(1, Math.ceil(total / limit));
    var curUrl = new URL(location.href), cur = Number(curUrl.searchParams.get('page') || 1);
    var base = new URL(curUrl.href); base.searchParams.delete('page');
    var cacheBase = 'utmbc4_' + base.pathname + base.search;
    var firstRows = utmbRows(first);
    if (rowsLookValid(firstRows, cur, limit)) cacheSet(cacheBase + '_p' + cur, firstRows);
    var all = firstRows.slice();
    var pageNums = [];
    for (var p = 1; p <= pages; p++) { if (p !== cur) pageNums.push(p); }
    var idx = 0, CONC = 5, done = 1;
    async function worker() {
      while (idx < pageNums.length) {
        var pn = pageNums[idx++];
        var rows = await fetchUtmbPage(base, pn, cacheBase, limit);
        all = all.concat(rows);
        done++;
        if (setStatus) setStatus(done + '/' + pages + ' pages UTMB — ' + all.length + ' lignes brutes');
      }
    }
    var workers = [];
    for (var w = 0; w < CONC; w++) workers.push(worker());
    await Promise.all(workers);
    var rowsOut = uniq(all).sort(function (a, b) { return (Number(a.rank) || 999999) - (Number(b.rank) || 999999); });
    if (!rowsOut.length) throw new Error('UTMB : aucune donnee recuperee.');
    return rowsOut;
  }

  // ---------- GoTiming ----------
  function domTableGoTiming() {
    var tables = [].slice.call(document.querySelectorAll('table'));
    var best = [];
    for (var t = 0; t < tables.length; t++) {
      var table = tables[t];
      var trs = [].slice.call(table.querySelectorAll('tr'));
      if (trs.length < 2) continue;
      var headerRow = -1, headers = [];
      for (var i = 0; i < Math.min(20, trs.length); i++) {
        var cells = [].slice.call(trs[i].querySelectorAll('th,td')).map(function (c) { return norm(c.textContent); });
        var joined = cells.join('|');
        if (/NOM|ATHLETE|COUREUR|NAME/.test(joined) && /TEMPS|CHRONO|RESULTAT|TIME/.test(joined)) { headerRow = i; headers = cells; break; }
      }
      if (headerRow < 0) continue;
      var idxName = -1, idxTime = -1, idxRank = -1, idxSex = -1, idxCat = -1;
      for (var h = 0; h < headers.length; h++) {
        var hh = headers[h];
        if (idxName < 0 && /NOM|ATHLETE|COUREUR|NAME/.test(hh)) idxName = h;
        if (idxTime < 0 && /TEMPS|CHRONO|RESULTAT|TIME/.test(hh)) idxTime = h;
        if (idxRank < 0 && /PLACE|POS|RANG|CLASSEMENT/.test(hh)) idxRank = h;
        if (idxSex < 0 && /SEXE|GENRE|^SEX$/.test(hh)) idxSex = h;
        if (idxCat < 0 && /^CAT/.test(hh)) idxCat = h;
      }
      if (idxName < 0 || idxTime < 0) continue;
      var out = [];
      for (var r = headerRow + 1; r < trs.length; r++) {
        var tds = [].slice.call(trs[r].children).filter(function (c) { return c.tagName === 'TD' || c.tagName === 'TH'; }).map(function (c) { return C(c.textContent); });
        if (!tds.length) continue;
        var name = tds[idxName] || '', time = tds[idxTime] || '';
        if (!name || !time) continue;
        out.push({ rank: tds[idxRank] || '', time: time, name: name, sex: idxSex >= 0 ? (tds[idxSex] || '') : '', category: idxCat >= 0 ? (tds[idxCat] || '') : '', uri: '', nationality: '', score: '' });
      }
      if (out.length > best.length) best = out;
    }
    return best;
  }
  function textScanGoTiming() {
    var lines = (document.body ? document.body.innerText : '').split(/\n+/).map(C).filter(Boolean);
    var out = [], rankRe = /^(\d{1,5})\.$/, timeRe = /^(?:\d{1,2}:)?\d{1,2}:\d{2}$/;
    for (var i = 0; i < lines.length; i++) {
      var rm = lines[i].match(rankRe); if (!rm) continue;
      var rank = rm[1], name = lines[i + 1] || '';
      if (!/[A-Za-z\u00c0-\u00ff]{2,}/.test(name)) continue;
      var time = '', cat = '', sex = '', end = -1;
      for (var j = i + 2; j <= Math.min(lines.length - 1, i + 7); j++) {
        var v = lines[j];
        if (/Homme|Femme|Male|Female/i.test(v)) { cat = v; sex = /Femme|Female/i.test(v) ? 'F' : 'M'; }
        if (timeRe.test(v)) { time = v; end = j; break; }
      }
      if (!time) continue;
      out.push({ rank: rank, time: time, name: name, sex: sex, category: cat, uri: '', nationality: '', score: '' });
      i = end;
    }
    return out;
  }
  async function scanGoTiming(setStatus) {
    var dom = domTableGoTiming();
    // G-Live limite l'affichage mobile à 100 lignes, mais son propre mode
    // export sait générer le classement complet dans le tableau courant.
    if (typeof grilleGen === 'function') {
      if (setStatus) setStatus('Chargement du classement complet GoTiming…');
      await grilleGen(0, 1);
      await new Promise(function (resolve) { requestAnimationFrame(resolve); });
      dom = domTableGoTiming();
    }
    if (dom.length) return uniq(dom);
    return uniq(textScanGoTiming());
  }

  // ---------- Construction du texte + envoi ----------
  function buildText(source, rows) {
    if (source === 'UTMB') {
      var lines = [];
      for (var i = 0; i < rows.length; i++) {
        var x = rows[i];
        var g = String(x.sex).toUpperCase() === 'F' ? 'Femme' : 'Homme';
        var nm = x.uri ? ('[' + x.name + '](https://utmb.world/fr/runner/' + x.uri + ')') : x.name;
        var nat = x.nationality || '-';
        var score = (x.score === 0 || x.score) ? String(x.score) : '-';
        lines.push([x.rank, x.time, nm, nat, g, x.category || '-', score].join('\n'));
      }
      return lines.join('\n');
    }
    var lines2 = [];
    for (var i2 = 0; i2 < rows.length; i2++) {
      var x2 = rows[i2];
      var line = (x2.rank || '') + '  ' + (x2.name || '') + '  ' + (x2.time || '');
      if (x2.category) line += '  ' + x2.category;
      lines2.push(line);
    }
    return lines2.join('\n');
  }

  // ---------- Interface : bouton flottant + overlay de progression ----------
  function hasScannableContent() {
    var host = location.hostname.toLowerCase();
    if (host.indexOf('utmb.world') >= 0) {
      return document.querySelectorAll('script[type="application/json"]').length > 0;
    }
    if (host.indexOf('gotiming.fr') >= 0) {
      return domTableGoTiming().length > 0 || textScanGoTiming().length > 0;
    }
    return false;
  }

  function ensureUI() {
    if (document.getElementById('c10k-import-btn')) return;
    if (!hasScannableContent()) return;
    var btn = document.createElement('button');
    btn.id = 'c10k-import-btn';
    btn.textContent = '📤 Importer vers Comparateur';
    btn.style.cssText = 'position:fixed;z-index:2147483647;right:16px;bottom:16px;background:#c0392b;color:#fff;font:600 14px system-ui;border:0;border-radius:999px;padding:12px 18px;box-shadow:0 6px 20px #0006;cursor:pointer';
    document.body.appendChild(btn);

    var overlay = document.createElement('div');
    overlay.id = 'c10k-import-overlay';
    overlay.style.cssText = 'display:none;position:fixed;z-index:2147483647;right:16px;bottom:70px;width:320px;max-width:88vw;background:#111;color:#fff;padding:14px;border-radius:12px;font:13px system-ui;box-shadow:0 8px 30px #0008;white-space:pre-line';
    document.body.appendChild(overlay);

    btn.addEventListener('click', async function () {
      overlay.style.display = 'block';
      overlay.textContent = 'Analyse de la page…';
      btn.disabled = true;
      // Ouvre l'onglet immédiatement (dans le prolongement du tap) pour que
      // Safari ne bloque pas l'ouverture une fois la collecte terminée.
      var newTab = window.open('', '_blank');
      try {
        var host = location.hostname.toLowerCase();
        var source = '', rows = [];
        if (host.indexOf('utmb.world') >= 0) {
          source = 'UTMB';
          rows = await scanUTMB(function (msg) { overlay.textContent = msg; });
        } else if (host.indexOf('gotiming.fr') >= 0) {
          source = 'GoTiming';
          rows = await scanGoTiming(function (msg) { overlay.textContent = msg; });
        } else {
          throw new Error('Site non reconnu.');
        }
        if (!rows.length) throw new Error('Aucun participant reconnu sur cette page.');
        overlay.textContent = rows.length + ' participants collectés. Ouverture du comparateur…';
        var text = buildText(source, rows);
        var b64 = btoa(unescape(encodeURIComponent(text)));
        var url = 'https://shurikn57.github.io/10km-FFA/mobile.html#import64=' + b64;
        if (newTab) { newTab.location.href = url; }
        else { window.open(url, '_blank'); }
        overlay.textContent = rows.length + ' participants envoyés dans un nouvel onglet.';
        btn.disabled = false;
      } catch (e) {
        if (newTab) { try { newTab.close(); } catch (e2) {} }
        overlay.textContent = 'Erreur : ' + (e && e.message ? e.message : e);
        btn.disabled = false;
      }
    });
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    ensureUI();
  } else {
    document.addEventListener('DOMContentLoaded', ensureUI);
  }
  // Certains sites (UTMB) chargent le contenu en JS après coup : on garde le bouton présent.
  setInterval(ensureUI, 2000);
})();
