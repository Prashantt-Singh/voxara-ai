/**
 * Voxara AI - Centralized Backend API Client
 *
 * Connects frontend interfaces to real FastAPI backend endpoints:
 * - Shared opportunity catalog & personalized match rankings
 * - Application tracking pipeline (Saved Opportunities)
 * - Persistent notifications and confirmation gates
 * - User hunt preferences
 * - LangGraph workflow telemetry and scheduler health
 *
 * Security:
 * - Injects cryptographic Supabase Bearer token on all protected requests.
 * - Never trusts client-supplied user IDs for identity authorization.
 * - Automatically handles 401/403 errors and network retries.
 */

import { supabase } from './supabaseClient';

export interface OpportunityItem {
  id: string;
  title: string;
  organization: string;
  type: string;
  source_url: string;
  application_url?: string | null;
  deadline?: string | null;
  description: string;
  location?: string | null;
  eligibility?: string | null;
  requirements: string[];
  match_score?: number;
  match_reason?: string | null;
  prize_or_salary?: string | null;
  verified_status: string;
  source_name: string;
  discovered_at?: string | null;
  // Personalized matching extra fields (when returned by /api/opportunities/matches)
  category?: string;
  is_remote?: boolean;
  relevance_tier?: string;
  match_reasons?: string[];
  match_explanation?: string;
  eligibility_status?: string;
}

export interface SavedOpportunityItem {
  id: string;
  user_id: string;
  opportunity_id: string;
  status: 'saved' | 'applied' | 'interviewing' | 'offered' | 'rejected' | 'archived';
  notes?: string | null;
  match_score: number;
  match_reason?: string | null;
  saved_at: string;
  updated_at: string;
  opportunity?: OpportunityItem | null;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  opportunity_id?: string | null;
  spoken_summary?: string | null;
  type: string;
  priority: string;
  is_read: boolean;
  requires_confirmation: boolean;
  confirmation_token?: string | null;
  created_at: string;
  delivered_at?: string | null;
}

export interface UserPreferencesItem {
  id?: string;
  roles: string[];
  opportunity_types: string[];
  domains: string[];
  min_match_score: number;
  auto_monitor_enabled: boolean;
  notifications_enabled: boolean;
  preferred_locations: string[];
  remote_only: boolean;
  skills: string[];
  education_level?: string | null;
  graduation_year?: number | null;
  eligibility_context?: Record<string, unknown>;
  updated_at?: string;
}

export interface MatchResponse {
  status: string;
  user_id: string;
  total_matched: number;
  opportunities: OpportunityItem[];
  criteria_applied: Record<string, unknown>;
}

export interface ExecutionEventItem {
  event_id?: string;
  execution_id: string;
  node_name: string;
  event_type: string;
  timestamp: string;
  status: string;
  duration?: number | null;
  duration_ms?: number | null;
  details?: Record<string, unknown> | null;
}

export interface ExecutionRecord {
  execution_id: string;
  workflow_type?: string;
  task?: string;
  status: string;
  events?: ExecutionEventItem[];
  created_at?: string;
  result?: Record<string, unknown>;
}

export interface SchedulerStatus {
  scheduler_enabled: boolean;
  enable_in_app_scheduler: boolean;
  is_running: boolean;
  interval_minutes: number;
  batch_size: number;
  deadline_alert_days: number;
  last_execution?: Record<string, unknown> | null;
}

// Configured Backend URL (with trailing slash stripped)
const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/+$/, '') ||
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') ||
  'http://localhost:8000';

/**
 * Retrieves the active Supabase JWT session access token.
 */
async function getAuthToken(): Promise<string | null> {
  if (!supabase) return null;
  try {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  } catch (err) {
    console.warn('Failed to retrieve active Supabase session token:', err);
    return null;
  }
}

