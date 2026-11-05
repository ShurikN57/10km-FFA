"""Tests de tools/build_db.py : référence, contrôle des exports, fusion, construction."""
import gzip
import itertools
import json
import random
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_db as b  # noqa: E402


def profile(name, pb, birth=1985, sex='M', ffa_id=None, date='12/10/25', club='Club', league=None, dept=None):
    return {'full_name': name, 'birth_year': birth, 'sex': sex, 'pb_sec': pb, 'pb_date': date, 'club': club,
            'athlete_ffa_id': ffa_id, 'league': league, 'department': dept}


def perf(name, pb, **kw):
    p = profile(name, pb, **kw)
    p['season'] = 2027
    return p


def empty():
    return {k: [] for k, _, _ in b.DISTANCES}


def raw_row(time, name, birth='1990', ffa_id='', club='Club', date='12/10/26'):
    return [time, name, club, 'I-F', '077', '', date, 'Lieu', birth, ffa_id]


def write_exports(directory, seasons=(2027,), rows=None, mutate=None):
    """Écrit un jeu complet d'exports bruts (4 distances × saisons × H/F)."""
    paths = []
    for key, label, _ in b.DISTANCES:
        event = {v: k for k, v in b.EVENT_DISTANCE.items()}[key]
        datasets = [{'year': y, 'sex': s, 'rows': (rows or {}).get((key, y, s), [raw_row("40'00''" if key in ('5k', '10k') else '2h30\'00\'\'', f'COUREUR {key} {s}')])}
                    for y in seasons for s in ('M', 'F')]
        doc = {'schema_version': 3, 'seasons': list(seasons), 'distance': label, 'event': event, 'datasets': datasets}
        if mutate:
            doc = mutate(key, doc)
            if doc is None:
                continue
        path = Path(directory) / f'ffa_{label}_{seasons[0]}.json.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            json.dump(doc, f)
        paths.append(path)
    return paths


class ParseTests(unittest.TestCase):
    def test_parse_time(self):
        for text, sec in [("33'05''", 1985), ("1h13'26''", 4406), ("2h05'30''", 7530), ('1:13:26', 4406),
                          ('33:05', 1985), ("33'05'' (+0,3)", 1985), ('2h05', 7500), ('', None), ('DNF', None)]:
            self.assertEqual(b.parse_time(text), sec, text)

    def test_parse_date(self):
        self.assertEqual(b.parse_date('5/9/26'), '05/09/26')
        self.assertEqual(b.parse_date('12/10/2026'), '12/10/26')
        self.assertIsNone(b.parse_date(''))

    def test_category(self):
        self.assertEqual(b.category(1993, 2027), 'SE')
        self.assertEqual(b.category(1992, 2027), 'M0')
        self.assertEqual(b.category(2012, 2027), None)  # minime : pas classé
        self.assertEqual(b.category(None, 2027), None)


