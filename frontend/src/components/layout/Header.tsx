import React from 'react';
import { ASSISTANT_STATES } from '../../types/assistant';
import type { AssistantState } from '../../types/assistant';

interface HeaderProps {
  currentState: AssistantState;
}

/**
 * Minimalist top navigation bar with brand badge and live state pill.
 */
export const Header: React.FC<HeaderProps> = ({ currentState }) => {
  const metadata = ASSISTANT_STATES[currentState];

  return (
    <header className="w-full py-4 sm:py-6" role="banner">
      <div className="flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-400" />
          <span className="font-semibold text-neutral-900 tracking-tight text-base sm:text-lg">
            Voxara<span className="text-amber-500 font-medium">.ai</span>
          </span>
        </div>

        {/* Small unobtrusive status label */}
        <div
          className="flex items-center gap-2 px-3 py-1 bg-white/80 border border-neutral-200/80 rounded-full shadow-xs text-xs text-neutral-600"
          aria-live="polite"
        >
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: metadata.accentColor }}
          />
          <span className="font-medium text-neutral-700">{metadata.label}</span>
        </div>
      </div>
    </header>
  );
};
