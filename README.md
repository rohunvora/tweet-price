# $PUMP Tweet-Price Correlation Analyzer

**Does Alon's tweeting correlate with $PUMP price?**

A tool to visualize and analyze the relationship between [@a1lon9](https://x.com/a1lon9)'s tweets and $PUMP token price movements.

## 🔗 Live Site

**https://tweet-price-rohun-voras-projects.vercel.app**

- `/chart` - Interactive candlestick chart with tweet markers
- `/data` - Stats panel and data table

## 📊 What It Shows

- **TradingView-style chart** with $PUMP price candles
- **Tweet markers** as avatar bubbles overlaid on the price chart
- **Silence gaps** - dashed lines showing quiet periods with % price change
- **Smart clustering** - nearby tweets grouped into single markers
- **Multiple timeframes** - 1m, 15m, 1h, 1D views

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- X API Bearer Token

### Setup

```bash
# Clone
git clone https://github.com/rohunvora/tweet-price.git
cd tweet-price

# Python setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with your X API token
echo "X_BEARER_TOKEN=your_token_here" > .env
```

### Fetch Data

```bash
python scripts/fetch_tweets.py      # Fetch tweets from @a1lon9
python scripts/fetch_prices.py      # Fetch $PUMP price data
python scripts/align_tweets.py      # Align tweets with prices
python scripts/export_static.py     # Export JSON for frontend
```

### Run Frontend

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000

## 📁 Project Structure

```
tweet-price/
├── scripts/
│   ├── config.py           # Configuration (pool address, API settings)
│   ├── fetch_tweets.py     # X API tweet fetcher
│   ├── fetch_prices.py     # GeckoTerminal price fetcher
│   ├── align_tweets.py     # Aligns tweets with prices
│   ├── export_static.py    # Exports static JSON
│   └── compute_stats.py    # Statistical calculations
│
├── data/                   # Raw data (gitignored)
│   ├── tweets.json        # Fetched tweets
│   ├── prices.db          # SQLite price database
│   └── tweet_events.json  # Aligned data
│
├── web/                    # Next.js frontend
│   ├── src/
│   │   ├── app/           # Pages
│   │   │   ├── chart/     # Chart page
│   │   │   └── data/      # Data table page
│   │   ├── components/
│   │   │   ├── Chart.tsx      # Main chart component
│   │   │   ├── DataTable.tsx  # Tweet data table
│   │   │   └── StatsPanel.tsx # Statistics display
│   │   └── lib/
│   │       ├── dataLoader.ts  # Data fetching utilities
│   │       ├── formatters.ts  # Format helpers
│   │       └── types.ts       # TypeScript types
│   │
│   └── public/data/       # Static JSON for frontend
│       ├── tweet_events.json
│       ├── stats.json
│       └── prices_*.json
│
└── vercel.json            # Vercel deployment config
```

## 🧮 How It Works

1. **Fetch tweets** from @a1lon9 via X API v2
2. **Fetch prices** from GeckoTerminal (Solana DEX data)
3. **Align** each tweet with the price at that exact minute
4. **Calculate** 1h and 24h price changes after each tweet
5. **Visualize** on an interactive chart with the tweet markers

### Chart Features

- **Tweet bubbles** - Avatar markers at price level when tweets occurred
- **Clustering** - Multiple tweets near each other merge into one bubble with count badge
- **Gap lines** - Dashed lines between clusters showing:
  - Time gap (e.g., "3d")
  - Price change during silence (e.g., "-20.6%")
- **Adaptive sizing** - Markers and labels scale based on zoom level

## ⚠️ Disclaimer

This is for **research and educational purposes only**. Not financial advice. Correlation ≠ causation. DYOR.

---

Built to explore whether founder activity correlates with token price 📊
