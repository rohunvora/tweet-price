'use client';

import { Stats } from '@/lib/types';

interface StatsPanelProps {
  stats: Stats;
  founderName: string;
}

export default function StatsPanel({ stats, founderName }: StatsPanelProps) {
  const { daily_comparison, correlation, current_status } = stats;
  
  // Capitalize first letter of founder name for display
  const displayName = founderName.charAt(0).toUpperCase() + founderName.slice(1);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4">
      {/* Current Status - Hero */}
      <div className="md:col-span-3 bg-gradient-to-r from-[#161B22] to-[#0D1117] border border-[#30363D] rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-[#8B949E] mb-1">
              Current Silence
            </h2>
            <div className="flex items-baseline gap-3">
              <span className="text-5xl font-bold text-[#F85149]">
                {current_status.days_since_last_tweet}
              </span>
              <span className="text-xl text-[#8B949E]">days</span>
            </div>
            <p className="text-sm text-[#6E7681] mt-2">
              Last tweet: {current_status.last_tweet_date}
            </p>
          </div>
          
          {current_status.price_change_during_silence !== null && (
            <div className="text-right">
              <p className="text-sm text-[#8B949E] mb-1">Price Impact</p>
              <span className={`text-4xl font-bold ${
                current_status.price_change_during_silence >= 0 
                  ? 'text-[#3FB950]' 
                  : 'text-[#F85149]'
              }`}>
                {current_status.price_change_during_silence >= 0 ? '+' : ''}
                {current_status.price_change_during_silence.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Tweet Days */}
      <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
        <h3 className="text-sm font-medium text-[#3FB950] mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#3FB950] rounded-full"></span>
          When {displayName} Tweets
        </h3>
        <div className="space-y-3">
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">Avg Return</span>
            <span className={`text-2xl font-bold ${
              daily_comparison.tweet_day_avg_return >= 0 
                ? 'text-[#3FB950]' 
                : 'text-[#F85149]'
            }`}>
              {daily_comparison.tweet_day_avg_return >= 0 ? '+' : ''}
              {daily_comparison.tweet_day_avg_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">Win Rate</span>
            <span className="text-xl font-semibold text-[#C9D1D9]">
              {daily_comparison.tweet_day_win_rate.toFixed(0)}%
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#6E7681]">Sample Size</span>
            <span className="text-[#8B949E]">
              {daily_comparison.tweet_day_count} days
            </span>
          </div>
        </div>
      </div>

      {/* No-Tweet Days */}
      <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
        <h3 className="text-sm font-medium text-[#F85149] mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#F85149] rounded-full"></span>
          When {displayName} is Silent
        </h3>
        <div className="space-y-3">
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">Avg Return</span>
            <span className={`text-2xl font-bold ${
              daily_comparison.no_tweet_day_avg_return >= 0 
                ? 'text-[#3FB950]' 
                : 'text-[#F85149]'
            }`}>
              {daily_comparison.no_tweet_day_avg_return >= 0 ? '+' : ''}
              {daily_comparison.no_tweet_day_avg_return.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">Win Rate</span>
            <span className="text-xl font-semibold text-[#C9D1D9]">
              {daily_comparison.no_tweet_day_win_rate.toFixed(0)}%
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#6E7681]">Sample Size</span>
            <span className="text-[#8B949E]">
              {daily_comparison.no_tweet_day_count} days
            </span>
          </div>
        </div>
      </div>

      {/* Correlation */}
      <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
        <h3 className="text-sm font-medium text-[#58A6FF] mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#58A6FF] rounded-full"></span>
          Statistical Correlation
        </h3>
        <div className="space-y-3">
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">7d Tweet-Price</span>
            <span className="text-2xl font-bold text-[#C9D1D9]">
              {correlation.correlation_7d.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#8B949E]">Significant?</span>
            <span className={`text-xl font-semibold ${
              daily_comparison.significant ? 'text-[#3FB950]' : 'text-[#F85149]'
            }`}>
              {daily_comparison.significant ? 'YES' : 'NO'}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-[#6E7681]">p-value</span>
            <span className="text-[#8B949E] font-mono">
              {daily_comparison.p_value?.toFixed(4) ?? 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="md:col-span-3 text-center text-xs text-[#6E7681] py-2">
        Price data from GeckoTerminal. Tweet data from X API. 
        This is not financial advice. DYOR.
      </div>
    </div>
  );
}
