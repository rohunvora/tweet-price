"""
Export price data as static JSON files for the frontend.
Chunked by timeframe for efficient loading.
"""
from typing import List, Dict
import json
import gzip
import sqlite3
from datetime import datetime
from config import DATA_DIR, PRICES_DB, PUBLIC_DATA_DIR, TIMEFRAMES


def export_timeframe(
    conn: sqlite3.Connection,
    timeframe: str,
    output_dir=PUBLIC_DATA_DIR,
    compress: bool = False
) -> int:
    """
    Export all data for a timeframe to JSON.
    Returns number of candles exported.
    """
    cursor = conn.execute("""
        SELECT timestamp_epoch, open, high, low, close, volume
        FROM ohlcv
        WHERE timeframe = ?
        ORDER BY timestamp_epoch
    """, (timeframe,))
    
    candles = []
    for row in cursor:
        ts, o, h, l, c, v = row
        # Compact format for smaller files
        candles.append({
            "t": ts,  # timestamp (epoch)
            "o": round(o, 8),
            "h": round(h, 8),
            "l": round(l, 8),
            "c": round(c, 8),
            "v": round(v, 2),
        })
    
    if not candles:
        return 0
    
    output = {
        "timeframe": timeframe,
        "count": len(candles),
        "start": candles[0]["t"],
        "end": candles[-1]["t"],
        "candles": candles
    }
    
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"prices_{timeframe}.json"
    filepath = output_dir / filename
    
    if compress:
        filepath = output_dir / f"{filename}.gz"
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            json.dump(output, f, separators=(",", ":"))
    else:
        with open(filepath, "w") as f:
            json.dump(output, f, separators=(",", ":"))
    
    # Calculate file size
    size_kb = filepath.stat().st_size / 1024
    print(f"  {timeframe}: {len(candles):,} candles → {filename} ({size_kb:.1f} KB)")
    
    return len(candles)


def export_1m_chunked(
    conn: sqlite3.Connection,
    output_dir=PUBLIC_DATA_DIR
) -> int:
    """
    Export 1m data chunked by month for lazy loading.
    """
    cursor = conn.execute("""
        SELECT timestamp_epoch, open, high, low, close, volume
        FROM ohlcv
        WHERE timeframe = '1m'
        ORDER BY timestamp_epoch
    """)
    
    # Group by month
    months = {}
    for row in cursor:
        ts, o, h, l, c, v = row
        dt = datetime.utcfromtimestamp(ts)
        month_key = dt.strftime("%Y-%m")
        
        if month_key not in months:
            months[month_key] = []
        
        months[month_key].append({
            "t": ts,
            "o": round(o, 8),
            "h": round(h, 8),
            "l": round(l, 8),
            "c": round(c, 8),
            "v": round(v, 2),
        })
    
    if not months:
        return 0
    
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    
    for month_key, candles in sorted(months.items()):
        output = {
            "timeframe": "1m",
            "month": month_key,
            "count": len(candles),
            "start": candles[0]["t"],
            "end": candles[-1]["t"],
            "candles": candles
        }
        
        filename = f"prices_1m_{month_key}.json"
        filepath = output_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(output, f, separators=(",", ":"))
        
        size_kb = filepath.stat().st_size / 1024
        print(f"  1m/{month_key}: {len(candles):,} candles ({size_kb:.1f} KB)")
        total += len(candles)
    
    # Create index file for 1m chunks
    index = {
        "timeframe": "1m",
        "chunks": [
            {
                "month": month_key,
                "file": f"prices_1m_{month_key}.json",
                "count": len(candles),
                "start": candles[0]["t"],
                "end": candles[-1]["t"],
            }
            for month_key, candles in sorted(months.items())
        ]
    }
    
    with open(output_dir / "prices_1m_index.json", "w") as f:
        json.dump(index, f, indent=2)
    
    return total


def main():
    """Export all price data to static JSON files."""
    print("=" * 60)
    print("Exporting Static Price Data")
    print("=" * 60)
    print(f"Output: {PUBLIC_DATA_DIR}")
    
    conn = sqlite3.connect(PRICES_DB)
    
    # Export each timeframe (except 1m which is chunked)
    print("\nExporting timeframes:")
    for tf in ["1d", "1h", "15m"]:
        export_timeframe(conn, tf)
    
    # Export 1m chunked by month
    print("\nExporting 1m (chunked by month):")
    total_1m = export_1m_chunked(conn)
    print(f"  Total 1m: {total_1m:,} candles")
    
    conn.close()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    
    # List all files
    print("\nGenerated files:")
    for f in sorted(PUBLIC_DATA_DIR.glob("prices_*.json")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

