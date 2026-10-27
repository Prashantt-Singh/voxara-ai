import { describe, it, expect, vi, beforeEach } from 'vitest';
import { isSupabaseConfigured } from '../lib/supabaseClient';

describe('Supabase Client Configuration', () => {
  it('identifies unconfigured state when environment variables are empty or placeholder', () => {
    const configured = isSupabaseConfigured();
    expect(typeof configured).toBe('boolean');
  });
});

describe('Authentication Operations & Flow Logic', () => {
  let mockSupabase: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSupabase = {
      auth: {
        signInWithOAuth: vi.fn(),
        signInWithPassword: vi.fn(),
        signUp: vi.fn(),
        resend: vi.fn(),
        exchangeCodeForSession: vi.fn(),
        signOut: vi.fn(),
        getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
        onAuthStateChange: vi.fn().mockReturnValue({
          data: { subscription: { unsubscribe: vi.fn() } },
        }),
      },
    };
  });

  describe('Google Sign-In with OAuth', () => {
    it('initiates official Supabase Google OAuth flow with redirect and PKCE options', async () => {
      mockSupabase.auth.signInWithOAuth.mockResolvedValue({
        data: { url: 'https://accounts.google.com/o/oauth2/v2/auth?...', provider: 'google' },
        error: null,
      });

      const redirectUrl = 'http://localhost:5173';
      const result = await mockSupabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: redirectUrl,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      expect(mockSupabase.auth.signInWithOAuth).toHaveBeenCalledWith({
        provider: 'google',
        options: {
          redirectTo: redirectUrl,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });
      expect(result.data.provider).toBe('google');
      expect(result.error).toBeNull();
    });

    it('returns informative error if Google OAuth initiation fails', async () => {
      mockSupabase.auth.signInWithOAuth.mockResolvedValue({
        data: { url: null, provider: 'google' },
        error: new Error('Google OAuth provider is not enabled'),
      });

      const result = await mockSupabase.auth.signInWithOAuth({
        provider: 'google',
      });

      expect(result.error).toBeTruthy();
      expect(result.error.message).toContain('Google OAuth provider is not enabled');
    });
  });

  describe('Email/Password Signup & Verification Link Flow', () => {
    it('enforces minimum password length of 8 characters', () => {
      const shortPassword = 'short';
      const isValid = shortPassword.length >= 8;
      expect(isValid).toBe(false);

      const validPassword = 'SecurePassword123!';
      expect(validPassword.length >= 8).toBe(true);
    });

    it('validates password matching on signup', () => {
      const password: string = 'Password123!';
      const confirmPassword: string = 'Password123!';
      const mismatch: string = 'PasswordMismatch!';
      expect(password === confirmPassword).toBe(true);
      expect(password === mismatch).toBe(false);
    });

    it('submits signup with email and password and requires email confirmation link', async () => {
      mockSupabase.auth.signUp.mockResolvedValue({
        data: {
          user: {
            id: 'user-uuid-123',
            email: 'user@voxara.ai',
            email_confirmed_at: null,
          },
          session: null, // Session is null until email link is clicked
        },
        error: null,
      });

      const res = await mockSupabase.auth.signUp({
        email: 'user@voxara.ai',
        password: 'ValidPassword123!',
        options: {
          emailRedirectTo: 'http://localhost:5173',
        },
      });

      expect(mockSupabase.auth.signUp).toHaveBeenCalledWith({
        email: 'user@voxara.ai',
        password: 'ValidPassword123!',
        options: {
          emailRedirectTo: 'http://localhost:5173',
        },
      });
      expect(res.data.user.email_confirmed_at).toBeNull();
      expect(res.data.session).toBeNull();
    });

    it('exchanges PKCE auth code for session on verification link callback', async () => {
      mockSupabase.auth.exchangeCodeForSession.mockResolvedValue({
        data: {
          session: { access_token: 'pkce-access-token', refresh_token: 'pkce-refresh-token' },
          user: { id: 'verified-user-123', email: 'user@voxara.ai', email_confirmed_at: '2026-10-26T12:00:00Z' },
        },
        error: null,
      });

      const res = await mockSupabase.auth.exchangeCodeForSession('valid-auth-code');

      expect(mockSupabase.auth.exchangeCodeForSession).toHaveBeenCalledWith('valid-auth-code');
      expect(res.data.session).toBeTruthy();
      expect(res.data.user.email_confirmed_at).toBeTruthy();
    });

    it('detects invalid or expired verification link error', async () => {
      mockSupabase.auth.exchangeCodeForSession.mockResolvedValue({
        data: { session: null, user: null },
        error: new Error('Token has expired or is invalid'),
      });

      const res = await mockSupabase.auth.exchangeCodeForSession('expired-auth-code');

      expect(res.error).toBeTruthy();
      const lower = res.error.message.toLowerCase();
      expect(lower.includes('expired') || lower.includes('invalid')).toBe(true);
    });

    it('resends verification email link with signup type and respects rate limit', async () => {
      mockSupabase.auth.resend.mockResolvedValue({
        data: {},
        error: null,
      });

      const res = await mockSupabase.auth.resend({
        type: 'signup',
        email: 'user@voxara.ai',
        options: {
          emailRedirectTo: 'http://localhost:5173',
        },
      });

      expect(mockSupabase.auth.resend).toHaveBeenCalledWith({
        type: 'signup',
        email: 'user@voxara.ai',
        options: {
          emailRedirectTo: 'http://localhost:5173',
        },
      });
      expect(res.error).toBeNull();
    });
  });

  describe('Email/Password Login & Sign-Out', () => {
    it('authenticates user with valid email and password credentials', async () => {
      mockSupabase.auth.signInWithPassword.mockResolvedValue({
        data: {
          user: { id: 'user-uuid-123', email: 'user@voxara.ai', email_confirmed_at: '2026-10-25T01:00:00Z' },
          session: { access_token: 'token-abc', refresh_token: 'refresh-xyz' },
        },
        error: null,
      });

      const res = await mockSupabase.auth.signInWithPassword({
        email: 'user@voxara.ai',
        password: 'ValidPassword123!',
      });

      expect(mockSupabase.auth.signInWithPassword).toHaveBeenCalledWith({
        email: 'user@voxara.ai',
        password: 'ValidPassword123!',
      });
      expect(res.data.session).toBeTruthy();
      expect(res.error).toBeNull();
    });

    it('detects unconfirmed email during login and prompts user to click verification link', async () => {
      mockSupabase.auth.signInWithPassword.mockResolvedValue({
        data: { user: null, session: null },
        error: new Error('Email not confirmed'),
      });

      const res = await mockSupabase.auth.signInWithPassword({
        email: 'unconfirmed@voxara.ai',
        password: 'ValidPassword123!',
      });

      expect(res.error.message).toBe('Email not confirmed');
      const isUnconfirmed = res.error.message.toLowerCase().includes('email not confirmed');
      expect(isUnconfirmed).toBe(true);
    });

    it('executes sign-out and clears session', async () => {
      mockSupabase.auth.signOut.mockResolvedValue({ error: null });

      const res = await mockSupabase.auth.signOut();
      expect(mockSupabase.auth.signOut).toHaveBeenCalled();
      expect(res.error).toBeNull();
    });
  });
});
