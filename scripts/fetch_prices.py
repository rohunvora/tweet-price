"""
Fetch multi-timeframe price data from GeckoTerminal or CoinGecko.
Store in unified DuckDB database.

Supports:
- Multi-asset fetching via --asset argument
- GeckoTerminal for DEX pools (1m, 15m, 1h, 1d data)
- CoinGecko for listed tokens (daily data only)
- Incremental fetching from last known timestamp

Usage:
    python fetch_prices.py                      # Fetch all enabled assets
    python fetch_prices.py --asset pump         # Fetch specific asset
    python fetch_prices.py --asset pump --full  # Full refetch
"""
import argparse
import httpx
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from config import TIMEFRAMES, TIMEFRAME_TO_GT, DATA_DIR
from db import (
    get_connection, init_schema, get_asset, get_enabled_assets,
    get_ingestion_state, update_ingestion_state, insert_prices
)

# API endpoints
GT_API = "https://api.geckoterminal.com/api/v2"
CG_API = "https://api.coingecko.com/api/v3"

MAX_CANDLES_PER_REQUEST = 1000
RATE_LIMIT_DELAY = 0.5  # Be nice to the APIs


def fetch_geckoterminal_ohlcv(
    network: str,
    pool_address: str,
    timeframe: str,
    before_timestamp: Optional[int] = None
) -> Tuple[List[Dict], Optional[int]]:
    """
    Fetch a single page of OHLCV data from GeckoTerminal.
    
    Args:
        network: Network name (e.g., 'solana', 'eth', 'bsc')
        pool_address: DEX pool address
        timeframe: One of '1m', '15m', '1h', '1d'
        before_timestamp: Pagination - fetch data before this timestamp
    
    Returns (candles, oldest_timestamp_in_page).
    """
    tf_type, aggregate = TIMEFRAME_TO_GT[timeframe]
    url = f"{GT_API}/networks/{network}/pools/{pool_address}/ohlcv/{tf_type}"
    
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
            print("      Rate limited, waiting 60s...")
            time.sleep(60)
            return fetch_geckoterminal_ohlcv(network, pool_address, timeframe, before_timestamp)
        
        if response.status_code != 200:
            print(f"      Error {response.status_code}: {response.text[:200]}")
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


def fetch_coingecko_daily(
    coingecko_id: str,
    days: int = 365
) -> List[Dict]:
    """
    Fetch daily OHLCV data from CoinGecko.
    
    Args:
        coingecko_id: CoinGecko token ID (e.g., 'bitcoin', 'jupiter-exchange-solana')
        days: Number of days of history to fetch
    
    Returns list of daily candles.
    """
    url = f"{CG_API}/coins/{coingecko_id}/ohlc"
    params = {
        "vs_currency": "usd",
        "days": days,
    }
    
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        
        if response.status_code == 429:
            print("      Rate limited, waiting 60s...")
            time.sleep(60)
            return fetch_coingecko_daily(coingecko_id, days)
        
        if response.status_code != 200:
            print(f"      Error {response.status_code}: {response.text[:200]}")
            return []
        
        ohlc_data = response.json()
        
        if not ohlc_data:
            return []
        
        candles = []
        for candle in ohlc_data:
            # CoinGecko returns [timestamp_ms, open, high, low, close]
            ts_ms, o, h, l, c = candle
            candles.append({
                "timestamp_epoch": int(ts_ms / 1000),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": 0.0,  # CoinGecko OHLC doesn't include volume
            })
        
        return candles


def fetch_geckoterminal_all_timeframes(
    network: str,
    pool_address: str,
    timeframes: List[str] = None,
    max_pages: Dict[str, int] = None
) -> Dict[str, List[Dict]]:
    """
    Fetch all timeframes for a GeckoTerminal pool.
    
    Args:
        network: Network name
        pool_address: Pool address
        timeframes: List of timeframes to fetch (default: all)
        max_pages: Dict of timeframe -> max pages to fetch
    
    Returns dict of timeframe -> candles.
    """
    if timeframes is None:
        timeframes = TIMEFRAMES
    
    if max_pages is None:
        max_pages = {
            "1m": 100,   # ~100k candles
            "15m": 50,   # ~50k candles  
            "1h": 30,    # ~30k candles
            "1d": 10,    # ~10k candles
        }
    
    results = {}
    
    for tf in timeframes:
        print(f"    Fetching {tf} data...")
        
        all_candles = []
        before_ts = None
        max_pg = max_pages.get(tf, 20)
        
        for page in range(max_pg):
            candles, oldest_ts = fetch_geckoterminal_ohlcv(
                network, pool_address, tf, before_ts
            )
            
            if not candles:
                if page == 0:
                    print(f"      No data available")
                break
            
            all_candles.extend(candles)
            oldest_date = datetime.utcfromtimestamp(oldest_ts).strftime("%Y-%m-%d")
            print(f"      Page {page + 1}: {len(candles)} candles (oldest: {oldest_date})")
            
            # Check if we got fewer than max (end of data)
            if len(candles) < MAX_CANDLES_PER_REQUEST:
                break
            
            # Paginate backwards
            before_ts = oldest_ts
            time.sleep(RATE_LIMIT_DELAY)
        
        if all_candles:
            # Sort by timestamp (oldest first)
            all_candles.sort(key=lambda x: x["timestamp_epoch"])
            results[tf] = all_candles
            print(f"      Total: {len(all_candles):,} candles")
    
    return results


