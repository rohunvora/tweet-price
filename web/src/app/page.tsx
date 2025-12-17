'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { loadTweetEvents, loadStats } from '@/lib/dataLoader';
import { TweetEvent, Stats } from '@/lib/types';
import StatsPanel from '@/components/StatsPanel';
import DataTable from '@/components/DataTable';

// Dynamic import for Chart to avoid SSR issues with canvas
const Chart = dynamic(() => import('@/components/Chart'), { 
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-[#0D1117]">
      <div className="text-[#8B949E]">Loading chart...</div>
    </div>
  ),
});

type Tab = 'chart' | 'table';

export default function Home() {
  const [tweetEvents, setTweetEvents] = useState<TweetEvent[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('chart');

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
                Does Alon Tweet = $PUMP Pump?
              </h1>
              <p className="text-sm text-[#8B949E] mt-1">
                Analyzing the correlation between @a1lon9&apos;s tweets and $PUMP price
              </p>
            </div>
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
      </header>

      {/* Stats Panel */}
      {stats && <StatsPanel stats={stats} />}

      {/* Tab Navigation */}
      <div className="border-b border-[#30363D] bg-[#161B22]">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-1">
            <button
              onClick={() => setActiveTab('chart')}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'chart'
                  ? 'border-[#58A6FF] text-[#C9D1D9]'
                  : 'border-transparent text-[#8B949E] hover:text-[#C9D1D9]'
              }`}
            >
              Chart View
            </button>
            <button
              onClick={() => setActiveTab('table')}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'table'
                  ? 'border-[#58A6FF] text-[#C9D1D9]'
                  : 'border-transparent text-[#8B949E] hover:text-[#C9D1D9]'
              }`}
            >
              Data Table
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {activeTab === 'chart' ? (
          <div className="flex-1 min-h-[500px]">
            <Chart tweetEvents={tweetEvents} />
          </div>
        ) : (
          <div className="flex-1 max-w-7xl mx-auto w-full">
            <DataTable events={tweetEvents} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#30363D] bg-[#161B22] py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-[#6E7681]">
          <p>
            Built with data. Not financial advice. 
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
