"""
Fetch multi-timeframe $PUMP price data from GeckoTerminal.
Store in SQLite with epoch timestamps for fast querying.
"""
from typing import Optional, List, Dict, Tuple
import httpx
import sqlite3
import time
from datetime import datetime
from config import (
    DATA_DIR, PRICES_DB, PUMP_POOL_ADDRESS,
    TIMEFRAMES, TIMEFRAME_TO_GT
)

# GeckoTerminal API
GT_API = "https://api.geckoterminal.com/api/v2"
MAX_CANDLES_PER_REQUEST = 1000
RATE_LIMIT_DELAY = 0.5  # Be nice to the API


def init_db(db_path=PRICES_DB) -> sqlite3.Connection:
    """Initialize SQLite database with WAL mode for concurrent reads."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            timeframe TEXT NOT NULL,
            timestamp_epoch INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (timeframe, timestamp_epoch)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tf_ts 
        ON ohlcv(timeframe, timestamp_epoch)
    """)
    conn.commit()
    return conn


def fetch_ohlcv_page(
    pool_address: str,
    timeframe: str,
    before_timestamp: Optional[int] = None
) -> Tuple[List[Dict], Optional[int]]:
    """
    Fetch a single page of OHLCV data from GeckoTerminal.
    Returns (candles, oldest_timestamp_in_page).
    """
    tf_type, aggregate = TIMEFRAME_TO_GT[timeframe]
    url = f"{GT_API}/networks/solana/pools/{pool_address}/ohlcv/{tf_type}"
    
    params = {
        "aggregate": aggregate,
        "limit": MAX_CANDLES_PER_REQUEST,
        "currency": "usd",
    }
    
    if before_timestamp:
        params["before_timestamp"] = before_timestamp
    
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        
        if response.status_code == 429:
            print("  Rate limited, waiting 60s...")
            time.sleep(60)
            return fetch_ohlcv_page(pool_address, timeframe, before_timestamp)
        
        if response.status_code != 200:
            print(f"  Error {response.status_code}: {response.text[:200]}")
            return [], None
        
        data = response.json()
        ohlcv_list = data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        
        if not ohlcv_list:
            return [], None
        
        candles = []
        oldest_ts = None
        
        for candle in ohlcv_list:
            ts, o, h, l, c, v = candle
            candles.append({
                "timestamp_epoch": int(ts),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            })
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
        
        return candles, oldest_ts


def fetch_all_timeframe(
    pool_address: str,
    timeframe: str,
    conn: sqlite3.Connection,
    max_pages: int = 50
) -> int:
    """
    Fetch all available data for a timeframe via pagination.
    Returns total candles fetched.
    """
    print(f"\nFetching {timeframe} data...")
    
    total_candles = 0
    before_ts = None
    
    for page in range(max_pages):
        candles, oldest_ts = fetch_ohlcv_page(pool_address, timeframe, before_ts)
        
        if not candles:
            print(f"  Page {page + 1}: No more data")
            break
        
        # Insert into database (upsert)
        conn.executemany("""
            INSERT OR REPLACE INTO ohlcv 
            (timeframe, timestamp_epoch, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (timeframe, c["timestamp_epoch"], c["open"], c["high"], c["low"], c["close"], c["volume"])
            for c in candles
        ])
        conn.commit()
        
        total_candles += len(candles)
        oldest_date = datetime.utcfromtimestamp(oldest_ts).strftime("%Y-%m-%d %H:%M")
        print(f"  Page {page + 1}: {len(candles)} candles (oldest: {oldest_date})")
        
        # Check if we got fewer than max (end of data)
        if len(candles) < MAX_CANDLES_PER_REQUEST:
            break
        
        # Paginate backwards
        before_ts = oldest_ts
        time.sleep(RATE_LIMIT_DELAY)
    
    return total_candles


def get_db_stats(conn: sqlite3.Connection) -> Dict:
    """Get statistics about data in the database."""
    stats = {}
    for tf in TIMEFRAMES:
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as count,
                MIN(timestamp_epoch) as min_ts,
                MAX(timestamp_epoch) as max_ts
            FROM ohlcv WHERE timeframe = ?
        """, (tf,))
        row = cursor.fetchone()
        if row and row[0] > 0:
            stats[tf] = {
                "count": row[0],
                "start": datetime.utcfromtimestamp(row[1]).isoformat() if row[1] else None,
                "end": datetime.utcfromtimestamp(row[2]).isoformat() if row[2] else None,
            }
    return stats


def main():
    """Main entry point."""
    print("=" * 60)
    print("Multi-Timeframe Price Fetcher for $PUMP")
    print("=" * 60)
    print(f"Pool: {PUMP_POOL_ADDRESS}")
    print(f"Database: {PRICES_DB}")
    
    conn = init_db()
    
    # Fetch each timeframe
    for tf in TIMEFRAMES:
        # Adjust max pages based on timeframe (1m needs more pages)
        max_pages = {
            "1m": 100,   # ~100k candles
            "15m": 50,   # ~50k candles  
            "1h": 30,    # ~30k candles
            "1d": 10,    # ~10k candles
        }.get(tf, 20)
        
        total = fetch_all_timeframe(PUMP_POOL_ADDRESS, tf, conn, max_pages)
        print(f"  Total {tf}: {total:,} candles")
    
    # Print summary
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)
    
    stats = get_db_stats(conn)
    for tf, s in stats.items():
        print(f"  {tf}: {s['count']:,} candles")
        print(f"       {s['start'][:10]} to {s['end'][:10]}")
    
    conn.close()
    print(f"\nDatabase saved to: {PRICES_DB}")


if __name__ == "__main__":
    main()