/**
 * Universal authenticated fetch wrapper.
 */
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  requiresAuth: boolean = false
): Promise<{ data: T | null; error: string | null; status: number }> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  if (requiresAuth) {
    const token = await getAuthToken();
    if (!token) {
      return {
        data: null,
        error: 'Please sign in to access your personal data.',
        status: 401,
      };
    }
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = `${BACKEND_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  try {
    const response = await fetch(url, { ...options, headers });
    const status = response.status;

    if (status === 401) {
      return {
        data: null,
        error: 'Authentication required or session expired. Please sign in.',
        status,
      };
    }

    if (status === 403) {
      return {
        data: null,
        error: 'Access denied: You do not have permission to access this resource.',
        status,
      };
    }

    if (!response.ok) {
      let errorMsg = `Server error (${status})`;
      try {
        const errJson = await response.json();
        errorMsg = errJson.detail || errJson.message || errorMsg;
      } catch {
        // use default error message
      }
      return { data: null, error: String(errorMsg), status };
    }

    // 204 No Content
    if (status === 204) {
      return { data: null, error: null, status };
    }

    const data = (await response.json()) as T;
    return { data, error: null, status };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Network error or backend unreachable';
    return { data: null, error: message, status: 0 };
  }
}

export const voxaraService = {
  // ---------------------------------------------------------------------------
  // 1. Opportunities & Search
  // ---------------------------------------------------------------------------

  /**
   * Fetches opportunities from the shared catalog with optional category filter.
   */
  async getOpportunities(type: string = 'all', limit: number = 50): Promise<OpportunityItem[]> {
    const typeParam = type && type.toLowerCase() !== 'all' ? `opp_type=${encodeURIComponent(type.toLowerCase())}&` : '';
    const res = await apiFetch<OpportunityItem[]>(`/api/opportunities?${typeParam}limit=${limit}`);
    return res.data || [];
  },

  /**
   * Fetches personalized matched opportunities evaluated against the user's preferences.
   * Derives real match scores and explanations directly from the backend.
   */
  async getMatchedOpportunities(category?: string, minScore?: number): Promise<{
    opportunities: OpportunityItem[];
    totalMatched: number;
    error: string | null;
    status: number;
  }> {
    const params = new URLSearchParams();
    if (category && category !== 'all') params.append('category', category);
    if (minScore !== undefined) params.append('min_score', String(minScore));
    params.append('limit', '50');

    const res = await apiFetch<MatchResponse>(
      `/api/opportunities/matches?${params.toString()}`,
      { method: 'GET' },
      true
    );

    if (res.error) {
      return { opportunities: [], totalMatched: 0, error: res.error, status: res.status };
    }

    const items = (res.data?.opportunities || []).map((opp) => ({
      ...opp,
      match_score: opp.match_score ?? 0,
    }));

    return {
      opportunities: items,
      totalMatched: res.data?.total_matched ?? items.length,
      error: null,
      status: res.status,
    };
  },

  /**
   * Fetches opportunities with upcoming deadlines.
   */
  async getDeadlines(limit: number = 10): Promise<OpportunityItem[]> {
    const res = await apiFetch<OpportunityItem[]>(`/api/opportunities/deadlines?limit=${limit}`);
    return res.data || [];
  },

  /**
   * Triggers the LangGraph opportunity hunter workflow to discover fresh opportunities.
   */
  async huntOpportunities(query: string = 'all', type: string = 'all', limit: number = 15): Promise<OpportunityItem[]> {
    const res = await apiFetch<{ opportunities: OpportunityItem[] }>(
      '/api/opportunities/hunt',
      {
        method: 'POST',
        body: JSON.stringify({ query, opportunity_type: type, limit }),
      }
    );
    return res.data?.opportunities || [];
  },

  // ---------------------------------------------------------------------------
  // 2. Saved Opportunities & Application Pipeline
  // ---------------------------------------------------------------------------

  /**
   * Retrieves saved opportunities for the authenticated user.
   */
  async getSavedOpportunities(status?: string): Promise<{
    data: SavedOpportunityItem[];
    error: string | null;
    status: number;
  }> {
    const statusParam = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';
    const res = await apiFetch<SavedOpportunityItem[]>(
      `/api/opportunities/saved${statusParam}`,
      { method: 'GET' },
      true
    );
    return { data: res.data || [], error: res.error, status: res.status };
  },

  /**
   * Saves an opportunity into the user's personal pipeline.
   */
  async saveOpportunity(
    opportunityId: string,
    status: SavedOpportunityItem['status'] = 'saved',
    notes?: string,
    matchScore: number = 0.0
  ): Promise<{ data: SavedOpportunityItem | null; error: string | null; status: number }> {
    const res = await apiFetch<SavedOpportunityItem>(
      '/api/opportunities/saved',
      {
        method: 'POST',
        body: JSON.stringify({
          opportunity_id: opportunityId,
          status,
          notes: notes || null,
          match_score: matchScore,
        }),
      },
      true
    );
    return { data: res.data, error: res.error, status: res.status };
  },

  /**
   * Updates application status or personal notes.
   */
  async updateSavedOpportunity(
    savedId: string,
    updates: { status?: SavedOpportunityItem['status']; notes?: string }
  ): Promise<{ data: SavedOpportunityItem | null; error: string | null; status: number }> {
    const res = await apiFetch<SavedOpportunityItem>(
      `/api/opportunities/saved/${savedId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      },
      true
    );
    return { data: res.data, error: res.error, status: res.status };
  },

  /**
   * Removes an opportunity from the user's pipeline.
   */
  async deleteSavedOpportunity(savedId: string): Promise<boolean> {
    const res = await apiFetch<{ status: string }>(
      `/api/opportunities/saved/${savedId}`,
      { method: 'DELETE' },
      true
    );
    return res.status >= 200 && res.status < 300;
  },

  // ---------------------------------------------------------------------------
  // 3. User Preferences
  // ---------------------------------------------------------------------------

  /**
   * Retrieves preferences for the authenticated user.
   */
  async getPreferences(): Promise<{ data: UserPreferencesItem | null; error: string | null; status: number }> {
    const res = await apiFetch<UserPreferencesItem>('/api/preferences', { method: 'GET' }, true);
    return { data: res.data, error: res.error, status: res.status };
  },

  /**
   * Updates preferences for the authenticated user.
   */
  async updatePreferences(
    updates: Partial<UserPreferencesItem>
  ): Promise<{ data: UserPreferencesItem | null; error: string | null; status: number }> {
    const res = await apiFetch<UserPreferencesItem>(
      '/api/preferences',
      {
        method: 'PUT',
        body: JSON.stringify(updates),
      },
      true
    );
    return { data: res.data, error: res.error, status: res.status };
  },

  // ---------------------------------------------------------------------------
  // 4. Notifications
  // ---------------------------------------------------------------------------

  /**
   * Retrieves persistent notifications for the authenticated user.
   */
  async getNotifications(unreadOnly: boolean = false, limit: number = 30): Promise<{
    data: NotificationItem[];
    error: string | null;
    status: number;
  }> {
    const res = await apiFetch<NotificationItem[]>(
      `/api/notifications?unread_only=${unreadOnly}&limit=${limit}`,
      { method: 'GET' },
      true
    );
    return { data: res.data || [], error: res.error, status: res.status };
  },

  /**
   * Marks a specific notification as read.
   */
  async markNotificationRead(notificationId: string): Promise<boolean> {
    const res = await apiFetch<{ status: string; marked: boolean }>(
      `/api/notifications/${notificationId}/read`,
      { method: 'POST' },
      true
    );
    return res.data?.marked ?? (res.status >= 200 && res.status < 300);
  },

  /**
   * Marks all notifications as read for the authenticated user.
   */
  async markAllNotificationsRead(): Promise<number> {
    const res = await apiFetch<{ status: string; marked_count: number }>(
      '/api/notifications/read-all',
      { method: 'POST' },
      true
    );
    return res.data?.marked_count ?? 0;
  },

  /**
   * Confirms a consequential human-in-the-loop action.
   */
  async confirmNotification(notificationId: string, confirmationToken: string): Promise<boolean> {
    const res = await apiFetch<{ status: string }>(
      `/api/notifications/${notificationId}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify({ confirmation_token: confirmationToken }),
      },
      true
    );
    return res.status >= 200 && res.status < 300;
  },

  // ---------------------------------------------------------------------------
  // 5. Workflows, Scheduler & Telemetry
  // ---------------------------------------------------------------------------

  async getExecutions(limit: number = 10): Promise<ExecutionRecord[]> {
    const res = await apiFetch<{ count: number; executions: ExecutionRecord[] }>(
      `/api/workflows/executions?limit=${limit}`
    );
    return res.data?.executions || [];
  },

  async getSchedulerStatus(): Promise<SchedulerStatus | null> {
    const res = await apiFetch<SchedulerStatus>('/api/workflows/scheduler/status');
    return res.data;
  },
};