class RawExportValidationTests(unittest.TestCase):
    def check(self, mutate=None, seasons=(2027,), expect=None, paths_filter=None):
        with tempfile.TemporaryDirectory() as d:
            paths = write_exports(d, seasons=seasons, mutate=mutate)
            if paths_filter:
                paths = paths_filter(paths)
            if expect is None:
                perfs, report = b.load_raw(paths, [2027])
                return perfs, report
            with self.assertRaises(b.InputError) as ctx:
                b.load_raw(paths, [2027])
            self.assertIn(expect, str(ctx.exception))

    def test_jeu_complet_accepte(self):
        perfs, report = self.check()
        self.assertEqual({k: len(v) for k, v in perfs.items()}, {'5k': 2, '10k': 2, 'semi': 2, 'marathon': 2})
        self.assertEqual(report['unreadable'], 0)

    def test_fichier_sans_aucun_bilan_refuse(self):
        self.check(lambda k, d: {**d, 'datasets': []} if k == 'semi' else d, expect='manquants')

    def test_version_de_schema_incorrecte_refusee(self):
        self.check(lambda k, d: {**d, 'schema_version': 2} if k == '10k' else d, expect='version de schéma')

    def test_bilan_femmes_manquant_refuse(self):
        self.check(lambda k, d: {**d, 'datasets': [x for x in d['datasets'] if x['sex'] == 'M']} if k == '5k' else d,
                   expect="(2027, 'F')")

    def test_bilan_vide_refuse(self):
        def m(k, d):
            if k == 'marathon':
                d['datasets'][0]['rows'] = []
            return d
        self.check(m, expect='vide')

    def test_distance_manquante_refusee(self):
        self.check(lambda k, d: None if k == 'marathon' else d, expect='export manquant pour la distance marathon')

    def test_distance_en_double_refusee(self):
        self.check(paths_filter=lambda p: p + [p[0]], expect='deuxième export')

    def test_mauvaise_saison_refusee(self):
        self.check(seasons=(2026,), expect='saisons')

    def test_bilan_en_trop_refuse(self):
        def m(k, d):
            if k == '10k':
                d['datasets'].append({'year': 2026, 'sex': 'M', 'rows': [raw_row("40'00''", 'X')]})
            return d
        self.check(m, expect='en trop')

    def test_temps_impossibles_ecartes_sur_toutes_les_distances(self):
        rows = {('5k', 2027, 'M'): [raw_row("10'53''", 'A')], ('10k', 2027, 'M'): [raw_row("22'00''", 'B')],
                ('semi', 2027, 'M'): [raw_row("50'00''", 'C')], ('marathon', 2027, 'M'): [raw_row("1h50'00''", 'D')]}
        with tempfile.TemporaryDirectory() as d:
            perfs, report = b.load_raw(write_exports(d, rows=rows), [2027])
        self.assertEqual(report['too_fast'], 4)
        self.assertEqual({k: len(v) for k, v in perfs.items()}, {'5k': 1, '10k': 1, 'semi': 1, 'marathon': 1})


