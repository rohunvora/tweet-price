# Archived Scripts

These scripts are no longer actively used but kept for reference.

## Files

### `nitter_scraper_v1_deprecated.py`
**Status:** Deprecated, replaced by `../nitter_scraper.py`

Original Nitter scraper that had reliability issues:
- 5 second delay between chunks triggered rate limiting
- No retry logic meant lost progress on errors
- Single Nitter instance = single point of failure

### `migrate_pump.py`
**Status:** One-time migration, completed

Migrated PUMP data from flat structure to subdirectory structure.
Only needed to run once during the multi-asset refactor.

### `migrate_to_duckdb.py`
**Status:** One-time migration, completed

Imported existing JSON/SQLite data into the unified DuckDB database.
Only needed to run once during the DuckDB migration.

---

If you need to perform similar migrations in the future, these files
can serve as templates, but they should not be run again.

