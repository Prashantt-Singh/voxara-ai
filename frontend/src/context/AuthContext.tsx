import React, { useEffect, useState, useMemo, useCallback } from 'react';
import type { User, Session, AuthError } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../lib/supabaseClient';
import { AuthContext } from './auth-context-def';
import type { AuthNotice } from './auth-context-def';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const configured = useMemo(() => isSupabaseConfigured(), []);

  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(configured && supabase));
  const [authNotice, setAuthNotice] = useState<AuthNotice | null>(null);

  // Clear notice banner
  const clearAuthNotice = useCallback(() => {
    setAuthNotice(null);
  }, []);

  // Initialize and persist session + handle email verification & OAuth callback
  useEffect(() => {
    if (!configured || !supabase) {
      return;
    }

    const client = supabase;
    let isMounted = true;

    const initializeAuth = async () => {
      try {
        if (typeof window === 'undefined') return;

        const urlParams = new URLSearchParams(window.location.search);
        const hashClean = window.location.hash.replace(/^#/, '');
        const hashParams = new URLSearchParams(hashClean);

        // 1. Detect error parameters returned in redirect (e.g. expired link, invalid token)
        const errorDescription =
          urlParams.get('error_description') ||
          hashParams.get('error_description') ||
          urlParams.get('error') ||
          hashParams.get('error');

        if (errorDescription) {
          const decoded = decodeURIComponent(errorDescription.replace(/\+/g, ' '));
          let friendly = decoded;
          const lower = decoded.toLowerCase();

          if (
            lower.includes('expired') ||
            lower.includes('otp_expired') ||
            lower.includes('token has expired')
          ) {
            friendly = 'This email verification link has expired or has already been used. Please sign in or request a new verification email.';
          } else if (lower.includes('invalid') || lower.includes('access_denied')) {
            friendly = 'This verification link is invalid or incomplete. Please request a fresh verification link.';
          }

          if (isMounted) {
            setAuthNotice({ type: 'error', message: friendly });
            setIsLoading(false);
          }
          window.history.replaceState({}, document.title, window.location.pathname);
          return;
        }

        // 2. Detect PKCE authorization code (?code=...) from email verification link or OAuth
        const authCode = urlParams.get('code');
        if (authCode) {
          const { data, error } = await client.auth.exchangeCodeForSession(authCode);

          if (error) {
            console.warn('Code exchange error:', error.message);
            const lower = error.message.toLowerCase();
            let friendly = error.message;

            if (
              lower.includes('expired') ||
              lower.includes('invalid') ||
              lower.includes('code challenge') ||
              lower.includes('pkce')
            ) {
              friendly = 'This email verification link is invalid, expired, or has already been used. Please sign in or request a new verification email.';
            }

            if (isMounted) {
              setAuthNotice({ type: 'error', message: friendly });
            }
          } else if (data.session && isMounted) {
            setSession(data.session);
            setUser(data.user);
            setAuthNotice({
              type: 'success',
              message: 'Your email has been verified successfully! Welcome to Voxara AI.',
            });
            window.history.replaceState({}, document.title, window.location.pathname);
            setIsLoading(false);
            return;
          }
          window.history.replaceState({}, document.title, window.location.pathname);
        }

        // 3. Normal session restoration
        const { data: { session: initialSession }, error: sessionError } = await client.auth.getSession();
        if (!isMounted) return;

        if (sessionError) {
          console.warn('Error fetching Supabase session:', sessionError.message);
        }

        setSession(initialSession);
        setUser(initialSession?.user ?? null);
        setIsLoading(false);

        // Clean any residual tokens from URL safely
        if (window.location.hash.includes('access_token=') || window.location.search.includes('code=')) {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      } catch {
        if (isMounted) setIsLoading(false);
      }
    };

    initializeAuth();

    // Listen for real-time authentication state changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, currentSession) => {
      if (!isMounted) return;
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      setIsLoading(false);

      if (event === 'SIGNED_IN' && currentSession?.user) {
        // If user signs in through email verification link or OAuth
        const isEmailConfirmed = Boolean(
          currentSession.user.email_confirmed_at ||
          currentSession.user.confirmed_at ||
          currentSession.user.app_metadata?.provider === 'google'
        );
        if (isEmailConfirmed) {
          // ensure URL is cleaned
          if (typeof window !== 'undefined' && (window.location.search || window.location.hash)) {
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        }
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [configured]);

  // Google OAuth sign in
  const signInWithGoogle = useCallback(async (): Promise<{ error: string | null }> => {
    if (!configured || !supabase) {
      return { error: 'Supabase is not configured. Please add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to your .env file.' };
    }

    try {
      const redirectUrl = window.location.origin;
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: redirectUrl,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      if (error) {
        return { error: error.message };
      }
      return { error: null };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return { error: msg };
    }
  }, [configured]);

  // Email/Password login
  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<{ error: string | null; isUnconfirmedEmail?: boolean }> => {
      if (!configured || !supabase) {
        return { error: 'Supabase is not configured. Please configure your .env file.' };
      }

      try {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });

        if (error) {
          const lowerMsg = error.message.toLowerCase();
          const isUnconfirmed =
            lowerMsg.includes('email not confirmed') ||
            lowerMsg.includes('unconfirmed') ||
            lowerMsg.includes('not verified');

          return {
            error: isUnconfirmed
              ? 'Your email address is not verified yet. Please check your inbox and click the verification link before signing in.'
              : error.message,
            isUnconfirmedEmail: isUnconfirmed,
          };
        }

        // Check if user email is unconfirmed even if login returned a user object
        if (data.user && !data.user.email_confirmed_at && !data.user.confirmed_at) {
          return {
            error: 'Your email address is not verified yet. Please check your inbox and click the verification link before signing in.',
            isUnconfirmedEmail: true,
          };
        }

        setSession(data.session);
        setUser(data.user);
        return { error: null };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return { error: msg };
      }
    },
    [configured]
  );

  // Email/Password signup using standard email verification link flow
  const signUpWithPassword = useCallback(
    async (
      email: string,
      password: string
    ): Promise<{ success: boolean; error: string | null; confirmationRequired: boolean }> => {
      if (!configured || !supabase) {
        return {
          success: false,
          error: 'Supabase is not configured. Please configure your .env file.',
          confirmationRequired: false,
        };
      }

      if (password.length < 8) {
        return {
          success: false,
          error: 'Password must be at least 8 characters long.',
          confirmationRequired: false,
        };
      }

      try {
        const redirectUrl = window.location.origin;
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            emailRedirectTo: redirectUrl,
          },
        });

        if (error) {
          return { success: false, error: error.message, confirmationRequired: false };
        }

        // Check if email confirmation is required (session will be null until the link is clicked)
        const isAlreadyConfirmed = Boolean(data.user?.email_confirmed_at || data.user?.confirmed_at);

        if (isAlreadyConfirmed && data.session) {
          setSession(data.session);
          setUser(data.user);
          return { success: true, error: null, confirmationRequired: false };
        }

        return { success: true, error: null, confirmationRequired: true };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return { success: false, error: msg, confirmationRequired: false };
      }
    },
    [configured]
  );

  // Resend confirmation email link respecting Supabase rate limits
  const resendVerificationEmail = useCallback(
    async (email: string): Promise<{ success: boolean; error: string | null }> => {
      if (!configured || !supabase) {
        return {
          success: false,
          error: 'Supabase is not configured. Please configure your .env file.',
        };
      }

      try {
        const redirectUrl = window.location.origin;
        const { error } = await supabase.auth.resend({
          type: 'signup',
          email: email.trim(),
          options: {
            emailRedirectTo: redirectUrl,
          },
        });

        if (error) {
          const lower = (error as AuthError).message.toLowerCase();
          if (lower.includes('security') || lower.includes('rate limit') || lower.includes('seconds')) {
            return {
              success: false,
              error: 'Rate limit reached. For security, please wait a minute before requesting another verification email.',
            };
          }
          return { success: false, error: error.message };
        }

        return { success: true, error: null };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return { success: false, error: msg };
      }
    },
    [configured]
  );

  // Sign out user
  const signOut = useCallback(async (): Promise<{ error: string | null }> => {
    if (!configured || !supabase) {
      setSession(null);
      setUser(null);
      return { error: null };
    }

    try {
      const { error } = await supabase.auth.signOut();
      setSession(null);
      setUser(null);
      if (error) {
        return { error: error.message };
      }
      return { error: null };
    } catch (err: unknown) {
      setSession(null);
      setUser(null);
      const msg = err instanceof Error ? err.message : String(err);
      return { error: msg };
    }
  }, [configured]);

  const value = useMemo(
    () => ({
      user,
      session,
      isLoading,
      isConfigured: configured,
      authNotice,
      clearAuthNotice,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      resendVerificationEmail,
      signOut,
    }),
    [
      user,
      session,
      isLoading,
      configured,
      authNotice,
      clearAuthNotice,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      resendVerificationEmail,
      signOut,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
