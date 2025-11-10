/**
 * Company Logo Component
 *
 * Displays company logos using Clearbit Logo API with fallback to ticker badge
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
 * Get Clearbit logo URL for a company domain
 * Clearbit provides free high-quality company logos
 */
export function getLogoUrl(domain: string | null | undefined, size: number = 128): string | null {
  if (!domain) return null;
  return `https://logo.clearbit.com/${domain}?size=${size}`;
}

/**
 * CompanyLogo component with automatic fallback
 */
export function CompanyLogo({ ticker, domain, size = 48, className = '' }: CompanyLogoProps) {
  const [imageError, setImageError] = useState(false);
  const logoUrl = getLogoUrl(domain, size);

  // If no domain or image failed to load, show ticker badge
  if (!logoUrl || imageError) {
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
      unoptimized // Clearbit returns optimized images already
    />
  );
}
