"""
Batch alignment of tweets with price data.
Uses efficient set-based joins (not N queries) for performance.

Output: tweet_events.json with price at tweet time and future prices.
"""
from typing import List, Dict, Optional, Tuple
import json
import sqlite3
import bisect
from datetime import datetime
from config import DATA_DIR, TWEETS_FILE, PRICES_DB, PUBLIC_DATA_DIR

# Price definition: we use candle CLOSE at the minute boundary
# This is documented for transparency in the proof table


def load_tweets() -> List[Dict]:
    """Load tweets sorted by timestamp."""
    with open(TWEETS_FILE) as f:
        data = json.load(f)
    
    tweets = data.get("tweets", [])
    
    # Parse and normalize timestamps
    for t in tweets:
        # Parse ISO timestamp to epoch
        dt = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        t["timestamp_epoch"] = int(dt.timestamp())
    
    # Sort by timestamp
    tweets.sort(key=lambda x: x["timestamp_epoch"])
    return tweets


def load_candles(conn: sqlite3.Connection, timeframe: str = "1m") -> Tuple[List[int], Dict[int, Dict]]:
    """
    Load all candles for a timeframe into memory.
    Returns (sorted_timestamps, timestamp_to_candle_dict).
    """
    cursor = conn.execute("""
        SELECT timestamp_epoch, open, high, low, close, volume
        FROM ohlcv
        WHERE timeframe = ?
        ORDER BY timestamp_epoch
    """, (timeframe,))
    
    timestamps = []
    candle_map = {}
    
    for row in cursor:
        ts, o, h, l, c, v = row
        timestamps.append(ts)
        candle_map[ts] = {
            "open": o, "high": h, "low": l, "close": c, "volume": v
        }
    
    return timestamps, candle_map


def find_price_at_time(
    target_ts: int,
    timestamps: List[int],
    candle_map: Dict[int, Dict]
) -> Optional[float]:
    """
    Find the candle close price at or just before target_ts.
    Uses binary search for O(log n) lookup.
    """
    if not timestamps:
        return None
    
    # Find insertion point
    idx = bisect.bisect_right(timestamps, target_ts)
    
    if idx == 0:
        # Target is before all candles
        return None
    
    # Get the candle at or just before target
    candle_ts = timestamps[idx - 1]
    return candle_map[candle_ts]["close"]


def align_tweets_with_prices(
    tweets: List[Dict],
    timestamps: List[int],
    candle_map: Dict[int, Dict]
) -> List[Dict]:
    """
    Align all tweets with price data in a single pass.
    For each tweet, find price at tweet time, +1h, +24h.
    """
    HOUR = 3600
    DAY = 86400
    
    aligned = []
    
    for tweet in tweets:
        ts = tweet["timestamp_epoch"]
        
        # Price at tweet time
        price_at = find_price_at_time(ts, timestamps, candle_map)
        
        # Price 1 hour later
        price_1h = find_price_at_time(ts + HOUR, timestamps, candle_map)
        
        # Price 24 hours later
        price_24h = find_price_at_time(ts + DAY, timestamps, candle_map)
        
        # Calculate percentage changes
        change_1h = None
        change_24h = None
        
        if price_at and price_1h:
            change_1h = round((price_1h - price_at) / price_at * 100, 2)
        
        if price_at and price_24h:
            change_24h = round((price_24h - price_at) / price_at * 100, 2)
        
        aligned.append({
            "tweet_id": tweet["id"],
            "timestamp": ts,
            "timestamp_iso": datetime.utcfromtimestamp(ts).isoformat() + "Z",
            "text": tweet["text"],
            "price_at_tweet": price_at,
            "price_1h": price_1h,
            "price_24h": price_24h,
            "change_1h_pct": change_1h,
            "change_24h_pct": change_24h,
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "impressions": tweet.get("impressions", 0),
        })
    
    return aligned


def save_tweet_events(events: List[Dict], output_path=None):
    """Save aligned tweet events to JSON."""
    if output_path is None:
        output_path = DATA_DIR / "tweet_events.json"
    
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "price_definition": "candle close at minute boundary",
        "count": len(events),
        "events": events
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved {len(events)} tweet events to {output_path}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Tweet-Price Alignment")
    print("=" * 60)
    
    # Load tweets
    print("\nLoading tweets...")
    tweets = load_tweets()
    print(f"  Loaded {len(tweets)} tweets")
    
    if not tweets:
        print("No tweets found!")
        return
    
    # Connect to price database
    print("\nLoading price data...")
    conn = sqlite3.connect(PRICES_DB)
    
    # Try 1m first, fall back to 15m, then 1h
    timestamps, candle_map = None, None
    for tf in ["1m", "15m", "1h", "1d"]:
        ts, cm = load_candles(conn, tf)
        if ts:
            print(f"  Using {tf} timeframe: {len(ts):,} candles")
            timestamps, candle_map = ts, cm
            break
    
    if not timestamps:
        print("No price data found in database!")
        conn.close()
        return
    
    # Align tweets with prices
    print("\nAligning tweets with prices...")
    aligned = align_tweets_with_prices(tweets, timestamps, candle_map)
    
    # Count successful alignments
    with_price = sum(1 for e in aligned if e["price_at_tweet"] is not None)
    print(f"  Aligned: {with_price}/{len(aligned)} tweets have price data")
    
    # Save to data directory
    save_tweet_events(aligned)
    
    # Also save to public directory for frontend
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_tweet_events(aligned, PUBLIC_DATA_DIR / "tweet_events.json")
    
    conn.close()
    
    # Print sample
    print("\nSample aligned events:")
    for event in aligned[-5:]:
        if event["price_at_tweet"]:
            change = event["change_24h_pct"]
            change_str = f"{change:+.1f}%" if change else "N/A"
            print(f"  {event['timestamp_iso'][:10]}: ${event['price_at_tweet']:.6f} → {change_str} (24h)")


if __name__ == "__main__":
    main()

