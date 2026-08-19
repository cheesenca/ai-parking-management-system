'use client';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Renders children directly under document.body (not wherever the component
 * happens to be nested) and locks background scroll while mounted. Avoids
 * any possible ancestor CSS quirk affecting position:fixed centering, and
 * guarantees the modal is visible in the current viewport immediately.
 */
export default function ModalPortal({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prevOverflow; };
  }, []);

  if (!mounted) return null;
  return createPortal(children, document.body);
}
