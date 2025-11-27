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
 * Tries PNG first (real logo), then SVG (generated fallback)
 */
export function getLogoUrl(ticker: string): string {
  return `/company-logos/${ticker.toLowerCase()}.png`;
}

/**
 * Get fallback SVG logo URL
 */
export function getSvgLogoUrl(ticker: string): string {
  return `/company-logos/${ticker.toLowerCase()}.svg`;
}

/**
 * CompanyLogo component with automatic fallback
 * Tries PNG first, then SVG, then ticker badge
 */
export function CompanyLogo({ ticker, domain, size = 48, className = '' }: CompanyLogoProps) {
  const [pngError, setPngError] = useState(false);
  const [svgError, setSvgError] = useState(false);

  const pngUrl = getLogoUrl(ticker);
  const svgUrl = getSvgLogoUrl(ticker);

  // Try SVG if PNG failed
  if (pngError && !svgError) {
    return (
      <Image
        src={svgUrl}
        alt={`${ticker} logo`}
        width={size}
        height={size}
        className={`rounded-lg ${className}`}
        onError={() => setSvgError(true)}
      />
    );
  }

  // Fallback ticker badge if both PNG and SVG fail
  if (pngError && svgError) {
    return (
      <div
        className={`flex items-center justify-center bg-gradient-to-br from-blue-500 to-blue-600 text-white font-bold rounded-lg ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
      >
        {ticker}
      </div>
    );
  }

  // Try PNG first (real logo)
  return (
    <Image
      src={pngUrl}
      alt={`${ticker} logo`}
      width={size}
      height={size}
      className={`rounded-lg ${className}`}
      onError={() => setPngError(true)}
    />
  );
}
