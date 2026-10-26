import React, { useEffect, useState, useMemo, useCallback } from 'react';
import type { User, Session, AuthError } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../lib/supabaseClient';
import { AuthContext } from './auth-context-def';
import type { VerifyOtpResult } from './auth-context-def';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const configured = useMemo(() => isSupabaseConfigured(), []);

  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(configured && supabase));

  const [oauthError, setOauthError] = useState<string | null>(() => {
    try {
      if (typeof window === 'undefined') return null;
      const urlParams = new URLSearchParams(window.location.search);
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
      const errorDescription =
        urlParams.get('error_description') ||
        hashParams.get('error_description') ||
        urlParams.get('error') ||
        hashParams.get('error');

      return errorDescription ? decodeURIComponent(errorDescription.replace(/\+/g, ' ')) : null;
    } catch {
      return null;
    }
  });

  // Clear OAuth error banner
  const clearOAuthError = useCallback(() => {
    setOauthError(null);
  }, []);

  // Clean URL after extracting OAuth error
  useEffect(() => {
    if (oauthError && typeof window !== 'undefined') {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [oauthError]);

  // Initialize and persist session
  useEffect(() => {
    if (!configured || !supabase) {
      return;
    }

    const client = supabase;
    let isMounted = true;

    // If URL contains PKCE auth code (e.g. from confirmation link or OAuth), exchange it for a session
    const urlParams = new URLSearchParams(window.location.search);
    const authCode = urlParams.get('code');

    const initializeAuth = async () => {
      try {
        if (authCode) {
          const { data, error } = await client.auth.exchangeCodeForSession(authCode);
          if (!error && data.session && isMounted) {
            setSession(data.session);
            setUser(data.user);
            setIsLoading(false);
            window.history.replaceState({}, document.title, window.location.pathname);
            return;
          }
        }

        const { data: { session: initialSession }, error } = await client.auth.getSession();
        if (!isMounted) return;
        if (error) {
          console.warn('Error fetching Supabase session:', error.message);
        }
        setSession(initialSession);
        setUser(initialSession?.user ?? null);
        setIsLoading(false);

        // If tokens existed in hash/search, clean URL cleanly
        if (window.location.hash.includes('access_token=') || window.location.search.includes('code=')) {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      } catch (err) {
        if (isMounted) setIsLoading(false);
      }
    };

    initializeAuth();

    // Listen for real-time authentication state changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, currentSession) => {
      if (!isMounted) return;
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      setIsLoading(false);
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
              ? 'Your email address is not verified yet. Please enter the 6-digit verification code.'
              : error.message,
            isUnconfirmedEmail: isUnconfirmed,
          };
        }

        // Check if user email is unconfirmed even if login returned a user object
        if (data.user && !data.user.email_confirmed_at && !data.user.confirmed_at) {
          return {
            error: 'Your email address is not verified yet. Please enter the 6-digit verification code.',
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

  // Email/Password signup with mandatory email confirmation
  const signUpWithPassword = useCallback(
    async (
      email: string,
      password: string
    ): Promise<{ success: boolean; error: string | null; requiresOtp: boolean }> => {
      if (!configured || !supabase) {
        return {
          success: false,
          error: 'Supabase is not configured. Please configure your .env file.',
          requiresOtp: false,
        };
      }

      if (password.length < 8) {
        return {
          success: false,
          error: 'Password must be at least 8 characters long.',
          requiresOtp: false,
        };
      }

      try {
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            emailRedirectTo: window.location.origin,
          },
        });

        if (error) {
          return { success: false, error: error.message, requiresOtp: false };
        }

        // If email confirmation is enabled, data.user is created but data.session is null until OTP is verified.
        const isAlreadyConfirmed = Boolean(data.user?.email_confirmed_at || data.user?.confirmed_at);

        if (isAlreadyConfirmed && data.session) {
          setSession(data.session);
          setUser(data.user);
          return { success: true, error: null, requiresOtp: false };
        }

        return { success: true, error: null, requiresOtp: true };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return { success: false, error: msg, requiresOtp: false };
      }
    },
    [configured]
  );

  // Verify 6-digit OTP code using official Supabase verifyOtp
  const verifyOtp = useCallback(
    async (
      email: string,
      token: string,
      type: 'signup' | 'email' = 'signup'
    ): Promise<VerifyOtpResult> => {
      if (!configured || !supabase) {
        return {
          success: false,
          error: 'Supabase is not configured. Please configure your .env file.',
        };
      }

      const cleanToken = token.trim();
      if (!cleanToken || cleanToken.length !== 6) {
        return {
          success: false,
          error: 'Please enter a complete 6-digit verification code.',
          isInvalid: true,
        };
      }

      try {
        // Attempt verifyOtp with specified type (default: signup)
        let { data, error } = await supabase.auth.verifyOtp({
          email: email.trim(),
          token: cleanToken,
          type,
        });

        // Fallback retry with type 'email' if signup type failed with invalid/expired
        if (error && type === 'signup') {
          const lower = error.message.toLowerCase();
          if (lower.includes('invalid') || lower.includes('expired')) {
            const fallback = await supabase.auth.verifyOtp({
              email: email.trim(),
              token: cleanToken,
              type: 'email',
            });
            if (!fallback.error) {
              data = fallback.data;
              error = null;
            }
          }
        }

        if (error) {
          const lower = error.message.toLowerCase();
          const isExpired = lower.includes('expired');
          const isInvalid = lower.includes('invalid') || lower.includes('incorrect');

          let friendlyError = error.message;
          if (isExpired) {
            friendlyError = 'The verification code has expired. Please request a new code.';
          } else if (isInvalid) {
            friendlyError = 'Invalid 6-digit verification code. Please check your email and try again.';
          }

          return {
            success: false,
            error: friendlyError,
            isExpired,
            isInvalid,
          };
        }

        if (data.session) {
          setSession(data.session);
          setUser(data.user);
        } else if (data.user) {
          setUser(data.user);
        }

        return {
          success: true,
          error: null,
        };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          success: false,
          error: msg,
        };
      }
    },
    [configured]
  );

  // Resend 6-digit confirmation OTP respecting Supabase rate limits
  const resendOtp = useCallback(
    async (email: string, type: 'signup' | 'email' = 'signup'): Promise<{ success: boolean; error: string | null }> => {
      if (!configured || !supabase) {
        return {
          success: false,
          error: 'Supabase is not configured. Please configure your .env file.',
        };
      }

      try {
        const { error } = await supabase.auth.resend({
          type: type as 'signup' | 'email_change',
          email: email.trim(),
          options: {
            emailRedirectTo: window.location.origin,
          },
        });

        if (error) {
          const lower = (error as AuthError).message.toLowerCase();
          if (lower.includes('security') || lower.includes('rate limit') || lower.includes('seconds')) {
            return {
              success: false,
              error: 'Rate limit reached. For security, please wait a minute before requesting another code.',
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
      oauthError,
      clearOAuthError,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      verifyOtp,
      resendOtp,
      signOut,
    }),
    [
      user,
      session,
      isLoading,
      configured,
      oauthError,
      clearOAuthError,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      verifyOtp,
      resendOtp,
      signOut,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
