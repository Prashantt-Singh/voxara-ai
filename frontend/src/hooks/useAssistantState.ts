import { useState, useCallback } from 'react';
import { ASSISTANT_STATES } from '../types/assistant';
import type { AssistantState, StateMetadata } from '../types/assistant';

export interface UseAssistantStateReturn {
  /** The current visual state of the assistant */
  state: AssistantState;
  /** Sets the assistant to a specific state */
  setState: (newState: AssistantState) => void;
  /** Current state metadata (label, description, accentColor) */
  metadata: StateMetadata;
  /** Reset back to idle */
  resetToIdle: () => void;
}

/**
 * Custom hook to manage the assistant's UI state.
 *
 * In Step 1, this acts as the state store for UI demonstration and visual verification.
 * In future steps, this will connect to audio streaming and agentic event listeners.
 */
export function useAssistantState(initialState: AssistantState = 'idle'): UseAssistantStateReturn {
  const [state, setState] = useState<AssistantState>(initialState);

  const resetToIdle = useCallback(() => {
    setState('idle');
  }, []);

  return {
    state,
    setState,
    metadata: ASSISTANT_STATES[state],
    resetToIdle,
  };
}
