import type {
  AssistantState,
  VoiceSessionStatus,
  VoiceSessionError,
  UseVoiceSessionReturn,
} from '../types/assistant';

export type {
  AssistantState,
  VoiceSessionStatus,
  VoiceSessionError,
  UseVoiceSessionReturn,
};

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Room,
  RoomEvent,
  ConnectionState,
  Track,
} from 'livekit-client';
import { voiceService } from '../lib/voiceService';

/**
 * Custom hook to manage LiveKit real-time voice sessions.
 *
 * Implements:
 * - Direct WebRTC connection via LiveKit Client
 * - Explicit connection lifecycle: disconnected, connecting, connected, error
 * - Real speaking/listening detection:
 *     - 'listening' when user local microphone track is unmuted and speaking
 *     - 'speaking' when remote assistant participant is actively speaking
 *     - 'idle' when connected and quiet
 * - Clean teardown and audio track release on disconnect
 * - Protection against duplicate connection attempts
 * - Clear error surfacing for permission denial and configuration issues
 */
export function useVoiceSession(): UseVoiceSessionReturn {
  const [status, setStatus] = useState<VoiceSessionStatus>('disconnected');
  const [assistantState, setAssistantState] = useState<AssistantState>('idle');
  const [error, setError] = useState<VoiceSessionError | null>(null);
  const [isMicrophoneEnabled, setIsMicrophoneEnabled] = useState<boolean>(false);
  const [roomName, setRoomName] = useState<string | null>(null);
  const [participantCount, setParticipantCount] = useState<number>(0);

  const roomRef = useRef<Room | null>(null);
  const isConnectingRef = useRef<boolean>(false);

  // Compute visual assistant state from real WebRTC room activity
  const updateAssistantVoiceState = useCallback((room: Room) => {
    if (room.state !== ConnectionState.Connected) {
      if (room.state === ConnectionState.Connecting || room.state === ConnectionState.Reconnecting) {
        setAssistantState('thinking');
      } else {
        setAssistantState('idle');
      }
      return;
    }

    // Check if remote agent/participant is speaking
    let remoteSpeaking = false;
    room.remoteParticipants.forEach((p) => {
      if (p.isSpeaking) {
        remoteSpeaking = true;
      }
    });

    if (remoteSpeaking) {
      setAssistantState('speaking');
      return;
    }

    // Check if local user is actively speaking into mic
    if (room.localParticipant?.isSpeaking) {
      setAssistantState('listening');
      return;
    }

    // Connected standby
    setAssistantState('idle');
  }, []);

  const cleanupRoom = useCallback(async () => {
    if (roomRef.current) {
      const room = roomRef.current;
      roomRef.current = null;
      try {
        // Disconnect disables microphone tracks automatically
        await room.disconnect();
      } catch (err) {
        console.warn('Error during room disconnect cleanup:', err);
      }
    }
    setIsMicrophoneEnabled(false);
    setParticipantCount(0);
    setRoomName(null);
    setStatus('disconnected');
  }, []);

  const disconnect = useCallback(async () => {
    isConnectingRef.current = false;
    await cleanupRoom();
    setAssistantState('idle');
  }, [cleanupRoom]);

  const connect = useCallback(async () => {
    // Prevent duplicate concurrent connection attempts
    if (isConnectingRef.current || roomRef.current?.state === ConnectionState.Connected) {
      console.warn('Connection attempt ignored: already connecting or connected.');
      return;
    }

    isConnectingRef.current = true;
    setStatus('connecting');
    setError(null);
    setAssistantState('thinking'); // Indicates connection setup and token negotiation

    try {
      // 1. Fetch short-lived token from backend
      const tokenData = await voiceService.requestToken();

      // 2. Instantiate LiveKit room client
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      roomRef.current = room;

      // 3. Set up real WebRTC room event listeners
      room
        .on(RoomEvent.Connected, () => {
          setStatus('connected');
          setRoomName(room.name);
          setParticipantCount(room.remoteParticipants.size + 1);
          updateAssistantVoiceState(room);
        })
        .on(RoomEvent.Reconnecting, () => {
          setStatus('connecting');
          setAssistantState('thinking');
        })
        .on(RoomEvent.Reconnected, () => {
          setStatus('connected');
          updateAssistantVoiceState(room);
        })
        .on(RoomEvent.Disconnected, () => {
          setStatus('disconnected');
          setAssistantState('idle');
          setIsMicrophoneEnabled(false);
        })
        .on(RoomEvent.ActiveSpeakersChanged, () => {
          updateAssistantVoiceState(room);
        })
        .on(RoomEvent.ParticipantConnected, () => {
          setParticipantCount(room.remoteParticipants.size + 1);
        })
        .on(RoomEvent.ParticipantDisconnected, () => {
          setParticipantCount(room.remoteParticipants.size + 1);
          updateAssistantVoiceState(room);
        })
        .on(RoomEvent.TrackSubscribed, (track: Track) => {
          if (track.kind === Track.Kind.Audio) {
            // Attach audio element to play remote assistant voice
            const el = track.attach();
            el.id = `livekit-audio-${track.sid}`;
            document.body.appendChild(el);
          }
        })
        .on(RoomEvent.TrackUnsubscribed, (track: Track) => {
          if (track.kind === Track.Kind.Audio) {
            track.detach().forEach((el) => el.remove());
          }
        });

      // 4. Connect WebRTC peer to LiveKit server
      await room.connect(tokenData.server_url, tokenData.token);

      // 5. Request microphone permission and enable audio publishing
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
        setIsMicrophoneEnabled(true);
      } catch (micErr: unknown) {
        console.error('Microphone access denied:', micErr);
        const micMessage =
          micErr instanceof Error
            ? micErr.message
            : 'Microphone permission was denied by the browser.';
        setError({
          type: 'permission',
          message: micMessage,
          details: 'Please allow microphone access in your browser settings to interact via voice.',
        });
        setAssistantState('error');
        // Do not abort connected room, but mark error and mic disabled
        setIsMicrophoneEnabled(false);
        return;
      }

      setStatus('connected');
      updateAssistantVoiceState(room);
    } catch (err: unknown) {
      console.error('LiveKit connection error:', err);
      const errMsg = err instanceof Error ? err.message : String(err);

      // Determine error category
      let errType: VoiceSessionError['type'] = 'connection';
      if (errMsg.toLowerCase().includes('permission') || errMsg.toLowerCase().includes('notallowederror')) {
        errType = 'permission';
      } else if (errMsg.toLowerCase().includes('livekit_not_configured') || errMsg.toLowerCase().includes('503')) {
        errType = 'configuration';
      }

      setError({
        type: errType,
        message: errMsg,
        details:
          errType === 'configuration'
            ? 'Backend LiveKit credentials (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET) must be set in backend/.env'
            : undefined,
      });

      setStatus('error');
      setAssistantState('error');
      await cleanupRoom();
    } finally {
      isConnectingRef.current = false;
    }
  }, [cleanupRoom, updateAssistantVoiceState]);

  const toggleSession = useCallback(async () => {
    if (status === 'connected' || status === 'connecting') {
      await disconnect();
    } else {
      await connect();
    }
  }, [status, connect, disconnect]);

  const setMicrophoneEnabled = useCallback(async (enabled: boolean) => {
    if (!roomRef.current || roomRef.current.state !== ConnectionState.Connected) {
      return;
    }
    try {
      await roomRef.current.localParticipant.setMicrophoneEnabled(enabled);
      setIsMicrophoneEnabled(enabled);
      if (roomRef.current) {
        updateAssistantVoiceState(roomRef.current);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError({
        type: 'permission',
        message: `Failed to toggle microphone: ${msg}`,
      });
    }
  }, [updateAssistantVoiceState]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
      }
    };
  }, []);

  return {
    status,
    assistantState,
    error,
    isMicrophoneEnabled,
    roomName,
    participantCount,
    connect,
    disconnect,
    toggleSession,
    setMicrophoneEnabled,
  };
}
