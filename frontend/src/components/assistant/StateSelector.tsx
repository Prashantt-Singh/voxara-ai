import React from 'react';
import type { AssistantState } from '../../types/assistant';

interface StateSelectorProps {
  currentState: AssistantState;
  onStateChange: (state: AssistantState) => void;
}

const STATES: AssistantState[] = [
  'idle',
  'listening',
  'thinking',
  'executing',
  'speaking',
  'error',
];

/**
 * Compact preview control for toggling visual states in Step 1.
 * Designed to be minimalist and easily removable when real backend telemetry is connected.
 */
export const StateSelector: React.FC<StateSelectorProps> = ({
  currentState,
  onStateChange,
}) => {
  return (
    <nav
      aria-label="Development visual state controls"
      className="inline-flex items-center gap-1 p-1 bg-white/70 backdrop-blur-md rounded-full border border-neutral-200 shadow-sm text-xs"
    >
      <span className="px-2 py-0.5 text-[11px] font-medium text-neutral-400 select-none uppercase tracking-wider">
        Preview State:
      </span>
      <div className="flex flex-wrap gap-1">
        {STATES.map((s) => {
          const isActive = currentState === s;
          return (
            <button
              key={s}
              onClick={() => onStateChange(s)}
              aria-pressed={isActive}
              className={`px-2.5 py-1 rounded-full text-xs font-medium capitalize transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-500 ${
                isActive
                  ? 'bg-neutral-900 text-white shadow-xs'
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
              }`}
            >
              {s}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
