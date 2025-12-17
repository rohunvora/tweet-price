"""
Compute pre-computed statistics for the frontend.
All heavy computation happens here, not in the browser.
"""
from typing import List, Dict, Optional
import json
import sqlite3
import numpy as np
from datetime import datetime
from scipy import stats
from config import DATA_DIR, PRICES_DB, PUBLIC_DATA_DIR


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_tweet_events() -> List[Dict]:
    """Load aligned tweet events."""
    path = DATA_DIR / "tweet_events.json"
    with open(path) as f:
        data = json.load(f)
    return data.get("events", [])


def load_daily_prices(conn: sqlite3.Connection) -> Dict[int, float]:
    """Load daily close prices as timestamp -> price map."""
    cursor = conn.execute("""
        SELECT timestamp_epoch, close
        FROM ohlcv
        WHERE timeframe = '1d'
        ORDER BY timestamp_epoch
    """)
    return {row[0]: row[1] for row in cursor}


def compute_daily_stats(
    events: List[Dict],
    daily_prices: Dict[int, float]
) -> Dict:
    """
    Compute tweet day vs no-tweet day statistics.
    """
    DAY = 86400
    
    # Get unique tweet days (epoch at midnight)
    tweet_days = set()
    for event in events:
        ts = event["timestamp"]
        day_start = (ts // DAY) * DAY
        tweet_days.add(day_start)
    
    # Calculate daily returns
    sorted_days = sorted(daily_prices.keys())
    tweet_day_returns = []
    no_tweet_day_returns = []
    
    for i in range(1, len(sorted_days)):
        day = sorted_days[i]
        prev_day = sorted_days[i - 1]
        
        price = daily_prices[day]
        prev_price = daily_prices[prev_day]
        
        if prev_price > 0:
            ret = (price - prev_price) / prev_price * 100
            
            if day in tweet_days:
                tweet_day_returns.append(ret)
            else:
                no_tweet_day_returns.append(ret)
    
    # Statistical test
    t_stat, p_value = None, None
    if len(tweet_day_returns) >= 5 and len(no_tweet_day_returns) >= 5:
        t_stat, p_value = stats.ttest_ind(tweet_day_returns, no_tweet_day_returns)
    
    return {
        "tweet_day_count": len(tweet_day_returns),
        "tweet_day_avg_return": round(sum(tweet_day_returns) / len(tweet_day_returns), 2) if tweet_day_returns else 0,
        "tweet_day_win_rate": round(sum(1 for r in tweet_day_returns if r > 0) / len(tweet_day_returns) * 100, 1) if tweet_day_returns else 0,
        "no_tweet_day_count": len(no_tweet_day_returns),
        "no_tweet_day_avg_return": round(sum(no_tweet_day_returns) / len(no_tweet_day_returns), 2) if no_tweet_day_returns else 0,
        "no_tweet_day_win_rate": round(sum(1 for r in no_tweet_day_returns if r > 0) / len(no_tweet_day_returns) * 100, 1) if no_tweet_day_returns else 0,
        "t_statistic": round(t_stat, 3) if t_stat else None,
        "p_value": round(p_value, 4) if p_value else None,
        "significant": p_value < 0.05 if p_value else False,
    }


def compute_quiet_periods(events: List[Dict], min_gap_days: int = 3) -> List[Dict]:
    """
    Identify periods where Alon stopped tweeting.
    """
    if not events:
        return []
    
    DAY = 86400
    sorted_events = sorted(events, key=lambda x: x["timestamp"])
    
    quiet_periods = []
    prev_ts = None
    
    for event in sorted_events:
        ts = event["timestamp"]
        
        if prev_ts is not None:
            gap_days = (ts - prev_ts) / DAY
            if gap_days >= min_gap_days:
                quiet_periods.append({
                    "start_ts": prev_ts,
                    "end_ts": ts,
                    "gap_days": round(gap_days, 1),
                    "start_date": datetime.utcfromtimestamp(prev_ts).strftime("%Y-%m-%d"),
                    "end_date": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
                })
        
        prev_ts = ts
    
    # Check if currently in quiet period
    last_ts = sorted_events[-1]["timestamp"]
    now_ts = int(datetime.utcnow().timestamp())
    gap_days = (now_ts - last_ts) / DAY
    
    if gap_days >= min_gap_days:
        quiet_periods.append({
            "start_ts": last_ts,
            "end_ts": now_ts,
            "gap_days": round(gap_days, 1),
            "start_date": datetime.utcfromtimestamp(last_ts).strftime("%Y-%m-%d"),
            "end_date": "ongoing",
            "is_current": True,
        })
    
    return quiet_periods


def compute_quiet_period_impact(
    quiet_periods: List[Dict],
    daily_prices: Dict[int, float]
) -> List[Dict]:
    """
    Calculate price impact during each quiet period.
    """
    sorted_days = sorted(daily_prices.keys())
    
    results = []
    for qp in quiet_periods:
        start_ts = qp["start_ts"]
        end_ts = qp["end_ts"]
        
        # Find price at start (closest day)
        start_price = None
        for day in sorted_days:
            if day >= start_ts:
                start_price = daily_prices.get(day)
                break
        
        # Find price at end (closest day)
        end_price = None
        for day in reversed(sorted_days):
            if day <= end_ts:
                end_price = daily_prices.get(day)
                break
        
        # Calculate change
        change_pct = None
        if start_price and end_price:
            change_pct = round((end_price - start_price) / start_price * 100, 1)
        
        results.append({
            **qp,
            "price_start": start_price,
            "price_end": end_price,
            "change_pct": change_pct,
        })
    
    return results


def compute_correlation(
    events: List[Dict],
    daily_prices: Dict[int, float]
) -> Dict:
    """
    Compute correlation between 7-day tweet count and price.
    """
    DAY = 86400
    
    # Build 7-day rolling tweet count for each day
    tweet_timestamps = [e["timestamp"] for e in events]
    sorted_days = sorted(daily_prices.keys())
    
    rolling_counts = []
    prices = []
    
    for day in sorted_days:
        # Count tweets in prior 7 days
        week_start = day - (7 * DAY)
        count = sum(1 for t in tweet_timestamps if week_start <= t < day)
        rolling_counts.append(count)
        prices.append(daily_prices[day])
    
    # Pearson correlation
    if len(rolling_counts) >= 10:
        corr, p_val = stats.pearsonr(rolling_counts, prices)
        return {
            "correlation_7d": round(corr, 3),
            "p_value": round(p_val, 4),
            "significant": p_val < 0.05,
            "sample_size": len(rolling_counts),
        }
    
    return {}


def main():
    """Compute and save all statistics."""
    print("=" * 60)
    print("Computing Statistics")
    print("=" * 60)
    
    # Load data
    print("\nLoading data...")
    events = load_tweet_events()
    print(f"  Tweet events: {len(events)}")
    
    conn = sqlite3.connect(PRICES_DB)
    daily_prices = load_daily_prices(conn)
    print(f"  Daily prices: {len(daily_prices)}")
    conn.close()
    
    if not events or not daily_prices:
        print("Missing data, cannot compute stats")
        return
    
    # Compute all stats
    print("\nComputing tweet day vs no-tweet day stats...")
    daily_stats = compute_daily_stats(events, daily_prices)
    
    print("Computing quiet periods...")
    quiet_periods = compute_quiet_periods(events)
    quiet_with_impact = compute_quiet_period_impact(quiet_periods, daily_prices)
    
    print("Computing correlations...")
    correlation = compute_correlation(events, daily_prices)
    
    # Find current status
    current_quiet = next((q for q in quiet_with_impact if q.get("is_current")), None)
    
    # Assemble final stats
    stats_output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_tweets": len(events),
            "tweets_with_price": sum(1 for e in events if e.get("price_at_tweet")),
            "date_range": {
                "start": events[0]["timestamp_iso"][:10] if events else None,
                "end": events[-1]["timestamp_iso"][:10] if events else None,
            }
        },
        "daily_comparison": daily_stats,
        "correlation": correlation,
        "current_status": {
            "days_since_last_tweet": int(current_quiet["gap_days"]) if current_quiet else 0,
            "price_change_during_silence": current_quiet["change_pct"] if current_quiet else None,
            "last_tweet_date": current_quiet["start_date"] if current_quiet else None,
        } if current_quiet else {
            "days_since_last_tweet": 0,
            "price_change_during_silence": None,
            "last_tweet_date": events[-1]["timestamp_iso"][:10] if events else None,
        },
        "quiet_periods": quiet_with_impact,
    }
    
    # Save to data directory
    output_path = DATA_DIR / "stats.json"
    with open(output_path, "w") as f:
        json.dump(stats_output, f, indent=2, cls=NumpyEncoder)
    print(f"\nSaved stats to {output_path}")
    
    # Also save to public directory
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    public_path = PUBLIC_DATA_DIR / "stats.json"
    with open(public_path, "w") as f:
        json.dump(stats_output, f, indent=2, cls=NumpyEncoder)
    print(f"Saved stats to {public_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("STATISTICS SUMMARY")
    print("=" * 60)
    print(f"\nTweet Days:")
    print(f"  Count: {daily_stats['tweet_day_count']}")
    print(f"  Avg Return: {daily_stats['tweet_day_avg_return']:+.2f}%")
    print(f"  Win Rate: {daily_stats['tweet_day_win_rate']:.1f}%")
    
    print(f"\nNo-Tweet Days:")
    print(f"  Count: {daily_stats['no_tweet_day_count']}")
    print(f"  Avg Return: {daily_stats['no_tweet_day_avg_return']:+.2f}%")
    print(f"  Win Rate: {daily_stats['no_tweet_day_win_rate']:.1f}%")
    
    print(f"\nStatistical Significance: {'YES' if daily_stats['significant'] else 'NO'} (p={daily_stats['p_value']})")
    
    if correlation:
        print(f"\nCorrelation (7d tweets vs price): {correlation['correlation_7d']}")
    
    if current_quiet:
        print(f"\nCurrent Silence: {int(current_quiet['gap_days'])} days")
        print(f"Price Impact: {current_quiet['change_pct']:+.1f}%")


if __name__ == "__main__":
    main()

