-- Schéma COMPLET de la base D1 de production `ffa-comparateur`.
-- Extrait de sqlite_master le 2026-11-04 (lecture seule, via l'API Cloudflare).
-- Les tables internes de FTS5 (athlete_fts_config, _content, _data, _docsize,
-- _idx) sont créées automatiquement par CREATE VIRTUAL TABLE et ne figurent pas ici.
--
-- Ce fichier décrit la STRUCTURE seulement. Les tables de rang sont précalculées
-- à partir de `athletes` ; les requêtes qui les remplissent ne sont pas encore
-- versionnées (voir README.md). Taille de la base : ~1,1 Go.
--
-- Pour le régénérer :
--   SELECT sql FROM sqlite_master WHERE sql IS NOT NULL
--     AND name NOT LIKE '_cf_%' AND name NOT LIKE 'sqlite_%';

-- Un profil par athlète et par distance (meilleure perf 2024-2026). Rempli par prepare_import.py.
-- pb_date au format JJ/MM/AA. Total par distance : voir ffa_distance_stats.
CREATE TABLE "athletes" (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  distance TEXT NOT NULL,
  full_name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  birth_year INTEGER,
  sex TEXT,
  pb_sec INTEGER NOT NULL,
  pb_course TEXT,
  pb_date TEXT,
  club TEXT,
  athlete_ffa_id TEXT
);

CREATE INDEX idx_athletes_distance_club_pb ON athletes(distance,club,pb_sec,id);
CREATE INDEX idx_athletes_next_distance_birth_pb ON "athletes"(distance,birth_year,pb_sec);
CREATE INDEX idx_athletes_next_distance_fullname ON "athletes"(distance,full_name);
CREATE INDEX idx_athletes_next_distance_name ON "athletes"(distance,name_key);
CREATE INDEX idx_athletes_next_distance_pb ON "athletes"(distance,pb_sec);
CREATE INDEX idx_athletes_next_distance_sex_birth_pb ON "athletes"(distance,sex,birth_year,pb_sec);
CREATE INDEX idx_athletes_next_distance_sex_pb ON "athletes"(distance,sex,pb_sec);

-- Recherche plein texte (trigrammes) sur name_key ; rowid = athletes.id.
CREATE VIRTUAL TABLE "athlete_fts" USING fts5(name_key,distance UNINDEXED,tokenize='trigram');


-- Classement général par distance : rank = RANK() sur pb_sec ; display_order = ordre d'affichage stable (ex aequo départagés).
CREATE TABLE "athlete_general_rank" (
  athlete_id INTEGER PRIMARY KEY,
  distance TEXT NOT NULL,
  rank INTEGER NOT NULL,
  display_order INTEGER NOT NULL
);

CREATE INDEX idx_general_rank_next_distance_display ON "athlete_general_rank"(distance,display_order,athlete_id);
CREATE INDEX idx_general_rank_next_distance_rank ON "athlete_general_rank"(distance,rank,athlete_id);

-- Idem, limité aux athlètes sans suffixe de nationalité « (XXX) » dans full_name.
CREATE TABLE "athlete_french_rank" (
  athlete_id INTEGER PRIMARY KEY,
  distance TEXT NOT NULL,
  rank_general INTEGER NOT NULL
);

CREATE INDEX idx_french_rank_next_distance_rank ON "athlete_french_rank"(distance,rank_general,athlete_id);

-- Rangs utilisés par /search et /ranking, tous par distance :
--   rank_general, rank_sex (par sexe),
--   rank_cat_before_sep (sexe + catégorie saison 2026), rank_cat_after_sep (sexe + catégorie saison 2027).
CREATE TABLE "athlete_search_rank" (
  athlete_id INTEGER PRIMARY KEY,
  rank_general INTEGER NOT NULL,
  rank_sex INTEGER,
  rank_cat_before_sep INTEGER,
  rank_cat_after_sep INTEGER
);

CREATE INDEX idx_search_rank_next_cat_after ON "athlete_search_rank"(rank_cat_after_sep,athlete_id);
CREATE INDEX idx_search_rank_next_cat_before ON "athlete_search_rank"(rank_cat_before_sep,athlete_id);
CREATE INDEX idx_search_rank_next_general ON "athlete_search_rank"(rank_general,athlete_id);
CREATE INDEX idx_search_rank_next_sex ON "athlete_search_rank"(rank_sex,athlete_id);

-- Rang par catégorie saison 2026, tous sexes confondus (par distance).
CREATE TABLE "athlete_rank_cat_before" (
  athlete_id INTEGER PRIMARY KEY,
  rank_category INTEGER
);

CREATE INDEX idx_rank_cat_before_next ON "athlete_rank_cat_before"(rank_category,athlete_id);

-- Rang par catégorie saison 2027, tous sexes confondus (par distance).
CREATE TABLE "athlete_rank_cat_after" (
  athlete_id INTEGER PRIMARY KEY,
  rank_category INTEGER
);

CREATE INDEX idx_rank_cat_after_next ON "athlete_rank_cat_after"(rank_category,athlete_id);

-- Rang parmi les athlètes de la même année de naissance (rank_year) et même année + sexe (rank_sex_year), par distance.
CREATE TABLE "athlete_rank_year" (
  athlete_id INTEGER PRIMARY KEY,
  rank_year INTEGER,
  rank_sex_year INTEGER
);

CREATE INDEX idx_rank_year_next_sex_year ON "athlete_rank_year"(rank_sex_year,athlete_id);
CREATE INDEX idx_rank_year_next_year ON "athlete_rank_year"(rank_year,athlete_id);

-- Ligue / département du club (codes FFA, ex. I-F / 077) et année civile de la perf (race_year).
CREATE TABLE "athlete_scope" (
  athlete_id INTEGER PRIMARY KEY,
  distance TEXT NOT NULL,
  league TEXT NOT NULL,
  department TEXT NOT NULL,
  race_year INTEGER
);

CREATE INDEX idx_scope_next_combined ON "athlete_scope"(distance,league,department,race_year,athlete_id);
CREATE INDEX idx_scope_next_distance_department ON "athlete_scope"(distance,department,athlete_id);
CREATE INDEX idx_scope_next_distance_league ON "athlete_scope"(distance,league,athlete_id);
CREATE INDEX idx_scope_next_distance_race_year ON "athlete_scope"(distance,race_year,athlete_id);

-- Combinaisons distinctes distance / ligue / département / club / année pour les listes de filtres (/ranking-options).
CREATE TABLE "ffa_scope_options"(distance TEXT NOT NULL,league TEXT NOT NULL,department TEXT NOT NULL,club TEXT NOT NULL,race_year INTEGER);

CREATE INDEX idx_scope_options_next_distance ON "ffa_scope_options"(distance,league,department,club,race_year);

-- Nombre total de profils par distance (évite un COUNT(*) sur athletes).
CREATE TABLE "ffa_distance_stats" (
  distance TEXT PRIMARY KEY,
  total INTEGER NOT NULL
);


-- Nombre de profils « français » par distance.
CREATE TABLE "ffa_french_stats" (
  distance TEXT PRIMARY KEY,
  total INTEGER NOT NULL
);
