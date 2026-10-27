import { createContext } from 'react';
import type { User, Session } from '@supabase/supabase-js';

export interface AuthNotice {
  type: 'success' | 'error' | 'info';
  message: string;
}

export interface AuthContextType {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isConfigured: boolean;
  authNotice: AuthNotice | null;
  clearAuthNotice: () => void;
  signInWithGoogle: () => Promise<{ error: string | null }>;
  signInWithPassword: (email: string, password: string) => Promise<{ error: string | null; isUnconfirmedEmail?: boolean }>;
  signUpWithPassword: (email: string, password: string) => Promise<{ success: boolean; error: string | null; confirmationRequired: boolean }>;
  resendVerificationEmail: (email: string) => Promise<{ success: boolean; error: string | null }>;
  signOut: () => Promise<{ error: string | null }>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
