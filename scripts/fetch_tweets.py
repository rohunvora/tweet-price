"""
Fetch tweets from @a1lon9 using X API v2.
Handles pagination to get up to 3,200 tweets (Twitter's limit).
"""
import httpx
import json
import time
from datetime import datetime
from config import (
    X_BEARER_TOKEN,
    X_API_BASE,
    TARGET_USERNAME,
    RATE_LIMIT_DELAY,
    TWEETS_FILE,
    DATA_DIR
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
    pagination_token: str = None,
    max_results: int = 100
) -> dict:
    """
    Fetch a page of tweets from a user's timeline.
    
    Returns tweet data with: id, text, created_at, public_metrics
    """
    url = f"{X_API_BASE}/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,conversation_id",
        "exclude": "retweets,replies",  # Only original tweets
    }
    
    if pagination_token:
        params["pagination_token"] = pagination_token
    
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_all_tweets(username: str = TARGET_USERNAME) -> list[dict]:
    """
    Fetch all available tweets from a user (up to 3,200).
    
    Returns list of tweet objects with:
    - id: Tweet ID
    - text: Tweet content
    - created_at: ISO timestamp
    - likes: Like count
    - retweets: Retweet count
    - replies: Reply count
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
        print(f"Looking up user @{username}...")
        user_id = get_user_id(client, username)
        print(f"Found user ID: {user_id}")
        
        # Paginate through all tweets
        pagination_token = None
        page = 1
        
        while True:
            print(f"Fetching page {page}...")
            
            try:
                data = fetch_user_tweets(client, user_id, pagination_token)
            except httpx.HTTPStatusError as e:
                print(f"API Error: {e.response.status_code}")
                print(f"Response: {e.response.text}")
                break
            
            tweets = data.get("data", [])
            if not tweets:
                print("No more tweets found.")
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
            
            print(f"  Got {len(tweets)} tweets (total: {len(all_tweets)})")
            
            # Check for more pages
            meta = data.get("meta", {})
            pagination_token = meta.get("next_token")
            
            if not pagination_token:
                print("Reached end of timeline.")
                break
            
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)
            page += 1
    
    # Sort by date (oldest first)
    all_tweets.sort(key=lambda x: x["created_at"])
    
    return all_tweets


def save_tweets(tweets: list[dict], filepath=TWEETS_FILE):
    """Save tweets to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    
    output = {
        "fetched_at": datetime.utcnow().isoformat(),
        "username": TARGET_USERNAME,
        "count": len(tweets),
        "tweets": tweets
    }
    
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved {len(tweets)} tweets to {filepath}")


def main():
    """Main entry point."""
    print("=" * 50)
    print("Tweet Fetcher for @a1lon9")
    print("=" * 50)
    
    tweets = fetch_all_tweets()
    
    if tweets:
        save_tweets(tweets)
        
        # Print summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Total tweets fetched: {len(tweets)}")
        print(f"Date range: {tweets[0]['created_at'][:10]} to {tweets[-1]['created_at'][:10]}")
        
        # Most engaging tweets
        by_engagement = sorted(tweets, key=lambda x: x["likes"] + x["retweets"], reverse=True)
        print("\nTop 5 most engaging tweets:")
        for i, tweet in enumerate(by_engagement[:5], 1):
            print(f"  {i}. [{tweet['likes']}❤️ {tweet['retweets']}🔁] {tweet['text'][:60]}...")
    else:
        print("No tweets fetched. Check your API credentials.")


if __name__ == "__main__":
    main()

