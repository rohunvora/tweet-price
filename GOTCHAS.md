# GOTCHAS.md - Read Before Changing ANYTHING

This file documents non-obvious design decisions and past debugging sessions.
**AI agents and developers: Read this BEFORE modifying any code.**

---

## Critical: Things That Will Crash the Frontend

### DST Duplicate Timestamps (export_static.py)

**Symptom:** Chart crashes with "Value is null" error from lightweight-charts.

**Root Cause:** Database stores datetime values. During DST "fall back" transitions,
two different wall-clock times (e.g., 2:00 AM before and after the change) can map
to the **same Unix timestamp**. lightweight-charts requires strictly unique timestamps.

**Solution:** export_static.py deduplicates timestamps during export, keeping the first
occurrence. There's a safety check that raises ValueError if duplicates slip through.

```python
# DO NOT REMOVE this deduplication logic in export_timeframe() and export_1m_chunked()
if ts_epoch in seen_timestamps:
    duplicates_skipped += 1
    continue
seen_timestamps.add(ts_epoch)
```

**Fixed in:** December 2024 after JUP chart started crashing.

---

## DOUBLE CANDLE Issue (1D Charts)

### What It Looks Like

The daily (1D) chart shows **two or more candles for the same day**, making the chart look "doubled" or have irregular spacing.

### Root Cause

Daily price data comes from multiple sources with **different timestamp conventions**:

| Source | Timestamp Convention |
|--------|---------------------|
| CoinGecko API | 00:00 UTC (midnight) |
| GeckoTerminal | 04:00 or 05:00 UTC |
| Birdeye backfill | 00:00 UTC |
| Hyperliquid API | 05:00 UTC |

When data from multiple sources is merged, you get **multiple candles per day**.

### How It's Fixed (Automatic)

`export_static.py` automatically normalizes all 1D timestamps to midnight UTC:

```python
# 1D TIMESTAMP NORMALIZATION - DO NOT REMOVE
if timeframe == "1d":
    normalized_ts = (ts_epoch // 86400) * 86400  # Snap to midnight
```

After normalization, deduplication keeps only the first candle for each timestamp.

### Verification

Run `python export_static.py` and look for:
```
(Normalized 379 timestamps to midnight UTC)
(Deduplicated 379 candles - same day from different sources)
```

### If Still Broken

See `docs/DATA_QUALITY_ISSUES.md` for detailed diagnosis and historical incidents.

---

## Database: Non-Obvious Design Decisions

### Staleness Limits in tweet_events View (db.py:139-142)

**What it does:** Each timeframe has a staleness limit:
- 1m: max 1 hour old
- 1h: max 24 hours old
- 1d: max 7 days old

**Why this exists:** Without staleness limits, a tweet from TODAY could match with
1-minute price data from 3 MONTHS AGO (when 1m collection started) instead of using
fresh 1h or 1d data. This caused wildly incorrect price_at_tweet values.

**DO NOT "optimize" by removing staleness checks.**

### CASE Statement Ordering (db.py:178-179)

```sql
CASE p.timeframe WHEN '1m' THEN 1 WHEN '1h' THEN 2 WHEN '1d' THEN 3 END
```

**DO NOT reorder this.** The fallback priority (1m > 1h > 1d) is intentional.
Changing the order breaks price lookups for tweets.

### Prices Table PRIMARY KEY (db.py:95)

```sql
PRIMARY KEY (asset_id, timeframe, timestamp)
```

The upsert logic in `insert_prices()` depends on this composite key.
**DO NOT change this** without also updating all INSERT...ON CONFLICT statements.

### insert_tweets Uses ON CONFLICT DO UPDATE (db.py:533-541)

This is intentional - we WANT to update engagement metrics (likes, retweets)
on re-fetch while preserving the original timestamp. Using INSERT OR IGNORE
would discard updated metrics.

### launch_date Filter in tweet_events (db.py:161)

```sql
WHERE t.timestamp >= a.launch_date
```

This prevents showing tweets from BEFORE the token existed.
**DO NOT remove this filter.**

---

## Fake Wick Detection (export_static.py)

### Automatic Wick Capping at Export Time

Fake wicks (MEV bots, fat fingers, data errors) are automatically capped during export.

**How it works:**
- If HIGH > max(OPEN, CLOSE) * 2, cap HIGH to that limit
- If LOW < min(OPEN, CLOSE) / 2, cap LOW to that limit

