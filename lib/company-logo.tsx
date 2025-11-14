/**
 * Company Logo Component
 *
 * Displays company logos using local SVG files
 */
'use client';

import Image from 'next/image';
import { useState } from 'react';

interface CompanyLogoProps {
  ticker: string;
  domain?: string | null;
  size?: number;
  className?: string;
}

/**
 * Get local logo URL for a company ticker
 * Uses locally fetched PNG logos (favicons)
 */
export function getLogoUrl(ticker: string): string {
  return `/company-logos/${ticker.toLowerCase()}.png`;
}

/**
 * CompanyLogo component with automatic fallback
 */
export function CompanyLogo({ ticker, domain, size = 48, className = '' }: CompanyLogoProps) {
  const [imageError, setImageError] = useState(false);
  const logoUrl = getLogoUrl(ticker);

  // Fallback ticker badge (should rarely be needed with local logos)
  if (imageError) {
    return (
      <div
        className={`flex items-center justify-center bg-gradient-to-br from-blue-500 to-blue-600 text-white font-bold rounded-lg ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
      >
        {ticker}
      </div>
    );
  }

  return (
    <Image
      src={logoUrl}
      alt={`${ticker} logo`}
      width={size}
      height={size}
      className={`rounded-lg ${className}`}
      onError={() => setImageError(true)}
    />
  );
}
