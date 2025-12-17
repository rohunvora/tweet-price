'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { loadTweetEvents, loadStats } from '@/lib/dataLoader';
import { TweetEvent, Stats } from '@/lib/types';
import DataTable from '@/components/DataTable';
import StatsPanel from '@/components/StatsPanel';

export default function DataPage() {
  const [tweetEvents, setTweetEvents] = useState<TweetEvent[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [eventsData, statsData] = await Promise.all([
          loadTweetEvents(),
          loadStats(),
        ]);
        setTweetEvents(eventsData.events);
        setStats(statsData);
      } catch (error) {
        console.error('Failed to load data:', error);
      }
      setLoading(false);
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D1117] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-[#58A6FF] border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-[#8B949E]">Loading data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D1117] flex flex-col">
      {/* Header */}
      <header className="border-b border-[#30363D] bg-[#161B22]">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-[#C9D1D9]">
                $PUMP Tweet Analysis
              </h1>
              <p className="text-sm text-[#8B949E] mt-1">
                Analyzing the correlation between @a1lon9&apos;s tweets and $PUMP price
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link 
                href="/chart"
                className="px-4 py-2 text-sm bg-[#21262D] text-[#8B949E] hover:bg-[#30363D] hover:text-[#C9D1D9] rounded-lg transition-colors"
              >
                View Chart
              </Link>
              <a
                href="https://twitter.com/a1lon9"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-[#21262D] hover:bg-[#30363D] rounded-lg transition-colors"
              >
                <img 
                  src="/avatars/a1lon9.png" 
                  alt="Alon" 
                  className="w-6 h-6 rounded-full"
                />
                <span className="text-[#C9D1D9]">@a1lon9</span>
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Stats Panel */}
      {stats && <StatsPanel stats={stats} />}

      {/* Data Table */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <DataTable events={tweetEvents} />
      </main>

      {/* Footer */}
      <footer className="border-t border-[#30363D] bg-[#161B22] py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-[#6E7681]">
          <p>
            Built with data from X API & GeckoTerminal. Not financial advice. 
            <a 
              href="https://pump.fun" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-[#58A6FF] hover:underline ml-1"
            >
              pump.fun
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