**Why this approach:**
- Catches fake spikes (HIGH way above both OPEN and CLOSE)
- Preserves legitimate crashes (where HIGH ≈ OPEN, price falls to lower CLOSE)
- Automatic - no manual intervention needed
- Non-destructive - candles are preserved, just wicks are capped

**Example:**
- PUMP spike: O=0.008, H=0.020, C=0.008 → HIGH capped to 0.016 (2x max body)
- BELIEVE crash: O=0.038, H=0.038, C=0.0003 → No change (HIGH ≈ OPEN, legitimate)

**Configuration:** `WICK_CAP_MULTIPLIER = 2.0` in export_static.py

---

## API Quirks: Know Before You Fetch

### CoinGecko: Use /ohlc/range, NOT /market_chart/range (fetch_prices.py)

**Symptom:** Chart renders as dots instead of candles, irregular timestamps.

**Root Cause:** The `/market_chart/range` endpoint returns **price points at irregular intervals**
(e.g., 13:12:40, 14:11:16), not proper OHLC candles. lightweight-charts expects regular intervals.

**Wrong endpoint:**
```
GET /coins/{id}/market_chart/range?from=X&to=Y
Returns: [[timestamp, price], ...] at ~hourly but IRREGULAR times
```

**Correct endpoint:**
```
GET /coins/{id}/ohlc/range?from=X&to=Y&interval=hourly
Returns: [[timestamp, O, H, L, C], ...] at EXACT hour boundaries
```

**Plan requirements:**
- `/market_chart/range`: Basic plan ($35/mo) - but gives irregular data!
- `/ohlc/range`: Analyst plan ($129/mo) or higher - proper OHLC candles

**Request limits:**
- Hourly: max 31 days per request (chunk into 30-day batches)
- Daily: max 180 days per request

**CoinGecko only supports 1h and 1d.** No 15m or 1m data available at any tier.

**Fixed in:** December 2024 after HYPE chart showed dots instead of candles.

---

### CoinGecko Usage Guidelines

**When to use CoinGecko:**
- Non-Solana chains (HYPE on Hyperliquid, EVM chains without DEX pools)
- CEX-only tokens not available on DEXes
- Backup/validation data source

**When NOT to use CoinGecko:**
- Solana DEX tokens (use GeckoTerminal + Birdeye instead)
- When you need 15m or 1m data (not supported)
- Demo/free tier (irregular timestamps break charts)

**CLI usage:**
```bash
# Backfill with CoinGecko (requires backfill_source: "coingecko" in assets.json)
python fetch_prices.py --asset hype --backfill --fresh

# Regular fetch uses price_source, backfill uses backfill_source
```

**GitHub Actions:** CoinGecko backfill is NOT run in hourly workflow.
Use `--backfill` manually for historical data. Regular hourly updates use primary price_source.

---

### GeckoTerminal Only Supports Backward Pagination (fetch_prices.py)

GeckoTerminal API only accepts `before_timestamp`, not `after_timestamp`.
You MUST paginate backwards from present to past.

**Why this matters for incremental fetch:**
You can't say "give me everything after timestamp X". Instead, you must:
1. Fetch the most recent page
2. Check if any returned candles are older than your last known timestamp
3. Stop when you hit existing data

**DO NOT try to add `after_timestamp` - the API doesn't support it.**

### GeckoTerminal 180-Day Paywall (fetch_prices.py:396-398)

Free tier returns HTTP 401 for data older than ~180 days.
Code handles this gracefully by returning empty list.

### X API 150-Day Historical Limit

X API v2 cannot retrieve tweets older than ~150 days.
For historical backfill, use Nitter scraper (`nitter_scraper.py`).

---

## Timezone Handling: Here Be Dragons

### Use calendar.timegm(), NOT datetime.timestamp() (fetch_prices.py:836)

**Wrong:**
```python
stop_at = last_ts.timestamp()  # Treats naive datetime as LOCAL time!
```

**Correct:**
```python
stop_at = calendar.timegm(last_ts.timetuple())  # Treats as UTC
```

DuckDB returns naive datetime objects. Using `.timestamp()` interprets them
as local time, which breaks incremental fetch logic.

**Fixed in:** December 2024 after workflow was re-fetching all historical data.

---

## Outlier Detection: Why 5-sigma?

### Threshold is 5σ, Not 3σ (fetch_prices.py:52, db.py:813)

```python
OUTLIER_THRESHOLD_STD = 5
```

