'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { TweetEvent, Candle } from '@/lib/types';

interface MarkerCanvasProps {
  tweetEvents: TweetEvent[];
  candles: Candle[];
  getCoordinateForPrice: (price: number) => number | null;
  getCoordinateForTime: (time: number) => number | null;
  visibleRange: { from: number; to: number } | null;
}

interface MarkerPosition {
  x: number;
  y: number;
  tweet: TweetEvent;
}

// Avatar image cache
const avatarCache = new Map<string, HTMLImageElement>();

export default function MarkerCanvas({
  tweetEvents,
  candles,
  getCoordinateForPrice,
  getCoordinateForTime,
  visibleRange,
}: MarkerCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredTweet, setHoveredTweet] = useState<TweetEvent | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const markersRef = useRef<MarkerPosition[]>([]);

  // Load avatar image
  useEffect(() => {
    if (!avatarCache.has('a1lon9')) {
      const img = new Image();
      img.src = '/avatars/a1lon9.png';
      img.onload = () => {
        avatarCache.set('a1lon9', img);
        // Trigger re-render
        drawMarkers();
      };
    }
  }, []);

  // Find price at tweet timestamp using binary search
  const findPriceAtTime = useCallback((timestamp: number): number | null => {
    if (candles.length === 0) return null;
    
    let left = 0;
    let right = candles.length - 1;
    
    while (left < right) {
      const mid = Math.floor((left + right + 1) / 2);
      if (candles[mid].t <= timestamp) {
        left = mid;
      } else {
        right = mid - 1;
      }
    }
    
    return candles[left]?.c ?? null;
  }, [candles]);

  // Draw markers on canvas
  const drawMarkers = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const markers: MarkerPosition[] = [];
    const avatar = avatarCache.get('a1lon9');
    const MARKER_SIZE = 24;
    const MARKER_RADIUS = MARKER_SIZE / 2;

    // Filter to tweets with price data in visible range
    const visibleTweets = tweetEvents.filter(tweet => {
      if (!tweet.price_at_tweet) return false;
      if (!visibleRange) return true;
      return tweet.timestamp >= visibleRange.from && tweet.timestamp <= visibleRange.to;
    });

    // Cluster overlapping markers
    const clustered = clusterMarkers(visibleTweets, getCoordinateForTime);

    for (const item of clustered) {
      if ('count' in item) {
        // Cluster marker
        const x = getCoordinateForTime(item.timestamp);
        const avgPrice = item.tweets.reduce((sum, t) => sum + (t.price_at_tweet || 0), 0) / item.tweets.length;
        const y = getCoordinateForPrice(avgPrice);

        if (x === null || y === null) continue;

        // Draw cluster circle
        ctx.beginPath();
        ctx.arc(x, y, MARKER_RADIUS + 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(88, 166, 255, 0.8)';
        ctx.fill();
        ctx.strokeStyle = '#58A6FF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw count
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 10px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`+${item.count}`, x, y);

        markers.push({ x, y, tweet: item.tweets[0] });
      } else {
        // Single tweet marker
        const tweet = item;
        const price = tweet.price_at_tweet || findPriceAtTime(tweet.timestamp);
        if (!price) continue;

        const x = getCoordinateForTime(tweet.timestamp);
        const y = getCoordinateForPrice(price);

        if (x === null || y === null) continue;

        // Draw circle border
        ctx.beginPath();
        ctx.arc(x, y, MARKER_RADIUS + 2, 0, Math.PI * 2);
        ctx.strokeStyle = '#58A6FF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw avatar or fallback circle
        if (avatar) {
          ctx.save();
          ctx.beginPath();
          ctx.arc(x, y, MARKER_RADIUS, 0, Math.PI * 2);
          ctx.clip();
          ctx.drawImage(
            avatar,
            x - MARKER_RADIUS,
            y - MARKER_RADIUS,
            MARKER_SIZE,
            MARKER_SIZE
          );
          ctx.restore();
        } else {
          ctx.beginPath();
          ctx.arc(x, y, MARKER_RADIUS, 0, Math.PI * 2);
          ctx.fillStyle = '#238636';
          ctx.fill();
        }

        markers.push({ x, y, tweet });
      }
    }

    markersRef.current = markers;
  }, [tweetEvents, candles, getCoordinateForPrice, getCoordinateForTime, visibleRange, findPriceAtTime]);

  // Redraw on changes
  useEffect(() => {
    drawMarkers();
  }, [drawMarkers]);

  // Handle resize
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    if (!parent) return;

    const resizeObserver = new ResizeObserver(() => {
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
      drawMarkers();
    });

    resizeObserver.observe(parent);
    return () => resizeObserver.disconnect();
  }, [drawMarkers]);

  // Handle mouse interaction
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if hovering over a marker
    const HOVER_RADIUS = 16;
    const hoveredMarker = markersRef.current.find(
      m => Math.hypot(m.x - x, m.y - y) < HOVER_RADIUS
    );

    if (hoveredMarker) {
      setHoveredTweet(hoveredMarker.tweet);
      setTooltipPos({ x: hoveredMarker.x, y: hoveredMarker.y - 40 });
      canvas.style.cursor = 'pointer';
    } else {
      setHoveredTweet(null);
      canvas.style.cursor = 'default';
    }
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const CLICK_RADIUS = 16;
    const clickedMarker = markersRef.current.find(
      m => Math.hypot(m.x - x, m.y - y) < CLICK_RADIUS
    );

    if (clickedMarker) {
      // Open tweet in new tab
      window.open(
        `https://twitter.com/a1lon9/status/${clickedMarker.tweet.tweet_id}`,
        '_blank'
      );
    }
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-auto z-10"
        onMouseMove={handleMouseMove}
        onClick={handleClick}
      />
      
      {/* Tooltip */}
      {hoveredTweet && (
        <div
          className="absolute z-20 pointer-events-none bg-[#161B22] border border-[#30363D] rounded-lg p-3 shadow-xl max-w-xs"
          style={{
            left: tooltipPos.x,
            top: tooltipPos.y,
            transform: 'translate(-50%, -100%)',
          }}
        >
          <p className="text-sm text-[#C9D1D9] line-clamp-3">
            {hoveredTweet.text}
          </p>
          <div className="mt-2 flex items-center gap-4 text-xs text-[#8B949E]">
            <span>❤️ {hoveredTweet.likes.toLocaleString()}</span>
            <span>🔁 {hoveredTweet.retweets.toLocaleString()}</span>
            {hoveredTweet.change_24h_pct !== null && (
              <span className={hoveredTweet.change_24h_pct >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}>
                {hoveredTweet.change_24h_pct >= 0 ? '+' : ''}{hoveredTweet.change_24h_pct.toFixed(1)}% (24h)
              </span>
            )}
          </div>
          <div className="mt-1 text-xs text-[#6E7681]">
            {new Date(hoveredTweet.timestamp * 1000).toLocaleString()}
          </div>
        </div>
      )}
    </>
  );
}