class MergeTests(unittest.TestCase):
    def merge(self, ref, perfs):
        r, p = empty(), empty()
        r['10k'], p['10k'] = ref, perfs
        out, stats = b.merge(r, p)
        return out['10k'], stats

    def test_meilleur_temps_conserve(self):
        out, stats = self.merge([profile('DUPONT Jean', 2100, ffa_id='1', club='Ancien', league='I-F')],
                                [perf('DUPONT Jean', 2050, ffa_id='1', club='Nouveau', league='PCA', date='01/02/27'),
                                 perf('DUPONT Jean', 2200, ffa_id='1')])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['pb_sec'], out[0]['club'], out[0]['league'], out[0]['pb_date']), (2050, 'Nouveau', 'PCA', '01/02/27'))
        self.assertEqual(stats['improved'], 1)

    def test_temps_plus_lent_ignore(self):
        out, stats = self.merge([profile('DUPONT Jean', 2000, ffa_id='1', club='Ancien')], [perf('DUPONT Jean', 2100, ffa_id='1', club='Nouveau')])
        self.assertEqual((out[0]['pb_sec'], out[0]['club']), (2000, 'Ancien'))
        self.assertEqual(stats['unchanged'], 1)

    def test_homonymes_avec_identifiants_differents_restent_separes(self):
        out, _ = self.merge([profile('MOREAU Alexandre', 3775, ffa_id='A'), profile('MOREAU Alexandre', 2577, ffa_id='B')],
                            [perf('MOREAU Alexandre', 3000, ffa_id='A')])
        self.assertEqual(sorted(p['pb_sec'] for p in out), [2577, 3000])

    def test_sans_identifiant_par_nom_annee_sexe(self):
        # Accents et casse ignorés ; une autre année de naissance = un autre athlète.
        out, _ = self.merge([profile('Éloïse MARTIN', 2500, birth=1990, sex='F')],
                            [perf('ELOISE Martin', 2400, birth=1990, sex='F'), perf('ELOISE MARTIN', 2300, birth=1991, sex='F')])
        self.assertEqual(sorted((p['birth_year'], p['pb_sec']) for p in out), [(1990, 2400), (1991, 2300)])

    def test_identifiant_relie_a_un_profil_sans_identifiant_unique(self):
        out, stats = self.merge([profile('PETIT Luc', 2500)], [perf('PETIT Luc', 2600, ffa_id='9')])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['athlete_ffa_id'], out[0]['pb_sec']), ('9', 2500))
        self.assertEqual(stats['linked_id'], 1)

    def test_deux_nouveaux_identifiants_ne_sont_pas_relies_au_meme_profil(self):
        out, stats = self.merge([profile('PETIT Luc', 2500)], [perf('PETIT Luc', 2600, ffa_id='9'), perf('PETIT Luc', 2700, ffa_id='10')])
        self.assertEqual(stats['linked_id'], 0)
        self.assertEqual(sorted((p['athlete_ffa_id'] or '-', p['pb_sec']) for p in out), [('-', 2500), ('10', 2700), ('9', 2600)])

    def test_resultat_sans_identifiant_rattache_au_profil_identifie_unique(self):
        out, _ = self.merge([profile('BITTEROLF Thomas', 7000, ffa_id='3611328')], [perf('BITTEROLF Thomas', 6900)])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['pb_sec'], out[0]['athlete_ffa_id']), (6900, '3611328'))

    def test_resultat_sans_identifiant_rattache_a_un_nouvel_identifiant_unique(self):
        out, stats = self.merge([], [perf('NOUVEAU Coureur', 2900, ffa_id='5'), perf('NOUVEAU Coureur', 2800)])
        self.assertEqual([(p['athlete_ffa_id'], p['pb_sec']) for p in out], [('5', 2800)])
        self.assertEqual(stats['new'], 1)

    def test_resultat_sans_identifiant_prefere_le_profil_sans_identifiant(self):
        ref = [profile('ADAM Frederic', 14726), profile('ADAM Frederic', 14332, ffa_id='2026257')]
        out, _ = self.merge(ref, [perf('ADAM Frederic', 14000)])
        self.assertEqual([(p['athlete_ffa_id'], p['pb_sec']) for p in out], [(None, 14000), ('2026257', 14332)])

    def test_cas_ambigu_independant_de_l_ordre(self):
        """Cas signalé : deux homonymes identifiés et un résultat sans identifiant.
        Quel que soit l'ordre, le résultat sans identifiant est écarté et signalé."""
        ref = [profile('MOREAU Alexandre', 3775, ffa_id='A'), profile('MOREAU Alexandre', 2577, ffa_id='B')]
        incoming = [perf('MOREAU Alexandre', 2500), perf('MOREAU Alexandre', 3700, ffa_id='A'), perf('AUTRE Coureur', 3000)]
        results = set()
        for order in itertools.permutations(incoming):
            out, stats = self.merge(ref, list(order))
            self.assertEqual(stats['ambiguous'], 1)
            results.add(json.dumps(out, sort_keys=True))
        self.assertEqual(len(results), 1)
        out = json.loads(results.pop())
        self.assertEqual(sorted((p['athlete_ffa_id'] or '-', p['pb_sec']) for p in out), [('-', 3000), ('A', 3700), ('B', 2577)])

    def test_cas_ambigu_avec_un_nouvel_identifiant(self):
        # Un homonyme identifié dans la référence + un nouvel identifiant entrant :
        # le résultat sans identifiant peut appartenir à l'un ou l'autre.
        incoming = [perf('LEROY Paul', 2500), perf('LEROY Paul', 2600, ffa_id='N')]
        for order in itertools.permutations(incoming):
            out, stats = self.merge([profile('LEROY Paul', 2700, ffa_id='R')], list(order))
            self.assertEqual(stats['ambiguous'], 1)
            self.assertEqual(sorted((p['athlete_ffa_id'], p['pb_sec']) for p in out), [('N', 2600), ('R', 2700)])

    def test_graphies_d_un_meme_nom_departagees_independamment_de_l_ordre(self):
        # Même chrono, même date : le nom affiché ne dépend pas de l'ordre d'entrée.
        variants = [perf('Éloïse MARTIN', 2400, birth=1990, sex='F'), perf('ELOISE MARTIN', 2400, birth=1990, sex='F'),
                    perf('Eloise Martin', 2400, birth=1990, sex='F')]
        names = set()
        for order in itertools.permutations(variants):
            out, stats = self.merge([], list(order))
            self.assertEqual((len(out), stats['new']), (1, 1))
            names.add(out[0]['full_name'])
        self.assertEqual(len(names), 1)

    def test_fusion_independante_de_l_ordre_sur_donnees_aleatoires(self):
        rng = random.Random(7)
        names = ['MARTIN Paul', 'DURAND Lea', 'DURAND Léa', 'Durand LEA', 'MOREAU Alexandre', 'PETIT Luc', 'ADAM Chloe', 'ADAM Chloé']
        ref = []
        for i in range(60):
            ref.append(profile(rng.choice(names), 2000 + rng.randrange(50) * 10, birth=1980 + rng.randrange(3),
                               sex=rng.choice('MF'), ffa_id=str(rng.randrange(40)) if rng.random() < 0.6 else None))
        # Unicité des identifiants dans la référence, comme en production.
        seen, unique = set(), []
        for p in ref:
            if p['athlete_ffa_id'] and p['athlete_ffa_id'] in seen:
                continue
            seen.add(p['athlete_ffa_id'])
            unique.append(p)
        ref = unique
        incoming = [perf(rng.choice(names), 1950 + rng.randrange(60) * 10, birth=1980 + rng.randrange(3), sex=rng.choice('MF'),
                         ffa_id=str(rng.randrange(60)) if rng.random() < 0.5 else None,
                         date=rng.choice(['01/10/26', '02/10/26']), club=rng.choice(['A', 'B']))
                    for _ in range(200)]
        reference_out, reference_stats = self.merge(ref, incoming)
        for _ in range(30):
            shuffled = incoming[:]
            rng.shuffle(shuffled)
            out, stats = self.merge(ref, shuffled)
            self.assertEqual(out, reference_out)
            self.assertEqual(stats, reference_stats)

    def test_fusion_idempotente(self):
        ref = [profile('DUPONT Jean', 2100, ffa_id='1')]
        perfs = [perf('DUPONT Jean', 2050, ffa_id='1'), perf('NOUVEAU Coureur', 2900)]
        once, _ = self.merge(ref, perfs)
        twice, _ = self.merge(once, perfs)
        self.assertEqual(once, twice)


