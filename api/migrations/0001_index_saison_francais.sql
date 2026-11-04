-- Index pour les classements par saison et « français uniquement ».
-- Ajout d'index seulement : aucune donnée modifiée, l'ancien Worker continue de
-- fonctionner. Annulation : DROP INDEX <nom>; pour chacun des trois.
--
-- L'expression de saison doit rester identique à SEASON_SQL dans api/worker.js
-- (sinon SQLite n'utilise pas l'index) : la saison N va du 01/09/N-1 au 31/08/N,
-- pb_date est au format JJ/MM/AA.

CREATE INDEX IF NOT EXISTS idx_athletes_season_pb ON athletes(
  distance,
  (2000 + CAST(substr(pb_date, 7, 2) AS INTEGER) + (CAST(substr(pb_date, 4, 2) AS INTEGER) >= 9)),
  pb_sec
);

CREATE INDEX IF NOT EXISTS idx_athletes_sex_season_pb ON athletes(
  distance,
  sex,
  (2000 + CAST(substr(pb_date, 7, 2) AS INTEGER) + (CAST(substr(pb_date, 4, 2) AS INTEGER) >= 9)),
  pb_sec
);

-- Index partiel : athlètes sans suffixe de nationalité « (XXX) » dans le nom.
CREATE INDEX IF NOT EXISTS idx_athletes_french_sex_pb ON athletes(distance, sex, pb_sec)
  WHERE full_name NOT GLOB '* ([A-Z][A-Z][A-Z])';
