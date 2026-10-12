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
 * LiveKit voice session connection lifecycle status.
 */
export type VoiceSessionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error';

/**
 * Standard error shape for voice session errors.
 */
export interface VoiceSessionError {
  type: 'permission' | 'connection' | 'configuration' | 'unknown';
  message: string;
  details?: string;
}

/**
 * Return signature of useVoiceSession hook.
 */
export interface UseVoiceSessionReturn {
  status: VoiceSessionStatus;
  assistantState: AssistantState;
  error: VoiceSessionError | null;
  isMicrophoneEnabled: boolean;
  roomName: string | null;
  participantCount: number;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  toggleSession: () => Promise<void>;
  setMicrophoneEnabled: (enabled: boolean) => Promise<void>;
}

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
