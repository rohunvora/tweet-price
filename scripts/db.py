"""
DuckDB database management for tweet-price analytics.
Single source of truth for all assets, tweets, and price data.
"""
import json
import duckdb
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_FILE = SCRIPTS_DIR / "assets.json"
ANALYTICS_DB = DATA_DIR / "analytics.duckdb"


def get_connection(db_path: Path = ANALYTICS_DB) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection with WAL mode enabled."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = duckdb.connect(str(db_path))
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Initialize the database schema."""
    
    # Assets table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            founder VARCHAR NOT NULL,
            network VARCHAR,
            pool_address VARCHAR,
            coingecko_id VARCHAR,
            price_source VARCHAR NOT NULL,
            launch_date TIMESTAMP NOT NULL,
            color VARCHAR,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        )
    """)
    
    # Tweets table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id VARCHAR PRIMARY KEY,
            asset_id VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            text VARCHAR,
            likes INTEGER DEFAULT 0,
            retweets INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            fetched_at TIMESTAMP DEFAULT now(),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    
    # Prices table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            asset_id VARCHAR NOT NULL,
            timeframe VARCHAR NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            fetched_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (asset_id, timeframe, timestamp),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    
    # Ingestion state for incremental fetching
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_state (
            asset_id VARCHAR NOT NULL,
            data_type VARCHAR NOT NULL,
            last_id VARCHAR,
            last_timestamp TIMESTAMP,
            updated_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (asset_id, data_type),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    
    # Create indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tweets_asset_ts 
        ON tweets(asset_id, timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tweets_asset 
        ON tweets(asset_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prices_asset_tf_ts 
        ON prices(asset_id, timeframe, timestamp)
    """)
    
    # Create tweet_events view with launch_date filter
    conn.execute("""
        CREATE OR REPLACE VIEW tweet_events AS
        SELECT 
            t.id AS tweet_id,
            t.asset_id,
            a.name AS asset_name,
            a.founder,
            a.color AS asset_color,
            t.timestamp,
            t.text,
            t.likes,
            t.retweets,
            t.replies,
            t.impressions,
            -- Price at tweet time (find closest 1m candle before tweet)
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1m'
               AND p.timestamp <= t.timestamp
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_at_tweet,
            -- Price 1 hour later
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1m'
               AND p.timestamp <= t.timestamp + INTERVAL '1 hour'
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_1h,
            -- Price 24 hours later
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1m'
               AND p.timestamp <= t.timestamp + INTERVAL '24 hours'
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_24h
        FROM tweets t
        JOIN assets a ON t.asset_id = a.id
        WHERE a.enabled = true
          AND t.timestamp >= a.launch_date
        ORDER BY t.timestamp
    """)
    
    # Fallback view using daily prices for assets without 1m data
    conn.execute("""
        CREATE OR REPLACE VIEW tweet_events_daily AS
        SELECT 
            t.id AS tweet_id,
            t.asset_id,
            a.name AS asset_name,
            a.founder,
            a.color AS asset_color,
            t.timestamp,
            t.text,
            t.likes,
            t.retweets,
            t.replies,
            t.impressions,
            -- Price at tweet time (find closest 1d candle)
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1d'
               AND p.timestamp <= t.timestamp
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_at_tweet,
            -- Price 1 day later (approximate 1h as same-day)
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1d'
               AND p.timestamp <= t.timestamp + INTERVAL '1 day'
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_1h,
            -- Price 1 day later
            (SELECT p.close 
             FROM prices p 
             WHERE p.asset_id = t.asset_id 
               AND p.timeframe = '1d'
               AND p.timestamp <= t.timestamp + INTERVAL '1 day'
             ORDER BY p.timestamp DESC 
             LIMIT 1) AS price_24h
        FROM tweets t
        JOIN assets a ON t.asset_id = a.id
        WHERE a.enabled = true
          AND t.timestamp >= a.launch_date
        ORDER BY t.timestamp
    """)


def load_assets_from_json(conn: duckdb.DuckDBPyConnection, assets_file: Path = ASSETS_FILE) -> int:
    """
    Load/sync assets from JSON config into database.
    Returns number of assets upserted.
    """
    with open(assets_file) as f:
        config = json.load(f)
    
    count = 0
    for asset in config.get("assets", []):
        conn.execute("""
            INSERT INTO assets (id, name, founder, network, pool_address, 
                               coingecko_id, price_source, launch_date, color, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                founder = EXCLUDED.founder,
                network = EXCLUDED.network,
                pool_address = EXCLUDED.pool_address,
                coingecko_id = EXCLUDED.coingecko_id,
                price_source = EXCLUDED.price_source,
                launch_date = EXCLUDED.launch_date,
                color = EXCLUDED.color,
                enabled = EXCLUDED.enabled,
                updated_at = now()
        """, [
            asset["id"],
            asset["name"],
            asset["founder"],
            asset.get("network"),
            asset.get("pool_address"),
            asset.get("coingecko_id"),
            asset["price_source"],
            asset["launch_date"],
            asset.get("color"),
            asset.get("enabled", True),
        ])
        count += 1
    
    return count


def get_asset(conn: duckdb.DuckDBPyConnection, asset_id: str) -> Optional[Dict[str, Any]]:
    """Get a single asset by ID."""
    result = conn.execute("""
        SELECT id, name, founder, network, pool_address, coingecko_id,
               price_source, launch_date, color, enabled
        FROM assets WHERE id = ?
    """, [asset_id]).fetchone()
    
    if not result:
        return None
    
    return {
        "id": result[0],
        "name": result[1],
        "founder": result[2],
        "network": result[3],
        "pool_address": result[4],
        "coingecko_id": result[5],
        "price_source": result[6],
        "launch_date": result[7],
        "color": result[8],
        "enabled": result[9],
    }


def get_enabled_assets(conn: duckdb.DuckDBPyConnection) -> List[Dict[str, Any]]:
    """Get all enabled assets."""
    results = conn.execute("""
        SELECT id, name, founder, network, pool_address, coingecko_id,
               price_source, launch_date, color, enabled
        FROM assets WHERE enabled = true
        ORDER BY name
    """).fetchall()
    
    return [
        {
            "id": r[0],
            "name": r[1],
            "founder": r[2],
            "network": r[3],
            "pool_address": r[4],
            "coingecko_id": r[5],
            "price_source": r[6],
            "launch_date": r[7],
            "color": r[8],
            "enabled": r[9],
        }
        for r in results
    ]


def get_all_assets(conn: duckdb.DuckDBPyConnection) -> List[Dict[str, Any]]:
    """Get all assets (including disabled)."""
    results = conn.execute("""
        SELECT id, name, founder, network, pool_address, coingecko_id,
               price_source, launch_date, color, enabled
        FROM assets
        ORDER BY name
    """).fetchall()
    
    return [
        {
            "id": r[0],
            "name": r[1],
            "founder": r[2],
            "network": r[3],
            "pool_address": r[4],
            "coingecko_id": r[5],
            "price_source": r[6],
            "launch_date": r[7],
            "color": r[8],
            "enabled": r[9],
        }
        for r in results
    ]


def get_ingestion_state(
    conn: duckdb.DuckDBPyConnection, 
    asset_id: str, 
    data_type: str
) -> Optional[Dict[str, Any]]:
    """Get ingestion state for an asset/data_type combo."""
    result = conn.execute("""
        SELECT last_id, last_timestamp, updated_at
        FROM ingestion_state
        WHERE asset_id = ? AND data_type = ?
    """, [asset_id, data_type]).fetchone()
    
    if not result:
        return None
    
    return {
        "last_id": result[0],
        "last_timestamp": result[1],
        "updated_at": result[2],
    }


def update_ingestion_state(
    conn: duckdb.DuckDBPyConnection,
    asset_id: str,
    data_type: str,
    last_id: Optional[str] = None,
    last_timestamp: Optional[datetime] = None
) -> None:
    """Update ingestion state after a successful fetch."""
    conn.execute("""
        INSERT INTO ingestion_state (asset_id, data_type, last_id, last_timestamp, updated_at)
        VALUES (?, ?, ?, ?, now())
        ON CONFLICT (asset_id, data_type) DO UPDATE SET
            last_id = COALESCE(EXCLUDED.last_id, ingestion_state.last_id),
            last_timestamp = COALESCE(EXCLUDED.last_timestamp, ingestion_state.last_timestamp),
            updated_at = now()
    """, [asset_id, data_type, last_id, last_timestamp])


def insert_tweets(
    conn: duckdb.DuckDBPyConnection,
    asset_id: str,
    tweets: List[Dict[str, Any]]
) -> int:
    """
    Insert tweets into database. Uses INSERT OR IGNORE for deduplication.
    Returns number of tweets inserted.
    """
    if not tweets:
        return 0
    
    inserted = 0
    for tweet in tweets:
        try:
            conn.execute("""
                INSERT INTO tweets (id, asset_id, timestamp, text, likes, retweets, replies, impressions, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (id) DO UPDATE SET
                    likes = EXCLUDED.likes,
                    retweets = EXCLUDED.retweets,
                    replies = EXCLUDED.replies,
                    impressions = EXCLUDED.impressions,
                    fetched_at = now()
            """, [
                tweet["id"],
                asset_id,
                tweet["timestamp"] if isinstance(tweet.get("timestamp"), datetime) else tweet.get("created_at"),
                tweet.get("text"),
                tweet.get("likes", 0),
                tweet.get("retweets", 0),
                tweet.get("replies", 0),
                tweet.get("impressions", 0),
            ])
            inserted += 1
        except Exception as e:
            print(f"Error inserting tweet {tweet.get('id')}: {e}")
    
    return inserted


def insert_prices(
    conn: duckdb.DuckDBPyConnection,
    asset_id: str,
    timeframe: str,
    candles: List[Dict[str, Any]]
) -> int:
    """
    Insert price candles into database.
    Returns number of candles inserted.
    """
    if not candles:
        return 0
    
    # Prepare data for bulk insert
    data = [
        (
            asset_id,
            timeframe,
            datetime.utcfromtimestamp(c["timestamp_epoch"]) if "timestamp_epoch" in c else c["timestamp"],
            c.get("open"),
            c.get("high"),
            c.get("low"),
            c.get("close"),
            c.get("volume"),
        )
        for c in candles
    ]
    
    conn.executemany("""
        INSERT INTO prices (asset_id, timeframe, timestamp, open, high, low, close, volume, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
        ON CONFLICT (asset_id, timeframe, timestamp) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            fetched_at = now()
    """, data)
    
    return len(data)


def get_tweet_events(
    conn: duckdb.DuckDBPyConnection,
    asset_id: Optional[str] = None,
    use_daily_fallback: bool = False
) -> List[Dict[str, Any]]:
    """
    Get aligned tweet events from the view.
    Optionally filter by asset_id.
    use_daily_fallback uses 1d prices for assets without 1m data.
    """
    view_name = "tweet_events_daily" if use_daily_fallback else "tweet_events"
    
    if asset_id:
        results = conn.execute(f"""
            SELECT tweet_id, asset_id, asset_name, founder, asset_color,
                   timestamp, text, likes, retweets, replies, impressions,
                   price_at_tweet, price_1h, price_24h
            FROM {view_name}
            WHERE asset_id = ?
            ORDER BY timestamp
        """, [asset_id]).fetchall()
    else:
        results = conn.execute(f"""
            SELECT tweet_id, asset_id, asset_name, founder, asset_color,
                   timestamp, text, likes, retweets, replies, impressions,
                   price_at_tweet, price_1h, price_24h
            FROM {view_name}
            ORDER BY timestamp
        """).fetchall()
    
    events = []
    for r in results:
        price_at = r[11]
        price_1h = r[12]
        price_24h = r[13]
        
        change_1h = None
        change_24h = None
        if price_at and price_1h:
            change_1h = round((price_1h - price_at) / price_at * 100, 2)
        if price_at and price_24h:
            change_24h = round((price_24h - price_at) / price_at * 100, 2)
        
        events.append({
            "tweet_id": r[0],
            "asset_id": r[1],
            "asset_name": r[2],
            "founder": r[3],
            "asset_color": r[4],
            "timestamp": int(r[5].timestamp()) if hasattr(r[5], 'timestamp') else r[5],
            "timestamp_iso": r[5].isoformat() + "Z" if hasattr(r[5], 'isoformat') else str(r[5]),
            "text": r[6],
            "likes": r[7],
            "retweets": r[8],
            "replies": r[9],
            "impressions": r[10],
            "price_at_tweet": price_at,
            "price_1h": price_1h,
            "price_24h": price_24h,
            "change_1h_pct": change_1h,
            "change_24h_pct": change_24h,
        })
    
    return events


def get_db_stats(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Get overall database statistics."""
    stats = {}
    
    # Asset counts
    stats["assets"] = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    stats["enabled_assets"] = conn.execute("SELECT COUNT(*) FROM assets WHERE enabled = true").fetchone()[0]
    
    # Tweet counts per asset
    tweet_counts = conn.execute("""
        SELECT a.id, a.name, COUNT(t.id) as tweet_count
        FROM assets a
        LEFT JOIN tweets t ON a.id = t.asset_id
        GROUP BY a.id, a.name
        ORDER BY a.name
    """).fetchall()
    stats["tweets_by_asset"] = {r[0]: {"name": r[1], "count": r[2]} for r in tweet_counts}
    
    # Price data ranges per asset
    price_ranges = conn.execute("""
        SELECT a.id, a.name, p.timeframe, 
               MIN(p.timestamp) as start_date,
               MAX(p.timestamp) as end_date,
               COUNT(*) as candle_count
        FROM assets a
        LEFT JOIN prices p ON a.id = p.asset_id
        WHERE p.timestamp IS NOT NULL
        GROUP BY a.id, a.name, p.timeframe
        ORDER BY a.name, p.timeframe
    """).fetchall()
    
    stats["prices_by_asset"] = {}
    for r in price_ranges:
        asset_id = r[0]
        if asset_id not in stats["prices_by_asset"]:
            stats["prices_by_asset"][asset_id] = {"name": r[1], "timeframes": {}}
        stats["prices_by_asset"][asset_id]["timeframes"][r[2]] = {
            "start": r[3].isoformat() if r[3] else None,
            "end": r[4].isoformat() if r[4] else None,
            "count": r[5],
        }
    
    return stats


def init_db(db_path: Path = ANALYTICS_DB) -> duckdb.DuckDBPyConnection:
    """Initialize database with schema and load assets from JSON."""
    conn = get_connection(db_path)
    init_schema(conn)
    load_assets_from_json(conn)
    return conn


# CLI interface
def main():
    """CLI for database management."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python db.py <command>")
        print("Commands:")
        print("  init          - Initialize database schema")
        print("  sync-assets   - Sync assets from JSON to database")
        print("  stats         - Show database statistics")
        print("  list-assets   - List all assets")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        print("Initializing database...")
        conn = get_connection()
        init_schema(conn)
        count = load_assets_from_json(conn)
        print(f"Database initialized at {ANALYTICS_DB}")
        print(f"Loaded {count} assets from {ASSETS_FILE}")
        conn.close()
    
    elif command == "sync-assets":
        print("Syncing assets from JSON...")
        conn = get_connection()
        count = load_assets_from_json(conn)
        print(f"Synced {count} assets")
        conn.close()
    
    elif command == "stats":
        conn = get_connection()
        init_schema(conn)
        stats = get_db_stats(conn)
        print(f"\nDatabase: {ANALYTICS_DB}")
        print(f"Total assets: {stats['assets']} ({stats['enabled_assets']} enabled)")
        print("\nTweets by asset:")
        for asset_id, info in stats.get("tweets_by_asset", {}).items():
            print(f"  {info['name']}: {info['count']:,} tweets")
        print("\nPrice data by asset:")
        for asset_id, info in stats.get("prices_by_asset", {}).items():
            print(f"  {info['name']}:")
            for tf, tf_info in info.get("timeframes", {}).items():
                print(f"    {tf}: {tf_info['count']:,} candles ({tf_info['start'][:10] if tf_info['start'] else 'N/A'} to {tf_info['end'][:10] if tf_info['end'] else 'N/A'})")
        conn.close()
    
    elif command == "list-assets":
        conn = get_connection()
        init_schema(conn)
        assets = get_all_assets(conn)
        print(f"\n{'ID':<12} {'Name':<12} {'Founder':<18} {'Network':<12} {'Source':<14} {'Enabled'}")
        print("-" * 90)
        for a in assets:
            enabled = "✓" if a["enabled"] else "✗"
            print(f"{a['id']:<12} {a['name']:<12} {a['founder']:<18} {a['network'] or 'N/A':<12} {a['price_source']:<14} {enabled}")
        conn.close()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()


