-- src/ris_mcp/schema.sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS decisions (
  id              TEXT PRIMARY KEY,
  applikation     TEXT NOT NULL,
  court           TEXT NOT NULL,
  geschaeftszahl  TEXT NOT NULL,
  entscheidungsdatum DATE,
  rechtssatznummer TEXT,
  dokumenttyp     TEXT,
  norm            TEXT,
  schlagworte     TEXT,
  rechtssatz      TEXT,
  text            TEXT,
  text_html       TEXT,
  source_url      TEXT,
  fetched_at      TIMESTAMP NOT NULL,
  aenderungsdatum TIMESTAMP,
  raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_court_date ON decisions(court, entscheidungsdatum DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_geschaeftszahl ON decisions(geschaeftszahl);
CREATE INDEX IF NOT EXISTS idx_decisions_aenderung ON decisions(aenderungsdatum);

CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
  geschaeftszahl, court, norm, schlagworte, rechtssatz, text,
  content='decisions', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
  INSERT INTO decisions_fts(rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES (new.rowid, new.geschaeftszahl, new.court, new.norm, new.schlagworte, new.rechtssatz, new.text);
END;
CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
  INSERT INTO decisions_fts(decisions_fts, rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES('delete', old.rowid, old.geschaeftszahl, old.court, old.norm, old.schlagworte, old.rechtssatz, old.text);
END;
CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
  INSERT INTO decisions_fts(decisions_fts, rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES('delete', old.rowid, old.geschaeftszahl, old.court, old.norm, old.schlagworte, old.rechtssatz, old.text);
  INSERT INTO decisions_fts(rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES (new.rowid, new.geschaeftszahl, new.court, new.norm, new.schlagworte, new.rechtssatz, new.text);
END;

CREATE TABLE IF NOT EXISTS laws (
  id              TEXT PRIMARY KEY,
  gesetzesnummer  TEXT NOT NULL,
  kurztitel       TEXT,
  langtitel       TEXT,
  paragraf        TEXT NOT NULL,
  absatz          TEXT,
  ueberschrift    TEXT,
  text            TEXT NOT NULL,
  fassung_vom     DATE,
  source_url      TEXT,
  fetched_at      TIMESTAMP NOT NULL,
  raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_laws_kurztitel ON laws(kurztitel);

CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(
  kurztitel, langtitel, paragraf, ueberschrift, text,
  content='laws', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS laws_ai AFTER INSERT ON laws BEGIN
  INSERT INTO laws_fts(rowid, kurztitel, langtitel, paragraf, ueberschrift, text)
  VALUES (new.rowid, new.kurztitel, new.langtitel, new.paragraf, new.ueberschrift, new.text);
END;

CREATE TABLE IF NOT EXISTS sync_state (
  applikation     TEXT PRIMARY KEY,
  last_full_sync  TIMESTAMP,
  last_delta_sync TIMESTAMP,
  watermark_aenderungsdatum TIMESTAMP,
  total_docs      INTEGER DEFAULT 0
);
