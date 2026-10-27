import { describe, it, expect, vi, beforeEach } from 'vitest';
import { voxaraService } from '../lib/voxaraService';
import { supabase } from '../lib/supabaseClient';

describe('Voxara Backend API Client Integration', () => {
  const MOCK_TOKEN = 'mock-supabase-jwt-token-xyz';

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();

    // Mock active session with Bearer access token
    if (supabase) {
      vi.spyOn(supabase.auth, 'getSession').mockResolvedValue({
        data: {
          session: {
            access_token: MOCK_TOKEN,
            token_type: 'bearer',
            expires_in: 3600,
            refresh_token: 'refresh-xyz',
            user: { id: 'user-alice', email: 'alice@voxara.ai', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '' },
          },
        },
        error: null,
      });
    }
  });

  describe('1. Shared Opportunity Catalog & Search', () => {
    it('fetches opportunities with type and limit parameters', async () => {
      const mockOpps = [
        {
          id: 'opp_1',
          title: 'AI Engineering Intern',
          organization: 'Google',
          type: 'internship',
          source_url: 'https://careers.google.com',
          verified_status: 'verified',
          source_name: 'SimplifyJobs',
          requirements: ['Python', 'PyTorch'],
          description: 'Build LLM systems.',
        },
      ];

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockOpps,
      });

      const results = await voxaraService.getOpportunities('internship', 20);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/opportunities?opp_type=internship&limit=20'),
        expect.any(Object)
      );
      expect(results).toHaveLength(1);
      expect(results[0].title).toBe('AI Engineering Intern');
    });

    it('fetches personalized opportunity matches with Bearer token', async () => {
      const mockMatchResponse = {
        status: 'success',
        user_id: 'user-alice',
        total_matched: 1,
        opportunities: [
          {
            id: 'opp_2',
            title: 'Full Stack Fellow',
            organization: 'MLH',
            category: 'fellowship',
            source_url: 'https://fellowship.mlh.io',
            source_name: 'Curated',
            match_score: 0.88,
            relevance_tier: 'High Match',
            match_explanation: 'Matches your preferences for Full Stack and Fellowship',
            requirements: ['React', 'TypeScript'],
            verified_status: 'verified',
            description: 'Open source fellowship',
          },
        ],
        criteria_applied: {},
      };

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockMatchResponse,
      });

      const { opportunities, totalMatched, error } = await voxaraService.getMatchedOpportunities('fellowship');

      expect(error).toBeNull();
      expect(totalMatched).toBe(1);
      expect(opportunities[0].match_score).toBe(0.88);
      expect(opportunities[0].relevance_tier).toBe('High Match');

      // Verify Authorization header had Bearer token
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/opportunities/matches'),
        expect.objectContaining({
          headers: expect.any(Headers),
        })
      );
      const callHeaders = (globalThis.fetch as any).mock.calls[0][1].headers;
      expect(callHeaders.get('Authorization')).toBe(`Bearer ${MOCK_TOKEN}`);
    });
  });

  describe('2. User Saved Opportunities & Application Tracking', () => {
    it('retrieves saved opportunities using authenticated Bearer token without client user_id query', async () => {
      const mockSaved = [
        {
          id: 'saved_1',
          user_id: 'user-alice',
          opportunity_id: 'opp_1',
          status: 'applied',
          notes: 'Submitted resume on portal',
          match_score: 0.85,
          saved_at: '2026-10-27T00:00:00Z',
          updated_at: '2026-10-27T00:00:00Z',
        },
      ];

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSaved,
      });

      const { data, error } = await voxaraService.getSavedOpportunities();

      expect(error).toBeNull();
      expect(data).toHaveLength(1);
      expect(data[0].status).toBe('applied');

      const callUrl = (globalThis.fetch as any).mock.calls[0][0];
      expect(callUrl).toContain('/api/opportunities/saved');
      expect(callUrl).not.toContain('user_id=default_user');

      const callHeaders = (globalThis.fetch as any).mock.calls[0][1].headers;
      expect(callHeaders.get('Authorization')).toBe(`Bearer ${MOCK_TOKEN}`);
    });

    it('saves an opportunity to pipeline via POST /api/opportunities/saved', async () => {
      const mockSavedItem = {
        id: 'saved_2',
        user_id: 'user-alice',
        opportunity_id: 'opp_99',
        status: 'saved',
        notes: null,
        match_score: 0.9,
        saved_at: '2026-10-27T00:00:00Z',
        updated_at: '2026-10-27T00:00:00Z',
      };

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSavedItem,
      });

      const { data, error } = await voxaraService.saveOpportunity('opp_99', 'saved', '', 0.9);

      expect(error).toBeNull();
      expect(data?.id).toBe('saved_2');

      const callBody = JSON.parse((globalThis.fetch as any).mock.calls[0][1].body);
      expect(callBody.opportunity_id).toBe('opp_99');
      expect(callBody.status).toBe('saved');
    });

    it('updates application status and notes via PATCH /api/opportunities/saved/:id', async () => {
      const updatedItem = {
        id: 'saved_2',
        status: 'interviewing',
        notes: 'Technical screen scheduled',
      };

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updatedItem,
      });

      const { data, error } = await voxaraService.updateSavedOpportunity('saved_2', {
        status: 'interviewing',
        notes: 'Technical screen scheduled',
      });

      expect(error).toBeNull();
      expect(data?.status).toBe('interviewing');

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/opportunities/saved/saved_2'),
        expect.objectContaining({ method: 'PATCH' })
      );
    });

    it('removes opportunity from pipeline via DELETE /api/opportunities/saved/:id', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'deleted', id: 'saved_2' }),
      });

      const success = await voxaraService.deleteSavedOpportunity('saved_2');

      expect(success).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/opportunities/saved/saved_2'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('3. Persistent Notifications', () => {
    it('retrieves persistent notifications via GET /api/notifications', async () => {
      const mockNotifs = [
        {
          id: 'notif_1',
          title: 'Deadline Approaching: AI Systems Fellowship',
          message: 'Application deadline is in 2 days.',
          type: 'deadline',
          priority: 'urgent',
          is_read: false,
          requires_confirmation: false,
          created_at: '2026-10-27T00:00:00Z',
        },
      ];

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockNotifs,
      });

      const { data, error } = await voxaraService.getNotifications(false);

      expect(error).toBeNull();
      expect(data).toHaveLength(1);
      expect(data[0].type).toBe('deadline');
      expect(data[0].priority).toBe('urgent');
    });

    it('marks a single notification as read via POST /api/notifications/:id/read', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'success', marked: true }),
      });

      const success = await voxaraService.markNotificationRead('notif_1');

      expect(success).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/notifications/notif_1/read'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('marks all notifications as read via POST /api/notifications/read-all', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'success', marked_count: 3 }),
      });

      const count = await voxaraService.markAllNotificationsRead();

      expect(count).toBe(3);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/notifications/read-all'),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  describe('4. User Preferences', () => {
    it('loads user preferences via GET /api/preferences', async () => {
      const mockPref = {
        roles: ['AI Engineer', 'Software Engineer'],
        opportunity_types: ['internship', 'hackathon'],
        domains: ['Artificial Intelligence'],
        min_match_score: 0.65,
        notifications_enabled: true,
        remote_only: false,
      };

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockPref,
      });

      const { data, error } = await voxaraService.getPreferences();

      expect(error).toBeNull();
      expect(data?.roles).toContain('AI Engineer');
      expect(data?.min_match_score).toBe(0.65);
    });

    it('updates user preferences via PUT /api/preferences', async () => {
      const updatedPref = {
        roles: ['Research Scientist'],
        opportunity_types: ['fellowship'],
        domains: ['Machine Learning'],
        min_match_score: 0.8,
        notifications_enabled: true,
        remote_only: true,
      };

      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => updatedPref,
      });

      const { data, error } = await voxaraService.updatePreferences(updatedPref);

      expect(error).toBeNull();
      expect(data?.roles).toContain('Research Scientist');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/preferences'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updatedPref),
        })
      );
    });
  });

  describe('5. Authentication Error Handling', () => {
    it('handles HTTP 401 unauthorized gracefully without throwing', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Authentication token has expired.' }),
      });

      const { data, error, status } = await voxaraService.getSavedOpportunities();

      expect(status).toBe(401);
      expect(data).toHaveLength(0);
      expect(error).toContain('Authentication required or session expired');
    });

    it('handles HTTP 403 access denied gracefully', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Forbidden: Access denied.' }),
      });

      const { data, error, status } = await voxaraService.getSavedOpportunities();

      expect(status).toBe(403);
      expect(data).toHaveLength(0);
      expect(error).toContain('Access denied');
    });
  });
});
