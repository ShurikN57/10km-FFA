DROP TABLE IF EXISTS athletes;

CREATE TABLE athletes (
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

CREATE INDEX idx_athletes_distance_pb ON athletes(distance, pb_sec);
CREATE INDEX idx_athletes_distance_name ON athletes(distance, name_key);
CREATE INDEX idx_athletes_distance_sex_pb ON athletes(distance, sex, pb_sec);
CREATE INDEX idx_athletes_distance_birth_pb ON athletes(distance, birth_year, pb_sec);
