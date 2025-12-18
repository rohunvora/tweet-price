"""
Fetch tweets from founders using X API v2.
Supports:
- Multi-asset fetching via --asset argument
- Incremental fetching with since_id
- Pre-launch filtering based on assets.json launch_date
- Direct writes to DuckDB

Usage:
    python fetch_tweets.py                    # Fetch all enabled assets
    python fetch_tweets.py --asset pump       # Fetch specific asset
    python fetch_tweets.py --asset pump --full  # Full refetch (ignore since_id)
"""
import argparse
import httpx
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import (
    X_BEARER_TOKEN,
    X_API_BASE,
    RATE_LIMIT_DELAY,
    DATA_DIR
)
from db import (
    get_connection, init_schema, get_asset, get_enabled_assets,
    get_ingestion_state, update_ingestion_state, insert_tweets
)


def get_user_id(client: httpx.Client, username: str) -> str:
    """Get the user ID from username."""
    url = f"{X_API_BASE}/users/by/username/{username}"
    response = client.get(url)
    response.raise_for_status()
    data = response.json()
    return data["data"]["id"]


def fetch_user_tweets(
    client: httpx.Client,
    user_id: str,
    since_id: Optional[str] = None,
    pagination_token: Optional[str] = None,
    max_results: int = 100
) -> dict:
    """
    Fetch a page of tweets from a user's timeline.
    
    Args:
        client: HTTP client
        user_id: Twitter user ID
        since_id: Only return tweets newer than this ID (for incremental fetch)
        pagination_token: Token for pagination
        max_results: Max tweets per page
    
    Returns tweet data with: id, text, created_at, public_metrics
    """
    url = f"{X_API_BASE}/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,conversation_id",
        "exclude": "retweets,replies",  # Only original tweets
    }
    
    if since_id:
        params["since_id"] = since_id
    
    if pagination_token:
        params["pagination_token"] = pagination_token
    
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_tweets_for_user(
    username: str,
    since_id: Optional[str] = None,
    max_pages: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch tweets for a user, optionally since a specific tweet ID.
    
    Args:
        username: Twitter username (without @)
        since_id: Only fetch tweets newer than this ID
        max_pages: Maximum number of pages to fetch
    
    Returns list of tweet objects.
    """
    if not X_BEARER_TOKEN:
        raise ValueError(
            "X_BEARER_TOKEN not found. Create a .env file with:\n"
            "X_BEARER_TOKEN=your_bearer_token_here"
        )
    
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
    }
    
    all_tweets = []
    
    with httpx.Client(headers=headers, timeout=30.0) as client:
        # First, get the user ID
        print(f"    Looking up @{username}...")
        try:
        user_id = get_user_id(client, username)
        except httpx.HTTPStatusError as e:
            print(f"    Error looking up user: {e.response.status_code}")
            return []
        
        # Paginate through tweets
        pagination_token = None
        page = 1
        
        while page <= max_pages:
            try:
                data = fetch_user_tweets(
                    client, user_id, 
                    since_id=since_id,
                    pagination_token=pagination_token
                )
            except httpx.HTTPStatusError as e:
                print(f"    API Error: {e.response.status_code}")
                if e.response.status_code == 429:
                    print("    Rate limited, waiting 60s...")
                    time.sleep(60)
                    continue
                break
            
            tweets = data.get("data", [])
            if not tweets:
                if page == 1:
                    print("    No new tweets found.")
                break
            
            # Process tweets
            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                processed = {
                    "id": tweet["id"],
                    "text": tweet["text"],
                    "created_at": tweet["created_at"],
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                }
                all_tweets.append(processed)
            
            print(f"    Page {page}: {len(tweets)} tweets (total: {len(all_tweets)})")
            
            # Check for more pages
            meta = data.get("meta", {})
            pagination_token = meta.get("next_token")
            
            if not pagination_token:
                break
            
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)
            page += 1
    
    # Sort by date (oldest first)
    all_tweets.sort(key=lambda x: x["created_at"])
    
    return all_tweets


def parse_iso_timestamp(iso_str: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    iso_str = iso_str.replace("Z", "+00:00")
    return datetime.fromisoformat(iso_str)


def fetch_for_asset(
    asset_id: str,
    full_fetch: bool = False,
    save_json: bool = True
) -> Dict[str, Any]:
    """
    Fetch tweets for a specific asset.
    
    Args:
        asset_id: Asset ID from assets.json
        full_fetch: If True, ignore since_id and fetch all
        save_json: If True, also save to JSON file (for backwards compatibility)
    
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
    print(f"Fetching tweets for {asset['name']} (@{asset['founder']})")
    print(f"{'='*60}")
    
    # Get since_id for incremental fetch
    since_id = None
    if not full_fetch:
        state = get_ingestion_state(conn, asset_id, "tweets")
        if state and state.get("last_id"):
            since_id = state["last_id"]
            print(f"    Incremental fetch since tweet ID: {since_id}")
    
    # Fetch tweets
    tweets = fetch_tweets_for_user(asset["founder"], since_id=since_id)
    
    if not tweets:
        conn.close()
        return {"status": "success", "fetched": 0, "inserted": 0}
    
    # Filter pre-launch tweets
    launch_date = asset["launch_date"]
    if isinstance(launch_date, str):
        launch_date = parse_iso_timestamp(launch_date)
    
    pre_launch_count = 0
    filtered_tweets = []
    for t in tweets:
        tweet_time = parse_iso_timestamp(t["created_at"])
        if tweet_time < launch_date:
            pre_launch_count += 1
            continue
        filtered_tweets.append(t)
    
    if pre_launch_count > 0:
        print(f"    Filtered {pre_launch_count} pre-launch tweets")
    
    # Insert into database
    inserted = insert_tweets(conn, asset_id, filtered_tweets)
    print(f"    Inserted/updated {inserted} tweets in database")
    
    # Update ingestion state with newest tweet ID
    if filtered_tweets:
        # Get the newest tweet (they're sorted oldest first)
        newest = max(filtered_tweets, key=lambda x: x["id"])
        update_ingestion_state(conn, asset_id, "tweets", last_id=newest["id"])
    
    # Optionally save to JSON for backwards compatibility
    if save_json and filtered_tweets:
        json_path = DATA_DIR / asset_id / "tweets.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing tweets if any
        existing_tweets = []
        if json_path.exists():
            with open(json_path) as f:
                existing_data = json.load(f)
                existing_tweets = existing_data.get("tweets", [])
        
        # Merge (deduplicate by ID)
        existing_ids = {t["id"] for t in existing_tweets}
        for t in filtered_tweets:
            if t["id"] not in existing_ids:
                existing_tweets.append(t)
        
        # Sort by date
        existing_tweets.sort(key=lambda x: x["created_at"])
        
        # Save
    output = {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "asset": asset_id,
            "username": asset["founder"],
            "count": len(existing_tweets),
            "tweets": existing_tweets
    }
    
        with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    
        print(f"    Saved to {json_path}")
    
    conn.close()
    
    return {
        "status": "success",
        "fetched": len(tweets),
        "pre_launch_filtered": pre_launch_count,
        "inserted": inserted,
    }


def fetch_all_assets(full_fetch: bool = False) -> Dict[str, Any]:
    """
    Fetch tweets for all enabled assets.
    
    Args:
        full_fetch: If True, ignore since_id and fetch all
    
    Returns dict of asset_id -> result.
    """
    conn = get_connection()
    init_schema(conn)
    
    assets = get_enabled_assets(conn)
    conn.close()
    
    print(f"\nFetching tweets for {len(assets)} enabled assets...")
    
    results = {}
    for asset in assets:
        result = fetch_for_asset(asset["id"], full_fetch=full_fetch)
        results[asset["id"]] = result
    
    # Print summary
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    
    total_fetched = 0
    total_inserted = 0
    for asset_id, result in results.items():
        status = result.get("status", "unknown")
        if status == "success":
            fetched = result.get("fetched", 0)
            inserted = result.get("inserted", 0)
            total_fetched += fetched
            total_inserted += inserted
            print(f"  {asset_id}: {fetched} fetched, {inserted} inserted")
        else:
            print(f"  {asset_id}: {status} - {result.get('reason', '')}")
    
    print(f"\nTotal: {total_fetched} tweets fetched, {total_inserted} inserted")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Fetch tweets for tracked assets"
    )
    parser.add_argument(
        "--asset", "-a",
        type=str,
        help="Specific asset ID to fetch (default: all enabled assets)"
    )
    parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Full fetch (ignore since_id, fetch all available tweets)"
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Don't save to JSON files (only write to database)"
    )
    
    args = parser.parse_args()
    
    if args.asset:
        fetch_for_asset(
            args.asset, 
            full_fetch=args.full,
            save_json=not args.no_json
        )
    else:
        fetch_all_assets(full_fetch=args.full)


if __name__ == "__main__":
    main()
