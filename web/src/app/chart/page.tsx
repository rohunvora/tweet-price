'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { loadTweetEvents } from '@/lib/dataLoader';
import { TweetEvent } from '@/lib/types';

const Chart = dynamic(() => import('@/components/Chart'), { 
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-screen bg-[#131722]">
      <div className="text-[#787B86]">Loading chart...</div>
    </div>
  ),
});

export default function ChartPage() {
  const [tweetEvents, setTweetEvents] = useState<TweetEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const eventsData = await loadTweetEvents();
        setTweetEvents(eventsData.events);
      } catch (error) {
        console.error('Failed to load data:', error);
      }
      setLoading(false);
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="h-screen bg-[#131722] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-[#2962FF] border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-[#787B86]">Loading chart data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-[#131722] flex flex-col">
      {/* Top toolbar - TradingView style */}
      <div className="h-10 bg-[#1E222D] border-b border-[#2A2E39] flex items-center px-2 gap-2">
        {/* Symbol info */}
        <div className="flex items-center gap-2 px-2 border-r border-[#2A2E39]">
          <span className="text-[#D1D4DC] font-medium">$PUMP/USD</span>
          <span className="text-[#787B86] text-xs">on Pump AMM</span>
        </div>
        
        {/* Navigation */}
        <div className="flex items-center gap-1 ml-auto">
          <Link 
            href="/chart"
            className="px-3 py-1 text-xs bg-[#2962FF] text-white rounded"
          >
            Chart
          </Link>
          <Link 
            href="/data"
            className="px-3 py-1 text-xs bg-[#2A2E39] text-[#787B86] hover:text-[#D1D4DC] rounded"
          >
            Data Table
          </Link>
        </div>
      </div>

      {/* Chart area */}
      <div className="flex-1 relative">
        <Chart tweetEvents={tweetEvents} />
      </div>

      {/* Bottom bar */}
      <div className="h-8 bg-[#1E222D] border-t border-[#2A2E39] flex items-center px-4 justify-between">
        <div className="flex items-center gap-4">
          <a
            href="https://twitter.com/a1lon9"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-[#787B86] hover:text-[#D1D4DC] text-xs"
          >
            <img src="/avatars/a1lon9.png" alt="Alon" className="w-5 h-5 rounded-full" />
            <span>@a1lon9 tweets shown</span>
          </a>
        </div>
        <div className="text-[#787B86] text-xs">
          {tweetEvents.length} tweets • Data from X API & GeckoTerminal
        </div>
      </div>
    </div>
  );
}

