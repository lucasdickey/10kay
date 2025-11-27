'use client';

/**
 * InfoTooltip Component
 *
 * Reusable, accessible tooltip for providing educational context about features
 * Works with hover states without interfering with parent element interactions
 * Fully keyboard accessible and ARIA labeled
 */

import { useState, useRef, useEffect } from 'react';

interface InfoTooltipProps {
  /** Label for the metric (used in ARIA labels) */
  label?: string;
  /** Tooltip text to display */
  info: string;
  /** Position of tooltip relative to trigger element */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** Custom styling for icon (only used when children not provided) */
  iconClassName?: string;
  /** Optional children to wrap as tooltip trigger instead of showing info icon */
  children?: React.ReactNode;
}

export function InfoTooltip({
  label,
  info,
  position = 'top',
  iconClassName = 'w-4 h-4',
  children,
}: InfoTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipId = `tooltip-${label?.replace(/\s+/g, '-').toLowerCase() || 'info'}`;

  // Close tooltip on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };

    if (isOpen || isFocused) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, isFocused]);

  const isVisible = isOpen || isFocused;

  const positionClasses = {
    top: 'bottom-full mb-3',
    bottom: 'top-full mt-3',
    left: 'right-full mr-3',
    right: 'left-full ml-3',
  };

  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 -translate-y-1',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 translate-y-1',
    left: 'left-full top-1/2 -translate-y-1/2 translate-x-1',
    right: 'right-full top-1/2 -translate-y-1/2 -translate-x-1',
  };

  const tooltipContent = (
    <>
      {info}
      {/* Arrow pointer */}
      <div
        className={`
          absolute w-2 h-2
          bg-gray-900
          transform rotate-45
          ${arrowClasses[position]}
        `}
        aria-hidden="true"
      />
    </>
  );

  const eventHandlers = {
    onClick: (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsOpen(!isOpen);
    },
    onMouseEnter: () => setIsOpen(true),
    onMouseLeave: () => !isFocused && setIsOpen(false),
    onFocus: () => setIsFocused(true),
    onBlur: () => setIsFocused(false),
  };

  if (children) {
    // Render children as tooltip trigger
    return (
      <div className="relative inline-flex">
        <div
          ref={triggerRef as any}
          tabIndex={0}
          className="relative inline-flex"
          aria-label={`Information about ${label || 'this item'}`}
          aria-describedby={isVisible ? tooltipId : undefined}
          {...eventHandlers}
        >
          {children}
        </div>

        {isVisible && (
          <div
            id={tooltipId}
            role="tooltip"
            className={`
              absolute z-[9999]
              px-3 py-2
              text-xs text-white
              bg-gray-900 rounded-lg
              shadow-lg
              max-w-4xl
              whitespace-normal
              pointer-events-none
              animate-in fade-in duration-200
              ${positionClasses[position]}
            `}
          >
            {tooltipContent}
          </div>
        )}
      </div>
    );
  }

  // Original icon-based rendering (backward compatible)
  return (
    <div className="relative inline-flex items-center">
      <button
        ref={triggerRef as any}
        type="button"
        className={`
          inline-flex items-center justify-center
          text-gray-400 hover:text-gray-600
          focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500
          rounded-full transition-colors
          ml-1.5
        `}
        aria-label={`Information about ${label || 'this metric'}`}
        aria-describedby={isVisible ? tooltipId : undefined}
        {...eventHandlers}
      >
        <svg
          className={`${iconClassName} flex-shrink-0`}
          fill="currentColor"
          viewBox="0 0 20 20"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isVisible && (
        <div
          id={tooltipId}
          role="tooltip"
          className={`
            absolute z-[9999]
            px-3 py-2
            text-xs text-white
            bg-gray-900 rounded-lg
            shadow-lg
            max-w-4xl
            whitespace-normal
            pointer-events-none
            animate-in fade-in duration-200
            ${positionClasses[position]}
          `}
        >
          {tooltipContent}
        </div>
      )}
    </div>
  );
}
