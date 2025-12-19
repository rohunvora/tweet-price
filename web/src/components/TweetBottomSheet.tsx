'use client';
import { Drawer } from 'vaul';
import { TweetEvent, Asset } from '@/lib/types';

interface TweetBottomSheetProps {
  tweet: TweetEvent | null;
  asset: Asset;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TweetBottomSheet({ tweet, asset, open, onOpenChange }: TweetBottomSheetProps) {
  if (!tweet) return null;

  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Drawer.Content className="fixed bottom-0 left-0 right-0 z-50 outline-none">
          <div className="bg-[#1E222D] rounded-t-2xl pb-safe">
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 bg-[#3A3E49] rounded-full" />
            </div>
            
            {/* Content */}
            <div className="px-4 pb-6">
              {/* Header */}
              <div className="flex items-center gap-3 mb-3">
                <img 
                  src={`/avatars/${asset.founder}.png`}
                  alt={asset.founder}
                  className="w-10 h-10 rounded-full"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
                <div>
                  <div className="text-[#D1D4DC] font-medium">@{asset.founder}</div>
                  <div className="text-[#787B86] text-sm">
                    {new Date(tweet.timestamp * 1000).toLocaleString()}
                  </div>
                </div>
              </div>
              
              {/* Tweet text */}
              <p className="text-[#D1D4DC] text-base leading-relaxed mb-4">
                {tweet.text}
              </p>
              
              {/* Engagement */}
              <div className="flex items-center gap-6 text-sm text-[#787B86] mb-4">
                <span>❤️ {tweet.likes.toLocaleString()}</span>
                <span>🔁 {tweet.retweets.toLocaleString()}</span>
              </div>
              
              {/* Price impact */}
              {tweet.price_at_tweet && (
                <div className="bg-[#131722] rounded-xl p-4 mb-4">
                  <div className="text-[#787B86] text-xs uppercase mb-2">Price Impact</div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="text-[#787B86] text-xs">At Tweet</div>
                      <div className="text-[#D1D4DC] font-mono">
                        ${tweet.price_at_tweet.toFixed(6)}
                      </div>
                    </div>
                    {tweet.change_1h_pct !== null && (
                      <div>
                        <div className="text-[#787B86] text-xs">+1 Hour</div>
                        <div className={`font-mono font-semibold ${
                          tweet.change_1h_pct >= 0 ? 'text-[#26A69A]' : 'text-[#EF5350]'
                        }`}>
                          {tweet.change_1h_pct >= 0 ? '+' : ''}{tweet.change_1h_pct.toFixed(1)}%
                        </div>
                      </div>
                    )}
                    {tweet.change_24h_pct !== null && (
                      <div>
                        <div className="text-[#787B86] text-xs">+24 Hours</div>
                        <div className={`font-mono font-semibold ${
                          tweet.change_24h_pct >= 0 ? 'text-[#26A69A]' : 'text-[#EF5350]'
                        }`}>
                          {tweet.change_24h_pct >= 0 ? '+' : ''}{tweet.change_24h_pct.toFixed(1)}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Action button */}
              <a
                href={`https://twitter.com/${asset.founder}/status/${tweet.tweet_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full py-3 text-center rounded-xl font-medium transition-colors"
                style={{ backgroundColor: asset.color, color: '#FFFFFF' }}
              >
                View on X
              </a>
            </div>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}