// Cluster overlapping markers
interface Cluster {
  timestamp: number;
  count: number;
  tweets: TweetEvent[];
}

function clusterMarkers(
  tweets: TweetEvent[],
  getX: (time: number) => number | null
): (TweetEvent | Cluster)[] {
  if (tweets.length === 0) return [];

  const CLUSTER_THRESHOLD = 20; // pixels
  const result: (TweetEvent | Cluster)[] = [];
  
  // Sort by timestamp
  const sorted = [...tweets].sort((a, b) => a.timestamp - b.timestamp);
  
  let currentCluster: TweetEvent[] = [sorted[0]];
  let clusterX = getX(sorted[0].timestamp);

  for (let i = 1; i < sorted.length; i++) {
    const tweet = sorted[i];
    const x = getX(tweet.timestamp);
    
    if (x !== null && clusterX !== null && Math.abs(x - clusterX) < CLUSTER_THRESHOLD) {
      currentCluster.push(tweet);
    } else {
      // Emit current cluster
      if (currentCluster.length > 1) {
        result.push({
          timestamp: currentCluster[Math.floor(currentCluster.length / 2)].timestamp,
          count: currentCluster.length,
          tweets: currentCluster,
        });
      } else {
        result.push(currentCluster[0]);
      }
      
      currentCluster = [tweet];
      clusterX = x;
    }
  }

  // Emit final cluster
  if (currentCluster.length > 1) {
    result.push({
      timestamp: currentCluster[Math.floor(currentCluster.length / 2)].timestamp,
      count: currentCluster.length,
      tweets: currentCluster,
    });
  } else if (currentCluster.length === 1) {
    result.push(currentCluster[0]);
  }

  return result;
}

