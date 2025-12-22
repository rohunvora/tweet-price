'use client';

/**
 * ClusterDrawer - Slide-in panel showing tweets in a cluster
 * ============================================================
 * 
 * Opens when user clicks a cluster bubble on the chart.
 * Shows all tweets in that cluster with navigation options.
 * 
 * - Desktop: Slides in from right
 * - Mobile: Slides up from bottom (bottom sheet style)
 */

import { useEffect, useRef } from 'react';
import { TweetEvent } from '@/lib/types';

interface ClusterDrawerProps {
  /** All tweets in the clicked cluster */
  tweets: TweetEvent[];
  /** Callback to close the drawer */
  onClose: () => void;
  /** Callback when user wants to navigate to a specific tweet */
  onNavigate: (timestamp: number) => void;
  /** Founder Twitter handle (for tweet links) */
  founder: string;
  /** Asset accent color */
  assetColor: string;
}

/**
 * Decode HTML entities in text (&gt; &amp; &lt; etc)
 */
function decodeHtmlEntities(text: string): string {
  if (typeof document === 'undefined') return text;
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  return textarea.value;
}

/**
 * Format timestamp to readable date
 */
function formatDate(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function ClusterDrawer({
  tweets,
  onClose,
  onNavigate,
  founder,
  assetColor,
}: ClusterDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  // Sort tweets chronologically (oldest first)
  const sortedTweets = [...tweets].sort((a, b) => a.timestamp - b.timestamp);

  // Calculate cluster stats
  const firstTweet = sortedTweets[0];
  const lastTweet = sortedTweets[sortedTweets.length - 1];
  const startDate = new Date(firstTweet.timestamp * 1000);
  const endDate = new Date(lastTweet.timestamp * 1000);
  
  // Overall price change from first to last tweet in cluster
  const overallChange = firstTweet.price_at_tweet && lastTweet.price_at_tweet
    ? ((lastTweet.price_at_tweet - firstTweet.price_at_tweet) / firstTweet.price_at_tweet) * 100
    : null;

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Delay adding listener to avoid immediate close
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40 animate-fade-in" />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="
          fixed z-50 bg-[var(--surface-0)] shadow-2xl
          
          /* Mobile: Bottom sheet */
          bottom-0 left-0 right-0 max-h-[70vh] rounded-t-2xl
          animate-slide-up
          
          /* Desktop: Side drawer */
          md:bottom-auto md:top-0 md:left-auto md:right-0 
          md:w-[420px] md:h-full md:max-h-none md:rounded-t-none md:rounded-l-xl
          md:animate-slide-in-right
        "
      >
        {/* Header */}
        <div 
          className="sticky top-0 bg-[var(--surface-0)] border-b border-[var(--border-subtle)] px-4 py-3 flex items-center gap-3 rounded-t-2xl md:rounded-t-none md:rounded-tl-xl"
        >
          {/* Drag handle (mobile only) */}
          <div className="absolute top-2 left-1/2 -translate-x-1/2 w-10 h-1 bg-[var(--border-default)] rounded-full md:hidden" />
          
          {/* Cluster info */}
          <div className="flex-1 mt-2 md:mt-0">
            <div className="flex items-center gap-2">
              <span 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: assetColor }}
              />
              <span className="font-semibold text-[var(--text-primary)]">
                {tweets.length} tweet{tweets.length > 1 ? 's' : ''}
              </span>
              {overallChange !== null && (
                <span className={`text-sm font-mono ${overallChange >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                  {overallChange >= 0 ? '+' : ''}{overallChange.toFixed(1)}%
                </span>
              )}
            </div>
            <div className="text-xs text-[var(--text-muted)] mt-0.5">
              {startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              {tweets.length > 1 && startDate.toDateString() !== endDate.toDateString() && (
                <> – {endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</>
              )}
            </div>
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-1)] transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Tweet list */}
        <div className="overflow-y-auto max-h-[calc(70vh-60px)] md:max-h-[calc(100vh-60px)]">
          {sortedTweets.map((tweet, index) => {
            const change = tweet.change_24h_pct;
            const isPositive = change !== null && change >= 0;
            const decodedText = decodeHtmlEntities(tweet.text);

            return (
              <div
                key={tweet.tweet_id}
                className="px-4 py-3 border-b border-[var(--border-subtle)] hover:bg-[var(--surface-1)] transition-colors"
              >
                <div className="flex items-start gap-3">
                  {/* Tweet number indicator */}
                  <div 
                    className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium"
                    style={{ 
                      backgroundColor: `${assetColor}20`,
                      color: assetColor 
                    }}
                  >
                    {index + 1}
                  </div>

                  {/* Tweet content */}
                  <div className="flex-1 min-w-0">
                    {/* Tweet text (links to Twitter) */}
                    <a
                      href={`https://twitter.com/${founder}/status/${tweet.tweet_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block group"
                    >
                      <p className="text-sm text-[var(--text-primary)] line-clamp-3 group-hover:text-[var(--accent)] transition-colors">
                        {decodedText}
                      </p>
                    </a>

                    {/* Date + price info */}
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-[var(--text-muted)]">
                      <span>{formatDate(tweet.timestamp)}</span>
                      {tweet.price_at_tweet && (
                        <>
                          <span>•</span>
                          <span className="tabular-nums">${tweet.price_at_tweet.toFixed(6)}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Right side: % change + chart button */}
                  <div className="flex-shrink-0 flex items-center gap-2">
                    {/* 24h change */}
                    {change !== null ? (
                      <span className={`font-mono text-sm font-semibold tabular-nums ${isPositive ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                        {isPositive ? '+' : ''}{change.toFixed(1)}%
                      </span>
                    ) : (
                      <span className="text-[var(--text-disabled)] text-sm">—</span>
                    )}

                    {/* Navigate to chart button */}
                    <button
                      onClick={() => onNavigate(tweet.timestamp)}
                      className="p-2 rounded-md text-[var(--text-muted)] hover:text-[var(--accent)] hover:bg-[var(--surface-2)] transition-colors"
                      title="Zoom to this tweet on chart"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M2 12L5.5 8.5L8 11L14 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M10 5H14V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer hint */}
        <div className="sticky bottom-0 bg-[var(--surface-0)] border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-muted)] text-center">
          Click chart icon to zoom • Click tweet to open on X
        </div>
      </div>
    </>
  );
}

