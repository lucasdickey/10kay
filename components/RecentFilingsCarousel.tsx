'use client';

import { useState, useRef, useEffect } from 'react';
import { EnhancedFilingCard } from './EnhancedFilingCard';

interface Analysis {
  id: string;
  slug: string | null;
  company_ticker: string;
  company_name: string;
  filing_type: string;
  filing_date: Date;
  key_takeaways: any;
}

interface RecentFilingsCarouselProps {
  filings: Analysis[];
}

export function RecentFilingsCarousel({ filings }: RecentFilingsCarouselProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const updateScrollButtons = () => {
    if (!scrollContainerRef.current) return;

    const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
    setCanScrollLeft(scrollLeft > 0);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
  };

  useEffect(() => {
    updateScrollButtons();
    window.addEventListener('resize', updateScrollButtons);
    return () => window.removeEventListener('resize', updateScrollButtons);
  }, []);

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    const cardWidth = container.querySelector('.filing-card')?.clientWidth || 350;
    const scrollAmount = cardWidth + 24; // card width + gap

    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  };

  if (filings.length === 0) {
    return null;
  }

  return (
    <div className="w-full bg-gray-50 border-y py-8">
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Recent Filings</h2>
            <p className="text-sm text-gray-600 mt-1">Latest 10-Q and 10-K analyses from the past 2 weeks</p>
          </div>

          {/* Desktop scroll buttons */}
          <div className="hidden md:flex items-center gap-2">
            <button
              onClick={() => scroll('left')}
              disabled={!canScrollLeft}
              className={`p-2 rounded-full border ${
                canScrollLeft
                  ? 'bg-white border-gray-300 hover:bg-gray-50 text-gray-700'
                  : 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed'
              } transition-colors`}
              aria-label="Scroll left"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={() => scroll('right')}
              disabled={!canScrollRight}
              className={`p-2 rounded-full border ${
                canScrollRight
                  ? 'bg-white border-gray-300 hover:bg-gray-50 text-gray-700'
                  : 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed'
              } transition-colors`}
              aria-label="Scroll right"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Carousel */}
        <div
          ref={scrollContainerRef}
          onScroll={updateScrollButtons}
          className="flex gap-6 overflow-x-auto scrollbar-hide snap-x snap-mandatory pb-4"
          style={{
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
          }}
        >
          {filings.map((filing) => (
            <div
              key={filing.id}
              className="filing-card flex-none w-full md:w-[calc(50%-12px)] lg:w-[calc(33.333%-16px)] snap-start"
            >
              <EnhancedFilingCard
                ticker={filing.company_ticker}
                companyName={filing.company_name}
                filingType={filing.filing_type}
                sentiment={filing.key_takeaways?.sentiment || 0}
                metrics={filing.key_takeaways?.metrics || {}}
                slug={filing.slug || ''}
                filingDate={filing.filing_date}
              />
            </div>
          ))}
        </div>

        {/* Mobile scroll indicator */}
        <div className="md:hidden flex justify-center gap-2 mt-4">
          <div className="text-xs text-gray-500 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16l-4-4m0 0l4-4m-4 4h18" />
            </svg>
            Swipe to see more
          </div>
        </div>
      </div>

      <style jsx>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </div>
  );
}
