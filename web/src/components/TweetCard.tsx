'use client';
import { TweetEvent } from '@/lib/types';

interface TweetCardProps {
  event: TweetEvent;
  founder: string;
}

export function TweetCard({ event, founder }: TweetCardProps) {
  const date = new Date(event.timestamp * 1000);
  
  return (
    <a
      href={`https://twitter.com/${founder}/status/${event.tweet_id}`}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#161B22] border border-[#30363D] rounded-xl p-4 mb-3 active:bg-[#1c2128] transition-colors"
    >
      {/* Header row */}
      <div className="flex justify-between items-start mb-2">
        <span className="text-[#8B949E] text-sm">
          {date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          <span className="text-[#6E7681] ml-1">
            {date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
          </span>
        </span>
        {event.change_24h_pct !== null && (
          <span className={`text-sm font-semibold ${
            event.change_24h_pct >= 0 ? 'text-[#26A69A]' : 'text-[#EF5350]'
          }`}>
            {event.change_24h_pct >= 0 ? '+' : ''}{event.change_24h_pct.toFixed(1)}%
          </span>
        )}
      </div>
      
      {/* Tweet text */}
      <p className="text-[#C9D1D9] text-sm leading-relaxed line-clamp-3 mb-3">
        {event.text}
      </p>
      
      {/* Footer row */}
      <div className="flex items-center gap-4 text-xs text-[#6E7681]">
        <span>❤️ {event.likes.toLocaleString()}</span>
        <span>🔁 {event.retweets.toLocaleString()}</span>
        {event.price_at_tweet && (
          <span className="ml-auto font-mono">${event.price_at_tweet.toFixed(4)}</span>
        )}
      </div>
    </a>
  );
}

