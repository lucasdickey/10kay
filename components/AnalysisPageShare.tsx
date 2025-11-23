'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ShareModal from './ShareModal';

interface AnalysisPageShareProps {
  slug: string;
  title: string;
}

export default function AnalysisPageShare({ slug, title }: AnalysisPageShareProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [mountPoint, setMountPoint] = useState<Element | null>(null);

  useEffect(() => {
    const mount = document.getElementById('share-button-mount');
    if (mount) setMountPoint(mount);
  }, []);

  const shareButton = (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="analysis-share-icon"
        title="Share this analysis"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          marginLeft: '8px',
          color: '#6b7280',
          verticalAlign: 'middle',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
        }}
      >
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          />
        </svg>
      </button>
      <ShareModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        url={`/${slug}`}
        title={title}
      />
    </>
  );

  if (!mountPoint) return null;

  return createPortal(shareButton, mountPoint);
}
