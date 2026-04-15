# Publishing the pre-built ris-mcp dataset to HuggingFace

Run after the full backfill (`ris-ingest --full`) completes on any one machine.

## 1. Generate a fresh stats report

```bash
ris-ingest coverage --out docs/stats.json
git add docs/stats.json
git commit -m "Refresh stats.json after backfill"
```

## 2. Prepare the DB for upload

```bash
DB=~/.local/share/ris-mcp/ris.db
sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);"
shasum -a 256 "$DB" | tee "${DB}.sha256"
```

## 3. Upload to HuggingFace

```bash
huggingface-cli login       # one-time
huggingface-cli upload voilaj/austrian-caselaw "$DB" ris.db
huggingface-cli upload voilaj/austrian-caselaw "${DB}.sha256" ris.db.sha256
```

If the repo does not exist, first:
`huggingface-cli repo create austrian-caselaw --type dataset --organization voilaj`.

## 4. Write a dataset card

Manually edit `README.md` on the HF repo (web UI). Include:
- Source: Austrian RIS Web Service v2.6 (data.bka.gv.at)
- License: CC0-1.0 (amtliches Werk per § 7 öUrhG)
- Schema reference: this repo's `src/ris_mcp/schema.sql`
- How to use: `pip install ris-mcp && ris-ingest import-from-hf`

## 5. Remove "coming soon" banners from the landing page

In `docs/index.html`, search for `<!-- HF-DATASET-PENDING -->` and remove each marked block (2 places). Commit:

```bash
git commit -m "Announce HF dataset availability"
```

## 6. Tag a docs-only release

```bash
git tag -a v0.2.1 -m "Pre-built dataset now available on HuggingFace"
git push origin v0.2.1
```
