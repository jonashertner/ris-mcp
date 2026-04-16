-- Retroactively populate the `court` column from Technisch.Organ in raw_json.
-- Safe to re-run: only updates rows where json_extract yields a non-NULL value.
UPDATE decisions
SET court = TRIM(json_extract(raw_json, '$.Data.Metadaten.Technisch.Organ'))
WHERE json_extract(raw_json, '$.Data.Metadaten.Technisch.Organ') IS NOT NULL
  AND TRIM(json_extract(raw_json, '$.Data.Metadaten.Technisch.Organ')) != '';
