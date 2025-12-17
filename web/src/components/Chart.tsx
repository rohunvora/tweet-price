'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  CrosshairMode,
  MouseEventParams,
} from 'lightweight-charts';
import { Timeframe, TweetEvent, Candle } from '@/lib/types';
import { loadPrices, toCandlestickData } from '@/lib/dataLoader';

interface ChartProps {
  tweetEvents: TweetEvent[];
}

const TIMEFRAMES: { label: string; value: Timeframe }[] = [
  { label: '1m', value: '1m' },
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '1D', value: '1d' },
];

export default function Chart({ tweetEvents }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersCanvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Default to 1D to show full history (user hasn't tweeted in 42+ days)
  const [timeframe, setTimeframe] = useState<Timeframe>('1d');
  const [loading, setLoading] = useState(true);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [showBubbles, setShowBubbles] = useState(true);
  const [hoveredTweet, setHoveredTweet] = useState<TweetEvent | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  
  // Avatar cache
  const avatarCacheRef = useRef<Map<string, HTMLImageElement>>(new Map());
  const defaultAvatarRef = useRef<HTMLImageElement | null>(null);

  // Load avatars
  useEffect(() => {
    // Load default Alon avatar
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = '/avatars/a1lon9.png';
    img.onload = () => {
      defaultAvatarRef.current = img;
      drawMarkers();
    };
  }, []);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const chart = createChart(container, {
      width: width || 800,
      height: height || 500,
      layout: {
        background: { color: '#131722' },
        textColor: '#D1D4DC',
      },
      grid: {
        vertLines: { color: '#1E222D' },
        horzLines: { color: '#1E222D' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#758696',
          width: 1,
          style: 0,
          labelBackgroundColor: '#2A2E39',
        },
        horzLine: {
          color: '#758696',
          width: 1,
          style: 0,
          labelBackgroundColor: '#2A2E39',
        },
      },
      timeScale: {
        borderColor: '#2A2E39',
        timeVisible: true,
        secondsVisible: false,
        // Enable mouse wheel zoom on time axis
        rightOffset: 5,
        minBarSpacing: 0.5,
      },
      rightPriceScale: {
        borderColor: '#2A2E39',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      // Enable all interactions
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: {
          time: true,
          price: true,
        },
        axisDoubleClickReset: {
          time: true,
          price: true,
        },
        mouseWheel: true,
        pinch: true,
      },
      localization: {
        priceFormatter: (price: number) => {
          if (price >= 1) return price.toFixed(2);
          if (price >= 0.01) return price.toFixed(4);
          return price.toFixed(6);
        },
      },
    });

    const series = chart.addCandlestickSeries({
      upColor: '#26A69A',
      downColor: '#EF5350',
      borderUpColor: '#26A69A',
      borderDownColor: '#EF5350',
      wickUpColor: '#26A69A',
      wickDownColor: '#EF5350',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle resize
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.applyOptions({ width, height });
          drawMarkers();
        }
      }
    });
    resizeObserver.observe(container);

    // Redraw markers on visible range change (zoom/pan)
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
      drawMarkers();
    });

    // Subscribe to crosshair move for hover detection
    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      handleCrosshairMove(param);
    });

    // Subscribe to click events
    chart.subscribeClick((param: MouseEventParams) => {
      handleChartClick(param);
    });

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  // Handle crosshair move to detect tweet marker hover
  const handleCrosshairMove = useCallback((param: MouseEventParams) => {
    if (!chartRef.current || !seriesRef.current || !showBubbles) {
      setHoveredTweet(null);
      return;
    }

    const chart = chartRef.current;
    const series = seriesRef.current;
    
    if (!param.point) {
      setHoveredTweet(null);
      return;
    }

    const { x, y } = param.point;
    setMousePos({ x, y });

    const HOVER_RADIUS = 24;

    // Find hovered tweet
    let found: TweetEvent | null = null;
    let foundX = 0, foundY = 0;

    for (const tweet of tweetEvents) {
      if (!tweet.price_at_tweet) continue;

      const tx = chart.timeScale().timeToCoordinate(tweet.timestamp as Time);
      const ty = series.priceToCoordinate(tweet.price_at_tweet);

      if (tx === null || ty === null) continue;

      const dist = Math.hypot(tx - x, ty - y);
      if (dist < HOVER_RADIUS) {
        found = tweet;
        foundX = tx;
        foundY = ty;
        break;
      }
    }

    if (found) {
      setHoveredTweet(found);
      setTooltipPos({ x: foundX, y: foundY });
    } else {
      setHoveredTweet(null);
    }
  }, [tweetEvents, showBubbles]);

  // Handle chart click for opening tweet
  const handleChartClick = useCallback((param: MouseEventParams) => {
    if (!chartRef.current || !seriesRef.current || !showBubbles) return;

    const chart = chartRef.current;
    const series = seriesRef.current;
    
    if (!param.point) return;

    const { x, y } = param.point;
    const CLICK_RADIUS = 24;

    for (const tweet of tweetEvents) {
      if (!tweet.price_at_tweet) continue;

      const tx = chart.timeScale().timeToCoordinate(tweet.timestamp as Time);
      const ty = series.priceToCoordinate(tweet.price_at_tweet);

      if (tx === null || ty === null) continue;

      const dist = Math.hypot(tx - x, ty - y);
      if (dist < CLICK_RADIUS) {
        window.open(
          `https://twitter.com/a1lon9/status/${tweet.tweet_id}`,
          '_blank'
        );
        break;
      }
    }
  }, [tweetEvents, showBubbles]);

  // Load data when timeframe changes
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const priceData = await loadPrices(timeframe);
        setCandles(priceData.candles);
        
        if (seriesRef.current && chartRef.current) {
          const chartData = toCandlestickData(priceData);
          seriesRef.current.setData(chartData as CandlestickData<Time>[]);
          
          // Smart initial positioning: show from first tweet with price to now
          const tweetsWithPrice = tweetEvents.filter(t => t.price_at_tweet !== null);
          if (tweetsWithPrice.length > 0 && priceData.candles.length > 0) {
            const firstTweetTime = tweetsWithPrice[0].timestamp;
            const lastDataTime = priceData.end;
            
            // Set visible range to show all tweets + current period
            chartRef.current.timeScale().setVisibleRange({
              from: firstTweetTime as Time,
              to: lastDataTime as Time,
            });
          } else {
            chartRef.current.timeScale().fitContent();
          }
          
          // Draw markers after data is set
          setTimeout(() => drawMarkers(), 100);
        }
      } catch (error) {
        console.error('Failed to load price data:', error);
      }
      setLoading(false);
    }
    loadData();
  }, [timeframe, tweetEvents]);

  // Redraw markers when bubbles toggle changes
  useEffect(() => {
    drawMarkers();
  }, [showBubbles, tweetEvents]);

  // Draw tweet markers on canvas
  const drawMarkers = useCallback(() => {
    if (!chartRef.current || !seriesRef.current || !showBubbles) {
      // Clear canvas if bubbles are off
      const canvas = markersCanvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    const canvas = markersCanvasRef.current;
    if (!canvas) return;

    const container = containerRef.current;
    if (!container) return;

    // Set canvas size with device pixel ratio for sharp rendering
    const dpr = window.devicePixelRatio || 1;
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const chart = chartRef.current;
    const series = seriesRef.current;
    const avatar = defaultAvatarRef.current;

    const BUBBLE_SIZE = 28;
    const BUBBLE_RADIUS = BUBBLE_SIZE / 2;

    // Get visible range
    const visibleRange = chart.timeScale().getVisibleRange();
    if (!visibleRange) return;

    // Filter tweets in visible range with price data
    const visibleTweets = tweetEvents.filter(tweet => {
      if (!tweet.price_at_tweet) return false;
      const time = tweet.timestamp;
      return time >= (visibleRange.from as number) && time <= (visibleRange.to as number);
    });

    // Draw each tweet bubble
    for (const tweet of visibleTweets) {
      const x = chart.timeScale().timeToCoordinate(tweet.timestamp as Time);
      const y = series.priceToCoordinate(tweet.price_at_tweet!);

      if (x === null || y === null) continue;

      // Draw white circle border
      ctx.beginPath();
      ctx.arc(x, y, BUBBLE_RADIUS + 2, 0, Math.PI * 2);
      ctx.strokeStyle = hoveredTweet?.tweet_id === tweet.tweet_id ? '#2962FF' : '#FFFFFF';
      ctx.lineWidth = hoveredTweet?.tweet_id === tweet.tweet_id ? 3 : 2;
      ctx.stroke();

      // Draw avatar or fallback
      if (avatar) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(x, y, BUBBLE_RADIUS, 0, Math.PI * 2);
        ctx.clip();
        ctx.drawImage(
          avatar,
          x - BUBBLE_RADIUS,
          y - BUBBLE_RADIUS,
          BUBBLE_SIZE,
          BUBBLE_SIZE
        );
        ctx.restore();
      } else {
        ctx.beginPath();
        ctx.arc(x, y, BUBBLE_RADIUS, 0, Math.PI * 2);
        ctx.fillStyle = '#2962FF';
        ctx.fill();
      }
    }
  }, [tweetEvents, showBubbles, hoveredTweet]);

  // Redraw when hovered tweet changes (for highlight effect)
  useEffect(() => {
    drawMarkers();
  }, [hoveredTweet, drawMarkers]);

  // Helper to jump to a specific time period
  const jumpToLastTweet = useCallback(() => {
    if (!chartRef.current || tweetEvents.length === 0) return;
    
    const tweetsWithPrice = tweetEvents.filter(t => t.price_at_tweet !== null);
    if (tweetsWithPrice.length === 0) return;
    
    const lastTweet = tweetsWithPrice[tweetsWithPrice.length - 1];
    const now = Math.floor(Date.now() / 1000);
    
    // Show 7 days before last tweet to now
    const from = lastTweet.timestamp - (7 * 24 * 60 * 60);
    const to = now;
    
    chartRef.current.timeScale().setVisibleRange({
      from: from as Time,
      to: to as Time,
    });
  }, [tweetEvents]);

  const jumpToAllTime = useCallback(() => {
    if (!chartRef.current) return;
    chartRef.current.timeScale().fitContent();
  }, []);

  return (
    <div className="relative w-full h-full bg-[#131722]">
      {/* Chart container - receives all pointer events */}
      <div ref={containerRef} className="absolute inset-0" />
      
      {/* Markers canvas overlay - pointer-events NONE to allow chart interaction */}
      <canvas
        ref={markersCanvasRef}
        className="absolute inset-0"
        style={{ 
          zIndex: 10, 
          pointerEvents: 'none'  // Critical: let events pass through to chart
        }}
      />

      {/* Top controls bar */}
      <div className="absolute top-2 left-2 z-20 flex items-center gap-2">
        {/* Bubble toggle */}
        <button
          onClick={() => setShowBubbles(!showBubbles)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs transition-colors ${
            showBubbles 
              ? 'bg-[#2962FF] text-white' 
              : 'bg-[#2A2E39] text-[#787B86] hover:text-[#D1D4DC]'
          }`}
        >
          <span>🐦</span>
          <span>{showBubbles ? 'Hide' : 'Show'} Tweets</span>
        </button>

        {/* Quick navigation buttons */}
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={jumpToLastTweet}
            className="px-2 py-1 text-xs text-[#787B86] hover:text-[#D1D4DC] hover:bg-[#2A2E39] rounded transition-colors"
            title="Jump to last tweet period"
          >
            Last Tweet
          </button>
          <button
            onClick={jumpToAllTime}
            className="px-2 py-1 text-xs text-[#787B86] hover:text-[#D1D4DC] hover:bg-[#2A2E39] rounded transition-colors"
            title="Show all data"
          >
            All Time
          </button>
        </div>
      </div>

      {/* Timeframe selector - TradingView style at bottom */}
      <div className="absolute bottom-2 left-2 flex items-center gap-1 z-20">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.value}
            onClick={() => setTimeframe(tf.value)}
            className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
              timeframe === tf.value
                ? 'bg-[#2962FF] text-white'
                : 'text-[#787B86] hover:text-[#D1D4DC] hover:bg-[#2A2E39]'
            }`}
          >
            {tf.label}
          </button>
        ))}
        
        {/* Interaction hint */}
        <span className="ml-3 text-[10px] text-[#555] select-none">
          Drag to pan • Scroll to zoom • Double-click to reset
        </span>
      </div>

      {/* Loading indicator */}
      {loading && (
        <div className="absolute top-2 right-2 z-20 flex items-center gap-2 bg-[#1E222D] px-3 py-1 rounded">
          <div className="w-3 h-3 border-2 border-[#2962FF] border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-[#787B86]">Loading...</span>
        </div>
      )}

      {/* Cursor indicator when hovering tweet */}
      {hoveredTweet && (
        <div 
          className="absolute z-15 pointer-events-none"
          style={{
            left: tooltipPos.x - 14,
            top: tooltipPos.y - 14,
            width: 28,
            height: 28,
          }}
        >
          <div className="w-full h-full rounded-full border-2 border-[#2962FF] animate-pulse" />
        </div>
      )}

      {/* Tooltip */}
      {hoveredTweet && (
        <div
          className="absolute z-30 pointer-events-none bg-[#1E222D] border border-[#2A2E39] rounded-lg p-3 shadow-xl max-w-xs"
          style={{
            left: Math.min(tooltipPos.x + 20, (containerRef.current?.clientWidth || 400) - 300),
            top: Math.max(tooltipPos.y - 60, 10),
          }}
        >
          <div className="flex items-start gap-2 mb-2">
            <img src="/avatars/a1lon9.png" alt="Alon" className="w-8 h-8 rounded-full" />
            <div>
              <div className="text-[#D1D4DC] font-medium text-sm">@a1lon9</div>
              <div className="text-[#787B86] text-xs">
                {new Date(hoveredTweet.timestamp * 1000).toLocaleString()}
              </div>
            </div>
          </div>
          <p className="text-sm text-[#D1D4DC] line-clamp-3 mb-2">
            {hoveredTweet.text}
          </p>
          <div className="flex items-center gap-4 text-xs text-[#787B86]">
            <span>❤️ {hoveredTweet.likes.toLocaleString()}</span>
            <span>🔁 {hoveredTweet.retweets.toLocaleString()}</span>
          </div>
          {hoveredTweet.change_1h_pct !== null && (
            <div className="mt-2 pt-2 border-t border-[#2A2E39] flex items-center gap-3 text-xs">
              <span className="text-[#787B86]">Price impact:</span>
              <span className={hoveredTweet.change_1h_pct >= 0 ? 'text-[#26A69A]' : 'text-[#EF5350]'}>
                1h: {hoveredTweet.change_1h_pct >= 0 ? '+' : ''}{hoveredTweet.change_1h_pct.toFixed(1)}%
              </span>
              {hoveredTweet.change_24h_pct !== null && (
                <span className={hoveredTweet.change_24h_pct >= 0 ? 'text-[#26A69A]' : 'text-[#EF5350]'}>
                  24h: {hoveredTweet.change_24h_pct >= 0 ? '+' : ''}{hoveredTweet.change_24h_pct.toFixed(1)}%
                </span>
              )}
            </div>
          )}
          <div className="mt-2 text-xs text-[#2962FF]">
            Click bubble to view tweet →
          </div>
        </div>
      )}
    </div>
  );
}
