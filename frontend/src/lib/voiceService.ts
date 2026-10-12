export interface VoiceTokenResponse {
  server_url: string;
  room_name: string;
  participant_identity: string;
  token: string;
}

export interface VoiceStatusResponse {
  status: 'ready' | 'configuration_required' | string;
  livekit_configured: boolean;
  livekit_server_url: string | null;
  default_room: string;
  details: string;
}

export interface VoiceServiceError {
  error: string;
  message: string;
  reason?: string;
  statusCode?: number;
}

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/+$/, '') ||
  'http://localhost:8000';

/**
 * Service client communicating with Voxara backend voice endpoints.
 */
export const voiceService = {
  /**
   * Check backend readiness and LiveKit configuration status.
   */
  async checkStatus(): Promise<VoiceStatusResponse> {
    try {
      const response = await fetch(`${BACKEND_URL}/api/voice/status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Voice status check failed with HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Unable to reach backend voice service at ${BACKEND_URL}: ${msg}`);
    }
  },

  /**
   * Request a short-lived signed JWT LiveKit connection token.
   * Keeps all API secrets securely on the backend.
   */
  async requestToken(options?: {
    identity?: string;
    name?: string;
    roomName?: string;
  }): Promise<VoiceTokenResponse> {
    let response: Response;
    try {
      response = await fetch(`${BACKEND_URL}/api/voice/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          identity: options?.identity,
          name: options?.name,
          room_name: options?.roomName,
        }),
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(
        `Failed to connect to backend server at ${BACKEND_URL}. Ensure the backend is running with "uvicorn app.main:app". Details: ${msg}`
      );
    }

    if (!response.ok) {
      let errorData: VoiceServiceError;
      try {
        const json = await response.json();
        errorData = (json.detail as VoiceServiceError) || {
          error: 'REQUEST_FAILED',
          message: json.detail || `Server returned error HTTP ${response.status}`,
        };
      } catch {
        errorData = {
          error: 'UNKNOWN_SERVER_ERROR',
          message: `Server returned HTTP ${response.status}`,
        };
      }
      errorData.statusCode = response.status;

      const formattedMsg =
        errorData.message +
        (errorData.reason ? ` (${errorData.reason})` : '');
      const err = new Error(formattedMsg);
      (err as unknown as { serviceError: VoiceServiceError }).serviceError = errorData;
      throw err;
    }

    return await response.json();
  },
};