Crypto prices have fat tails. Using 3-sigma (standard for normal distributions)
flagged legitimate 50-100% pumps as outliers. 5-sigma catches only true anomalies
like sniper bot spikes (1000x+ of median).

**DO NOT lower this threshold without testing on real pump data.**

---

## Export Pipeline: Chunking Strategy

### 1m Data is Chunked by Month (export_static.py)

Large assets can have millions of 1-minute candles. We chunk by month for:
1. Lazy loading in frontend (only load visible range)
2. Smaller individual file sizes
3. Efficient cache invalidation (only update current month)

Structure:
```
prices_1m_index.json     # Lists all chunks with date ranges
prices_1m_2025-07.json   # July 2025 data
prices_1m_2025-08.json   # August 2025 data
```

**DO NOT switch to a single prices_1m.json - it will break the frontend.**

---

## Frontend Integration

### Asset Data is Loaded Per-Asset

Frontend fetches:
1. `assets.json` (list of all assets)
2. `{asset}/tweet_events.json` (selected asset's tweets)
3. `{asset}/prices_1h.json` (for chart)
4. `{asset}/prices_1m_index.json` (for zoom, lazy loaded)

**DO NOT combine all assets into a single JSON - defeats lazy loading.**

---

## GitHub Actions Workflow

### YAML Heredoc Syntax for Inline Python (.github/workflows/hourly-update.yml)

Inline Python in YAML must use heredoc syntax:
```yaml
run: |
  python3 << 'PYTHON_SCRIPT'
  import sys
  # ... code here
  PYTHON_SCRIPT
```

**DO NOT use `python -c "..."` for multiline code** - YAML parsing breaks.

**Fixed in:** December 2024 after workflow failed with "unexpected token" errors.

---

## Data Overrides: Persistent Manual Fixes

### Why Data Overrides Exist (scripts/data_overrides.json)

**Problem:** One-time data fixes (removing outliers, excluding bad candles, filtering date ranges)
get RESET when:
- Data is re-fetched
- Export is re-run
- A new developer/agent doesn't know about the fix

**Solution:** `data_overrides.json` contains all manual fixes in a declarative format.
These are applied at EXPORT time, not stored in the database.

**File location:** `scripts/data_overrides.json`

### How It Works

```
Raw Data (DB) → Export → Apply Overrides → JSON Files (Frontend)
```

The database contains RAW data. Overrides are applied during export.
This means:
1. Raw data is never corrupted
2. Fixes persist across re-fetches
3. All fixes are documented and auditable
4. You can always see what was fixed and WHY

### Override Types

1. **price_overrides** - Fix specific candles (cap HIGH, exclude candle)
2. **tweet_exclusions** - Exclude specific tweet IDs from export
3. **asset_data_ranges** - Override the date range for an asset's data
4. **price_exclusions** - Exclude entire candles from export

### Example: PUMP Fake Wick Fix

```json
{
  "id": "pump-fake-wick-sept18",
  "asset_id": "pump",
  "timeframe": "1h",
  "timestamp": "2025-09-18T18:00:00Z",
  "action": "cap_high",
  "value": 0.009,
  "reason": "Fake wick from MEV bot/sniper. Original HIGH was ~0.02."
}
```

### CRITICAL RULES

1. **NEVER delete entries** without understanding WHY they were added
2. **ALWAYS add a reason** when creating new overrides
3. **Run export after changes** to verify they work
4. **Check this file FIRST** when investigating data issues

### When to Add an Override

- Found a fake wick that the automatic detector missed
- Need to exclude a specific bad candle
- Need to restrict date range for an asset (data quality issues)
- Need to exclude specific tweets (spam, off-topic, etc.)

**DO NOT manually edit the database for one-time fixes.** Use data_overrides.json.

---

## NEVER DELETE DATA FROM DATABASE

### The Rule

**NEVER run DELETE statements on the prices or tweets tables without verifying overlap first.**

### Why This Exists (December 2024 Incident)

A cleanup script deleted 92 HYPE candles assuming they were "duplicate migration data."
They weren't duplicates—they had **zero overlap** with existing data. Result: 24% of HYPE
daily data was lost and had to be restored from backup.

### Before ANY Bulk Delete

Run this verification query:

```sql
-- Check overlap BEFORE deleting
WITH to_delete AS (
    SELECT DISTINCT DATE_TRUNC('day', timestamp) as dt
    FROM prices
    WHERE asset_id = 'ASSET' AND timeframe = '1d'
    AND data_source = 'SOURCE_TO_DELETE'
),
to_keep AS (
    SELECT DISTINCT DATE_TRUNC('day', timestamp) as dt
    FROM prices
    WHERE asset_id = 'ASSET' AND timeframe = '1d'
    AND data_source != 'SOURCE_TO_DELETE'
)
SELECT
    (SELECT COUNT(*) FROM to_delete) as dates_to_delete,
    (SELECT COUNT(*) FROM to_keep) as dates_to_keep,
    (SELECT COUNT(*) FROM to_delete WHERE dt IN (SELECT dt FROM to_keep)) as overlap;

-- ONLY proceed if overlap = dates_to_delete (all deletions are true duplicates)
```

### Safe Alternatives

1. **Use data_overrides.json** to exclude data at export time (non-destructive)
2. **Add a `deprecated` flag** instead of deleting
3. **Archive to a backup table** before deleting

---

## Data Truncation Protection (hourly-update.yml)

### Problem: Silent Data Loss

Historical data can be silently lost when:
1. Database cache is corrupted/missing historical data
2. Git merge conflict overwrites full export with partial data
3. Incremental fetch runs but historical data wasn't in DB

### Solution: Pre/Post Comparison

The hourly workflow now:
1. **Snapshots** current data counts BEFORE export
2. **Compares** new counts to old counts AFTER export
3. **Blocks commit** if any asset's data drops >10%

```
🚨 DATA TRUNCATION DETECTED - BLOCKING COMMIT
The following data would be lost:
   - zora/1h: 5794 → 737 (lost 5057)
```

### Manual Fix

If truncation is detected:
```bash
# Check what's wrong
python validate_export.py --asset ASSET

# Re-export from DB (if DB has data)
python validate_export.py --asset ASSET --fix

# If DB is missing data, restore from backup or re-fetch with --backfill
python fetch_prices.py --asset ASSET --backfill
```

**DO NOT bypass the truncation check** - it exists to prevent production data loss.

---

## True Validation: Expected vs Actual Candles

### The Problem with "File Exists" Validation

Checking "does the JSON file exist and have data" is **NOT real validation**.
This approach missed the HYPE bug where 14,294 candles existed but at irregular
timestamps, causing the chart to render as dots instead of candles.

### True Validation Method

Use `validate_candle_coverage.py` to validate against mathematical truth:

```bash
python validate_candle_coverage.py --asset hype --verbose
```

**How it works:**
1. Load `launch_date` from assets.json (source of truth)
2. Calculate expected candles: `(today - launch_date) / interval`
3. Compare against actual candles in exported JSON
4. Report coverage % and detect gaps
5. Fail if coverage < 95%

**Example output:**
```
Timeframe    Expected     Actual   Coverage   Status
--------------------------------------------------
1d                387        384      99.2%       OK
1h              9,310      9,229      99.1%       OK
15m            37,241      5,936      15.9%     FAIL
```

### When to Run Validation

- After any `fetch_prices.py --backfill` operation
- After changing CoinGecko/Birdeye fetch logic
- Before committing data changes
- When investigating chart rendering issues

### What Validation Catches

1. **Coverage gaps** - Missing date ranges (e.g., 15m data only covers recent months)
2. **Pre-launch data** - Data before token existed (suspicious)
3. **Irregular timestamps** - More candles than expected suggests non-bucketed data
4. **Data source issues** - Wrong endpoint, API plan limitations

**DO NOT rely on "file exists" checks.** Always use the validation script.

---

## Checklist: Before You Commit

- [ ] Did you read this file?
- [ ] If modifying db.py views: Did you preserve staleness limits?
- [ ] If modifying export: Did you test for duplicate timestamps?
- [ ] If modifying fetch: Did you use calendar.timegm() for UTC?
- [ ] If adding timeframes: Did you add to CASE statements?
- [ ] If fixing data issues: Did you add to data_overrides.json (not manual DB edit)?
- [ ] If deleting DB data: Did you verify overlap first? (See "NEVER DELETE DATA" section)
- [ ] Run `python export_static.py` - does it complete without errors?
- [ ] Run `python validate_export.py` - do all assets pass?
- [ ] Run `python validate_candle_coverage.py --asset X` - is coverage ≥95%?
- [ ] Open the frontend - do charts load without crashing?
- [ ] Do charts render as CANDLES (not dots)?

---

*Last updated: December 2024*
*Maintainer: Learned these the hard way so you don't have to.*
