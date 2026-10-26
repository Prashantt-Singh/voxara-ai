import { createContext } from 'react';
import type { User, Session } from '@supabase/supabase-js';

export interface VerifyOtpResult {
  success: boolean;
  error: string | null;
  isExpired?: boolean;
  isInvalid?: boolean;
}

export interface AuthContextType {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isConfigured: boolean;
  oauthError: string | null;
  clearOAuthError: () => void;
  signInWithGoogle: () => Promise<{ error: string | null }>;
  signInWithPassword: (email: string, password: string) => Promise<{ error: string | null; isUnconfirmedEmail?: boolean }>;
  signUpWithPassword: (email: string, password: string) => Promise<{ success: boolean; error: string | null; requiresOtp: boolean }>;
  verifyOtp: (email: string, token: string, type?: 'signup' | 'email') => Promise<VerifyOtpResult>;
  resendOtp: (email: string, type?: 'signup' | 'email') => Promise<{ success: boolean; error: string | null }>;
  signOut: () => Promise<{ error: string | null }>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
