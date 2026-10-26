import React, { useState } from 'react';
import { ASSISTANT_STATES } from '../../types/assistant';
import type { AssistantState } from '../../types/assistant';
import { useAuth } from '../../hooks/useAuth';
import { LogOut } from 'lucide-react';

interface HeaderProps {
  currentState: AssistantState;
}

/**
 * Minimalist top navigation bar with brand badge, live state pill, and authenticated user profile with sign-out.
 */
export const Header: React.FC<HeaderProps> = ({ currentState }) => {
  const metadata = ASSISTANT_STATES[currentState];
  const { user, signOut } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOut();
    } finally {
      setIsSigningOut(false);
    }
  };

  const userEmail = user?.email || user?.user_metadata?.email || '';
  const initial = userEmail ? userEmail.charAt(0).toUpperCase() : 'U';

  return (
    <header className="w-full py-4 sm:py-6" role="banner">
      <div className="flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-400" />
          <span className="font-semibold text-neutral-900 tracking-tight text-base sm:text-lg">
            Voxara<span className="text-amber-500 font-medium">.ai</span>
          </span>
        </div>

        {/* Right side: Status label & User session controls */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Small unobtrusive status label */}
          <div
            className="hidden sm:flex items-center gap-2 px-3 py-1 bg-white/80 border border-neutral-200/80 rounded-full shadow-2xs text-xs text-neutral-600"
            aria-live="polite"
          >
            <span
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: metadata.accentColor }}
            />
            <span className="font-medium text-neutral-700">{metadata.label}</span>
          </div>

          {/* Authenticated user pill & sign-out action */}
          {user && (
            <div className="flex items-center gap-2 bg-white/90 border border-neutral-200/90 rounded-full pl-1.5 pr-2 py-1 shadow-2xs text-xs">
              <div
                className="w-6 h-6 rounded-full bg-amber-100 text-amber-900 font-semibold flex items-center justify-center text-[11px] shrink-0"
                title={userEmail}
              >
                {initial}
              </div>
              <span
                className="font-medium text-neutral-700 max-w-[120px] sm:max-w-[180px] truncate hidden md:inline"
                title={userEmail}
              >
                {userEmail}
              </span>
              <button
                onClick={handleSignOut}
                disabled={isSigningOut}
                title="Sign out of Voxara AI"
                className="p-1 text-neutral-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-all cursor-pointer flex items-center gap-1"
                aria-label="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="text-[11px] hidden sm:inline text-neutral-500 hover:text-red-600">
                  {isSigningOut ? 'Signing out...' : 'Sign Out'}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
