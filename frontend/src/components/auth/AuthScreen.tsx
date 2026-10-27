import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import {
  AlertCircle,
  Mail,
  Lock,
  ArrowRight,
  Sparkles,
  Info,
  X,
  ShieldAlert,
  MailCheck,
  RefreshCw,
  CheckCircle2,
  ArrowLeft,
} from 'lucide-react';

export const AuthScreen: React.FC = () => {
  const {
    isConfigured,
    authNotice,
    clearAuthNotice,
    signInWithGoogle,
    signInWithPassword,
    signUpWithPassword,
    resendVerificationEmail,
  } = useAuth();

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');

  // Email verification link flow state
  const [verificationPendingEmail, setVerificationPendingEmail] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState<number>(0);
  const [isResending, setIsResending] = useState<boolean>(false);
  const [resendNotice, setResendNotice] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);

  // Form submission state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUnconfirmedError, setIsUnconfirmedError] = useState<boolean>(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState<boolean>(false);

  // Cooldown countdown effect
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const resetFormState = () => {
    setErrorMessage(null);
    setIsUnconfirmedError(false);
    setResendNotice(null);
    setResendError(null);
  };

  const handleModeSwitch = (newMode: 'signin' | 'signup') => {
    setMode(newMode);
    resetFormState();
    setPassword('');
    setConfirmPassword('');
  };

  const handleGoogleSignIn = async () => {
    setIsGoogleLoading(true);
    resetFormState();
    try {
      const res = await signInWithGoogle();
      if (res.error) {
        setErrorMessage(res.error);
        setIsGoogleLoading(false);
      }
      // On success, browser redirects to Google OAuth
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
      setIsGoogleLoading(false);
    }
  };

  const handleSignInSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please fill in both email and password.');
      return;
    }

    setIsLoading(true);
    resetFormState();

    try {
      const res = await signInWithPassword(email, password);
      if (res.error) {
        setErrorMessage(res.error);
        if (res.isUnconfirmedEmail) {
          setIsUnconfirmedError(true);
        }
      }
      // On success, AuthContext triggers session update and App will re-render
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage('Please fill in all fields.');
      return;
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long as required by your project settings.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match. Please verify your password.');
      return;
    }

    setIsLoading(true);
    resetFormState();

    try {
      const res = await signUpWithPassword(email, password);
      if (res.error) {
        setErrorMessage(res.error);
      } else if (res.confirmationRequired) {
        // Transition to "Check your email" confirmation screen
        setVerificationPendingEmail(email);
        setResendCooldown(60);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerification = async (targetEmail: string) => {
    if (!targetEmail || resendCooldown > 0 || isResending) return;

    setIsResending(true);
    setResendNotice(null);
    setResendError(null);

    try {
      const res = await resendVerificationEmail(targetEmail);
      if (res.success) {
        setResendNotice('A fresh verification link has been sent to your email.');
        setResendCooldown(60);
      } else {
        setResendError(res.error || 'Failed to resend verification email.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setResendError(msg);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6] text-neutral-900 flex flex-col justify-between selection:bg-amber-200 selection:text-neutral-900 px-4 py-8">
      {/* Top minimal bar */}
      <div className="w-full max-w-5xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-400" />
          <span className="font-semibold text-neutral-900 tracking-tight text-base sm:text-lg">
            Voxara<span className="text-amber-500 font-medium">.ai</span>
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-neutral-500 bg-white/80 border border-neutral-200/80 px-3 py-1 rounded-full shadow-2xs">
          <Sparkles className="w-3 h-3 text-amber-500" />
          <span>Supabase Auth</span>
        </div>
      </div>

      {/* Main Container */}
      <div className="w-full max-w-md mx-auto my-auto pt-6 pb-8">
        {/* Unconfigured Alert Notice */}
        {!isConfigured && (
          <div
            role="alert"
            className="mb-6 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-950 text-xs text-left shadow-2xs animate-fadeIn"
          >
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <p className="font-semibold text-amber-900 text-sm">
                  Supabase Environment Configuration Required
                </p>
                <p className="text-amber-800 leading-relaxed">
                  To connect your project, add your Supabase credentials to <code className="bg-amber-100 font-mono px-1 py-0.5 rounded">frontend/.env</code>:
                </p>
                <div className="bg-amber-100/70 p-2.5 rounded-lg font-mono text-[11px] text-amber-950 mt-2 space-y-0.5">
                  <p>VITE_SUPABASE_URL=https://&lt;project-id&gt;.supabase.co</p>
                  <p>VITE_SUPABASE_ANON_KEY=&lt;your-anon-publishable-key&gt;</p>
                </div>
                <p className="text-[11px] text-amber-700/90 pt-1">
                  Find these in your Supabase dashboard under <strong>Project Settings &gt; API</strong>.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Auth Notice (Success / Error from verification callback or OAuth) */}
        {authNotice && (
          <div
            role={authNotice.type === 'error' ? 'alert' : 'status'}
            className={`mb-6 p-4 rounded-2xl text-xs text-left shadow-2xs flex items-start gap-2.5 animate-fadeIn ${
              authNotice.type === 'error'
                ? 'bg-red-50 border border-red-200 text-red-950'
                : 'bg-emerald-50 border border-emerald-200 text-emerald-950'
            }`}
          >
            {authNotice.type === 'error' ? (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-medium leading-relaxed">{authNotice.message}</p>
            </div>
            <button
              onClick={clearAuthNotice}
              className="text-neutral-400 hover:text-neutral-600 cursor-pointer p-0.5"
              aria-label="Dismiss notice"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Card Frame */}
        <div className="bg-white rounded-3xl border border-neutral-200/90 p-6 sm:p-8 shadow-xs backdrop-blur-xs">
          {verificationPendingEmail ? (
            /* Dedicated Check Your Email Confirmation Screen */
            <div className="text-center animate-fadeIn">
              <div className="mx-auto w-14 h-14 rounded-2xl bg-amber-50 border border-amber-200/80 flex items-center justify-center mb-4 text-amber-600 shadow-2xs">
                <MailCheck className="w-7 h-7" />
              </div>

              <h2 className="text-xl sm:text-2xl font-bold text-neutral-900 tracking-tight">
                Check your inbox
              </h2>

              <p className="text-xs sm:text-sm text-neutral-600 mt-2 max-w-sm mx-auto leading-relaxed">
                We sent a confirmation link to:
                <br />
                <span className="font-semibold text-neutral-900 break-all">{verificationPendingEmail}</span>
              </p>

              <div className="my-5 p-3.5 bg-amber-50/70 border border-amber-200/70 rounded-xl text-left text-xs text-amber-950 flex items-start gap-2.5">
                <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium">Click the link in the email to activate your account.</p>
                  <p className="text-[11px] text-amber-800 leading-relaxed">
                    Once clicked, you will be redirected back to Voxara AI. If you don't see the email within a minute, make sure to check your spam folder.
                  </p>
                </div>
              </div>

              {resendNotice && (
                <div
                  role="status"
                  className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2 text-left animate-fadeIn"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{resendNotice}</span>
                </div>
              )}

              {resendError && (
                <div
                  role="alert"
                  className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs flex items-start gap-2 text-left animate-fadeIn"
                >
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <span>{resendError}</span>
                </div>
              )}

              {/* Resend Link Action */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => handleResendVerification(verificationPendingEmail)}
                  disabled={resendCooldown > 0 || isResending}
                  className="text-xs font-medium text-amber-600 hover:text-amber-700 disabled:text-neutral-400 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-1.5 cursor-pointer"
                >
                  {isResending ? (
                    <>
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      <span>Sending verification email...</span>
                    </>
                  ) : resendCooldown > 0 ? (
                    <span>Resend email in {resendCooldown}s</span>
                  ) : (
                    <>
                      <RefreshCw className="w-3 h-3" />
                      <span>Resend verification link</span>
                    </>
                  )}
                </button>
              </div>

              <div className="mt-6 pt-5 border-t border-neutral-100">
                <button
                  type="button"
                  onClick={() => {
                    setVerificationPendingEmail(null);
                    setMode('signin');
                  }}
                  className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-800 transition-colors cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to sign in</span>
                </button>
              </div>
            </div>
          ) : (
            /* Sign In / Sign Up Forms */
            <div>
              {/* Header Title */}
              <div className="text-center mb-6">
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900">
                  {mode === 'signin' ? 'Welcome back' : 'Create an account'}
                </h1>
                <p className="text-xs sm:text-sm text-neutral-500 mt-1.5">
                  {mode === 'signin'
                    ? 'Sign in to access your Voxara AI assistant & opportunities'
                    : 'Get started with real-time AI opportunities & voice intelligence'}
                </p>
              </div>

              {/* Mode Switcher Tabs */}
              <div className="grid grid-cols-2 p-1 bg-neutral-100/80 rounded-xl mb-6">
                <button
                  type="button"
                  onClick={() => handleModeSwitch('signin')}
                  className={`py-2 text-xs sm:text-sm font-medium rounded-lg transition-all cursor-pointer ${
                    mode === 'signin'
                      ? 'bg-white text-neutral-900 shadow-2xs'
                      : 'text-neutral-500 hover:text-neutral-900'
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => handleModeSwitch('signup')}
                  className={`py-2 text-xs sm:text-sm font-medium rounded-lg transition-all cursor-pointer ${
                    mode === 'signup'
                      ? 'bg-white text-neutral-900 shadow-2xs'
                      : 'text-neutral-500 hover:text-neutral-900'
                  }`}
                >
                  Create Account
                </button>
              </div>

              {/* Google OAuth Button */}
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={isGoogleLoading || isLoading || !isConfigured}
                className="w-full py-2.5 px-4 rounded-xl font-medium text-xs sm:text-sm text-neutral-800 bg-white border border-neutral-200/90 hover:bg-neutral-50/80 hover:border-neutral-300 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-2xs flex items-center justify-center gap-2.5 cursor-pointer"
              >
                {isGoogleLoading ? (
                  <div className="w-4 h-4 border-2 border-neutral-700 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                )}
                <span>Continue with Google</span>
              </button>

              {/* Divider */}
              <div className="relative my-6 text-center">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-neutral-200/80" />
                </div>
                <span className="relative bg-white px-3 text-[11px] uppercase tracking-wider text-neutral-400 font-medium">
                  or with email
                </span>
              </div>

              {/* Error Notice */}
              {errorMessage && (
                <div
                  role="alert"
                  className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs text-left animate-fadeIn"
                >
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium leading-relaxed">{errorMessage}</p>
                      {isUnconfirmedError && (
                        <div className="mt-2.5 pt-2 border-t border-red-200/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                          <span className="text-[11px] text-red-800">Need a fresh verification link?</span>
                          <button
                            type="button"
                            onClick={() => handleResendVerification(email)}
                            disabled={resendCooldown > 0 || isResending}
                            className="text-xs font-semibold text-amber-800 hover:text-amber-950 underline disabled:text-neutral-400 disabled:no-underline cursor-pointer inline-flex items-center gap-1"
                          >
                            {isResending ? (
                              <>
                                <RefreshCw className="w-3 h-3 animate-spin" />
                                <span>Sending...</span>
                              </>
                            ) : resendCooldown > 0 ? (
                              <span>Resend in {resendCooldown}s</span>
                            ) : (
                              <>
                                <RefreshCw className="w-3 h-3" />
                                <span>Resend link</span>
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Resend Notice when in signin mode */}
              {resendNotice && mode === 'signin' && (
                <div
                  role="status"
                  className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2 text-left animate-fadeIn"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{resendNotice}</span>
                </div>
              )}

              {/* Forms */}
              {mode === 'signin' ? (
                /* Sign In Form */
                <form onSubmit={handleSignInSubmit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-neutral-700 mb-1.5 text-left">
                      Email address
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                      <input
                        type="email"
                        required
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@domain.com"
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-neutral-200 bg-neutral-50/50 text-neutral-900 focus:bg-white focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-hidden transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-neutral-700 mb-1.5 text-left">
                      Password
                    </label>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                      <input
                        type="password"
                        required
                        autoComplete="current-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-neutral-200 bg-neutral-50/50 text-neutral-900 focus:bg-white focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-hidden transition-all"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading || !isConfigured}
                    className="w-full py-2.5 px-4 rounded-xl font-medium text-xs sm:text-sm text-neutral-900 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer mt-2"
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-neutral-900 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <span>Sign In</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </form>
              ) : (
                /* Sign Up Form */
                <form onSubmit={handleSignUpSubmit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-neutral-700 mb-1.5 text-left">
                      Email address
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                      <input
                        type="email"
                        required
                        autoComplete="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@domain.com"
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-neutral-200 bg-neutral-50/50 text-neutral-900 focus:bg-white focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-hidden transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium text-neutral-700 text-left">
                        Password
                      </label>
                      <span className="text-[10px] text-neutral-400">Min 8 characters</span>
                    </div>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                      <input
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-neutral-200 bg-neutral-50/50 text-neutral-900 focus:bg-white focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-hidden transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-neutral-700 mb-1.5 text-left">
                      Confirm Password
                    </label>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                      <input
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm rounded-xl border border-neutral-200 bg-neutral-50/50 text-neutral-900 focus:bg-white focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-hidden transition-all"
                      />
                    </div>
                  </div>

                  <div className="p-3 bg-amber-50/60 border border-amber-200/60 rounded-xl text-left flex items-start gap-2">
                    <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <p className="text-[11px] text-amber-900 leading-relaxed">
                      After signing up, a <strong>confirmation link</strong> will be sent to your email to verify your account.
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading || !isConfigured}
                    className="w-full py-2.5 px-4 rounded-xl font-medium text-xs sm:text-sm text-neutral-900 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer mt-2"
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-neutral-900 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <span>Create Account</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Minimal Footer */}
      <div className="w-full max-w-md mx-auto text-center text-xs text-neutral-400">
        <p>Voxara AI &bull; Autonomous Opportunity Discovery & Voice Intelligence</p>
      </div>
    </div>
  );
};
