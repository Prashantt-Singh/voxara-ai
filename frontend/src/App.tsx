import React from 'react';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import { LandingPage } from './app/LandingPage';
import { AuthScreen } from './components/auth/AuthScreen';

const MainAppRouter: React.FC = () => {
  const { user, isLoading } = useAuth();

  // Show a clean loading indicator while checking session tokens
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#FAF9F6] flex flex-col items-center justify-center selection:bg-amber-200">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-3 h-3 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-400" />
          <span className="font-semibold text-neutral-900 tracking-tight text-lg">
            Voxara<span className="text-amber-500 font-medium">.ai</span>
          </span>
        </div>
        <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-neutral-400 mt-3 font-medium">Restoring session...</p>
      </div>
    );
  }

  // Enforce authentication gate: User must be signed in AND have confirmed email
  const isVerified = Boolean(
    user && (user.email_confirmed_at || user.confirmed_at || user.app_metadata?.provider === 'google')
  );

  if (!user || !isVerified) {
    return <AuthScreen />;
  }

  // Once authenticated and verified, provide full access to the Voxara dashboard
  return <LandingPage />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <MainAppRouter />
    </AuthProvider>
  );
};

export default App;
