export interface OpportunityItem {
  id: string;
  title: string;
  organization: string;
  type: string;
  source_url: string;
  deadline?: string | null;
  description: string;
  requirements: string[];
  match_score?: number;
  match_reason?: string | null;
  prize_or_salary?: string | null;
  verified_status: string;
  source_name: string;
  discovered_at?: string | null;
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
  user_id?: string;
  opportunity_id?: string | null;
  title: string;
  message: string;
  spoken_summary?: string | null;
  type: string;
  priority: string;
  is_read: boolean;
  requires_confirmation: boolean;
  confirmation_token?: string | null;
  created_at: string;
}

export interface ExecutionEventItem {
  event_id: string;
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
}

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/+$/, '') ||
  'http://localhost:8000';

export const voxaraService = {
  // Shared Opportunity Catalog
  async getOpportunities(type?: string): Promise<OpportunityItem[]> {
    try {
      const queryParam = type && type !== 'all' ? `?type=${encodeURIComponent(type)}&limit=20` : '?limit=20';
      const res = await fetch(`${BACKEND_URL}/api/opportunities${queryParam}`);
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async getDeadlines(limit: number = 10): Promise<OpportunityItem[]> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/opportunities/deadlines?limit=${limit}`);
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async huntOpportunities(query: string = 'all', type: string = 'all'): Promise<OpportunityItem[]> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/opportunities/hunt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, opportunity_type: type, limit: 10 }),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return data.opportunities || [];
    } catch {
      return [];
    }
  },

  // User Pipeline & Application Tracking
  async getSavedOpportunities(userId: string = 'default_user', status?: string): Promise<SavedOpportunityItem[]> {
    try {
      const statusParam = status ? `&status=${encodeURIComponent(status)}` : '';
      const res = await fetch(`${BACKEND_URL}/api/opportunities/saved?user_id=${encodeURIComponent(userId)}${statusParam}`);
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async saveOpportunity(
    opportunityId: string,
    status: 'saved' | 'applied' | 'interviewing' | 'offered' | 'rejected' | 'archived' = 'saved',
    notes?: string,
    matchScore: number = 0.0,
    userId: string = 'default_user',
  ): Promise<SavedOpportunityItem | null> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/opportunities/saved?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          opportunity_id: opportunityId,
          status,
          notes,
          match_score: matchScore,
        }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async updateSavedOpportunity(
    savedId: string,
    updates: { status?: string; notes?: string },
    userId: string = 'default_user',
  ): Promise<SavedOpportunityItem | null> {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/opportunities/saved/${savedId}?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        },
      );
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async deleteSavedOpportunity(savedId: string, userId: string = 'default_user'): Promise<boolean> {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/opportunities/saved/${savedId}?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'DELETE',
        },
      );
      return res.ok;
    } catch {
      return false;
    }
  },

  // Notifications & Human Confirmation Gate
  async getNotifications(userId: string = 'default_user'): Promise<NotificationItem[]> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/notifications?user_id=${encodeURIComponent(userId)}&limit=15`);
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async confirmNotification(id: string, token: string, userId: string = 'default_user'): Promise<boolean> {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/notifications/${id}/confirm?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirmation_token: token }),
        },
      );
      return res.ok;
    } catch {
      return false;
    }
  },

  async markNotificationRead(id: string, userId: string = 'default_user'): Promise<boolean> {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/notifications/${id}/read?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'POST',
        },
      );
      return res.ok;
    } catch {
      return false;
    }
  },

  // Telemetry
  async getExecutions(): Promise<ExecutionRecord[]> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/workflows/executions?limit=10`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.executions || [];
    } catch {
      return [];
    }
  },
};