class ReferenceTests(unittest.TestCase):
    def test_ecriture_relecture_et_prolongation(self):
        prof = empty()
        prof['10k'] = [profile('DUPONT Jean', 2100, ffa_id='1', league='I-F', dept='077')]
        with tempfile.TemporaryDirectory() as d:
            b.write_reference(prof, [2024, 2025, 2026], d, 'test')
            loaded, seasons = b.load_reference(d)
            self.assertEqual((seasons, loaded['10k']), ([2024, 2025, 2026], prof['10k']))
            # Prolongation : les anciens fichiers sont remplacés.
            b.write_reference(loaded, [2024, 2025, 2026, 2027], d, 'test')
            self.assertEqual(sorted(p.name for p in Path(d).iterdir())[0], 'ffa_10km_2024_2027.json.gz')
            self.assertEqual(len(list(Path(d).iterdir())), 4)
            self.assertEqual(b.load_reference(d)[1], [2024, 2025, 2026, 2027])

    def test_saisons_incoherentes_refusees(self):
        with tempfile.TemporaryDirectory() as d:
            b.write_reference(empty(), [2024, 2025, 2026], d, 'test')
            path = Path(d) / 'ffa_semi_2024_2026.json.gz'
            doc = json.load(gzip.open(path, 'rt'))
            doc['seasons'] = [2024, 2025]
            with gzip.open(path, 'wt') as f:
                json.dump(doc, f)
            with self.assertRaises(b.InputError):
                b.load_reference(d)

    def test_reference_du_depot(self):
        _, seasons = b.load_reference()
        self.assertEqual(seasons, [2024, 2025, 2026])

    def test_saison_deja_dans_la_reference_refusee(self):
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d) / 'ref'
            b.write_reference(empty(), [2024, 2025, 2026], ref, 'test')
            exports = write_exports(d, seasons=(2026,))
            code = b.main(['--out', str(Path(d) / 'x.db'), '--reference', str(ref), '--season', '2026', '--raw', *map(str, exports)])
            self.assertEqual(code, 2)
            self.assertFalse((Path(d) / 'x.db').exists())

    def test_chaine_complete_avec_prolongation(self):
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d) / 'ref'
            prof = empty()
            prof['10k'] = [profile('COUREUR 10k M', 2500, birth=1990)]
            b.write_reference(prof, [2024, 2025, 2026], ref, 'test')
            exports = write_exports(d)
            code = b.main(['--out', str(Path(d) / 'x.db'), '--reference', str(ref), '--season', '2027',
                           '--raw', *map(str, exports), '--write-reference', str(ref)])
            self.assertEqual(code, 0)
            loaded, seasons = b.load_reference(ref)
            self.assertEqual(seasons, [2024, 2025, 2026, 2027])
            self.assertEqual([p['pb_sec'] for p in loaded['10k'] if p['sex'] == 'M'], [2400])  # 40'00'' < 2500 s
            self.assertEqual(len(loaded['marathon']), 2)


