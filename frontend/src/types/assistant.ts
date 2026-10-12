/**
 * Supported visual states for Voxara AI assistant.
 * In Step 1, these drive UI and animation feedback.
 */
export type AssistantState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'executing'
  | 'speaking'
  | 'error';

/**
 * Human-readable metadata and description for each assistant state.
 */
export interface StateMetadata {
  label: string;
  description: string;
  accentColor: string;
}

export const ASSISTANT_STATES: Record<AssistantState, StateMetadata> = {
  idle: {
    label: 'Ready',
    description: 'Voxara is on standby and ready to assist.',
    accentColor: '#F59E0B',
  },
  listening: {
    label: 'Listening...',
    description: 'Receiving voice or text input.',
    accentColor: '#EAB308',
  },
  thinking: {
    label: 'Thinking...',
    description: 'Processing intent and reasoning about the request.',
    accentColor: '#F97316',
  },
  executing: {
    label: 'Executing...',
    description: 'Running agent workflows and tool operations.',
    accentColor: '#FB923C',
  },
  speaking: {
    label: 'Speaking...',
    description: 'Synthesizing voice response and communicating back.',
    accentColor: '#FBBF24',
  },
  error: {
    label: 'Attention Needed',
    description: 'An error or unexpected interruption occurred.',
    accentColor: '#EF4444',
  },
};