def fetch_for_asset(
    asset_id: str,
    full_fetch: bool = False,
    timeframes: List[str] = None
) -> Dict[str, Any]:
    """
    Fetch prices for a specific asset.
    
    Args:
        asset_id: Asset ID from assets.json
        full_fetch: If True, fetch all history (ignore last_timestamp)
        timeframes: Specific timeframes to fetch (default: based on price_source)
    
    Returns fetch result stats.
    """
    conn = get_connection()
    init_schema(conn)
    
    # Get asset config
    asset = get_asset(conn, asset_id)
    if not asset:
        conn.close()
        return {"status": "error", "reason": f"Asset '{asset_id}' not found"}
    
    if not asset["enabled"]:
        conn.close()
        return {"status": "skipped", "reason": "Asset is disabled"}
    
    print(f"\n{'='*60}")
    print(f"Fetching prices for {asset['name']}")
    print(f"{'='*60}")
    print(f"    Source: {asset['price_source']}")
    print(f"    Network: {asset['network']}")
    
    price_source = asset["price_source"]
    results = {"status": "success", "timeframes": {}}
    
    if price_source == "geckoterminal":
        # GeckoTerminal - need pool_address and network
        pool_address = asset.get("pool_address")
        network = asset.get("network")
        
        if not pool_address:
            conn.close()
            return {"status": "error", "reason": "No pool_address configured"}
        
        print(f"    Pool: {pool_address}")
        
        # Fetch all timeframes
        if timeframes is None:
            timeframes = TIMEFRAMES
        
        price_data = fetch_geckoterminal_all_timeframes(
            network, pool_address, timeframes
        )
        
        # Insert into database
        for tf, candles in price_data.items():
            if candles:
                inserted = insert_prices(conn, asset_id, tf, candles)
                
                # Update ingestion state
                latest_ts = max(c["timestamp_epoch"] for c in candles)
                update_ingestion_state(
                    conn, asset_id, f"prices_{tf}",
                    last_timestamp=datetime.utcfromtimestamp(latest_ts)
                )
                
                results["timeframes"][tf] = {
                    "count": inserted,
                    "latest": datetime.utcfromtimestamp(latest_ts).isoformat(),
                }
    
    elif price_source == "coingecko":
        # CoinGecko - need coingecko_id
        coingecko_id = asset.get("coingecko_id")
        
        if not coingecko_id:
            conn.close()
            return {"status": "error", "reason": "No coingecko_id configured"}
        
        print(f"    CoinGecko ID: {coingecko_id}")
        
        # CoinGecko only provides daily OHLC
        print(f"    Fetching daily data...")
        candles = fetch_coingecko_daily(coingecko_id, days=365)
        
        if candles:
            inserted = insert_prices(conn, asset_id, "1d", candles)
    
            # Update ingestion state
            latest_ts = max(c["timestamp_epoch"] for c in candles)
            update_ingestion_state(
                conn, asset_id, "prices_1d",
                last_timestamp=datetime.utcfromtimestamp(latest_ts)
            )
            
            results["timeframes"]["1d"] = {
                "count": inserted,
                "latest": datetime.utcfromtimestamp(latest_ts).isoformat(),
            }
            print(f"      Inserted {inserted} daily candles")
        else:
            print(f"      No data available")
    
    else:
        conn.close()
        return {"status": "error", "reason": f"Unknown price_source: {price_source}"}
    
    conn.close()
    return results


def fetch_all_assets(
    full_fetch: bool = False,
    timeframes: List[str] = None
) -> Dict[str, Any]:
    """
    Fetch prices for all enabled assets.
    
    Args:
        full_fetch: If True, fetch all history
        timeframes: Specific timeframes to fetch
    
    Returns dict of asset_id -> result.
    """
    conn = get_connection()
    init_schema(conn)
    
    assets = get_enabled_assets(conn)
    conn.close()
    
    print(f"\nFetching prices for {len(assets)} enabled assets...")
    
    results = {}
    for asset in assets:
        result = fetch_for_asset(
            asset["id"], 
            full_fetch=full_fetch,
            timeframes=timeframes
        )
        results[asset["id"]] = result
        
        # Be nice to APIs between assets
        time.sleep(1)
    
    # Print summary
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    
    for asset_id, result in results.items():
        status = result.get("status", "unknown")
        if status == "success":
            tf_summary = ", ".join(
                f"{tf}:{info['count']}" 
                for tf, info in result.get("timeframes", {}).items()
            )
            print(f"  {asset_id}: {tf_summary or 'no data'}")
        else:
            print(f"  {asset_id}: {status} - {result.get('reason', '')}")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Fetch price data for tracked assets"
    )
    parser.add_argument(
        "--asset", "-a",
        type=str,
        help="Specific asset ID to fetch (default: all enabled assets)"
    )
    parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Full fetch (fetch all available history)"
    )
    parser.add_argument(
        "--timeframe", "-t",
        type=str,
        action="append",
        help="Specific timeframe(s) to fetch (can use multiple times)"
    )
    
    args = parser.parse_args()
    
    timeframes = args.timeframe if args.timeframe else None
    
    if args.asset:
        fetch_for_asset(
            args.asset, 
            full_fetch=args.full,
            timeframes=timeframes
        )
    else:
        fetch_all_assets(
            full_fetch=args.full,
            timeframes=timeframes
        )


if __name__ == "__main__":
    main()