class BuildTests(unittest.TestCase):
    def test_tables_derivees(self):
        prof = empty()
        prof['10k'] = [profile('B COUREUR', 2000, ffa_id='1', league='I-F', dept='077'),
                       profile('A COUREUR', 2000, ffa_id='2'),
                       profile('ETRANGER John (GBR)', 1900, ffa_id='3'),
                       profile('C COUREUSE', 2100, sex='F', birth=1960, date='')]
        prof['5k'] = [profile('TROP RAPIDE', 600)]  # < 12 min : écarté
        with tempfile.TemporaryDirectory() as d:
            db, n = b.build(Path(d) / 'ffa.db', prof)
            self.assertEqual(n, 4)
            q = lambda sql: db.execute(sql).fetchall()
            self.assertEqual(q('SELECT full_name, r.rank, r.display_order FROM athletes a JOIN athlete_general_rank r ON r.athlete_id=a.id ORDER BY r.display_order'),
                             [('ETRANGER John (GBR)', 1, 1), ('A COUREUR', 2, 2), ('B COUREUR', 2, 3), ('C COUREUSE', 4, 4)])
            # Rang « français » = rang parmi tous, étrangers exclus de la liste.
            self.assertEqual(q('SELECT a.full_name, f.rank_general FROM athlete_french_rank f JOIN athletes a ON a.id=f.athlete_id ORDER BY 2, 1'),
                             [('A COUREUR', 2), ('B COUREUR', 2), ('C COUREUSE', 4)])
            self.assertEqual(q("SELECT rank_sex FROM athlete_search_rank s JOIN athletes a ON a.id=s.athlete_id WHERE a.sex='F'"), [(1,)])
            self.assertEqual(q("SELECT league, department, race_year FROM athlete_scope s JOIN athletes a ON a.id=s.athlete_id WHERE a.full_name='B COUREUR'"), [('I-F', '077', 2025)])
            self.assertEqual(q("SELECT race_year FROM athlete_scope s JOIN athletes a ON a.id=s.athlete_id WHERE a.full_name='C COUREUSE'"), [(None,)])
            self.assertEqual(q('SELECT distance, total FROM ffa_distance_stats'), [('10k', 4)])
            self.assertEqual(q('SELECT distance, total FROM ffa_french_stats'), [('10k', 3)])
            self.assertEqual(q("SELECT COUNT(*) FROM athlete_fts WHERE athlete_fts MATCH '\"COUREUR\"'"), [(2,)])
            sql = Path(d) / 'ffa.sql'
            b.export_sql(db, sql)
            fresh = sqlite3.connect(':memory:')
            fresh.executescript(sql.read_text(encoding='utf-8'))
            for table, _ in b.EXPORT_TABLES:
                self.assertEqual(fresh.execute(f'SELECT * FROM {table} ORDER BY 1, 2').fetchall(),
                                 db.execute(f'SELECT * FROM {table} ORDER BY 1, 2').fetchall(), table)
            self.assertEqual(fresh.execute("SELECT COUNT(*) FROM athlete_fts WHERE athlete_fts MATCH '\"COUREUR\"'").fetchall(), [(2,)])
            db.close()


if __name__ == '__main__':
    unittest.main()
