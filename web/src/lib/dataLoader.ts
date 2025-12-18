import { PriceData, Timeframe, Candle, TweetEvent } from './types';

// Cache for loaded price data
const priceCache = new Map<string, PriceData>();

/**
 * Load price data for a specific timeframe
 */
export async function loadPrices(timeframe: Timeframe): Promise<PriceData> {
  const cacheKey = timeframe;
  
  if (priceCache.has(cacheKey)) {
    return priceCache.get(cacheKey)!;
  }
  
  // For 1m, we need to load the index and potentially multiple chunks
  if (timeframe === '1m') {
    return load1mPrices();
  }
  
  const response = await fetch(`/data/prices_${timeframe}.json`);
  const data: PriceData = await response.json();
  
  priceCache.set(cacheKey, data);
  return data;
}

/**
 * Load 1m prices (chunked by month for performance)
 */
async function load1mPrices(): Promise<PriceData> {
  if (priceCache.has('1m')) {
    return priceCache.get('1m')!;
  }
  
  // Load index
  const indexResponse = await fetch('/data/prices_1m_index.json');
  const index = await indexResponse.json();
  
  // Load all chunks in parallel
  const chunkPromises = index.chunks.map(async (chunk: { file: string }) => {
    const response = await fetch(`/data/${chunk.file}`);
    return response.json();
  });
  
  const chunks = await Promise.all(chunkPromises);
  
  // Merge all candles
  const allCandles: Candle[] = [];
  for (const chunk of chunks) {
    allCandles.push(...chunk.candles);
  }
  
  // Sort by timestamp
  allCandles.sort((a, b) => a.t - b.t);
  
  const merged: PriceData = {
    timeframe: '1m',
    count: allCandles.length,
    start: allCandles[0]?.t || 0,
    end: allCandles[allCandles.length - 1]?.t || 0,
    candles: allCandles,
  };
  
  priceCache.set('1m', merged);
  return merged;
}

/**
 * Load tweet events data
 */
export async function loadTweetEvents() {
  const response = await fetch('/data/tweet_events.json');
  return response.json();
}

/**
 * Load pre-computed statistics
 */
export async function loadStats() {
  const response = await fetch('/data/stats.json');
  return response.json();
}

/**
 * Convert price data to Lightweight Charts candlestick format
 */
export function toCandlestickData(prices: PriceData) {
  return prices.candles.map(c => ({
    time: c.t as number,
    open: c.o,
    high: c.h,
    low: c.l,
    close: c.c,
  }));
}

/**
 * Get sorted array of tweet timestamps for binary search
 */
export function getSortedTweetTimestamps(tweets: TweetEvent[]): number[] {
  return tweets
    .filter(t => t.price_at_tweet !== null)
    .map(t => t.timestamp)
    .sort((a, b) => a - b);
}
