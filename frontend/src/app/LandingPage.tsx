import React, { useState } from 'react';
import { useAssistantState } from '../hooks/useAssistantState';
import { useVoiceSession } from '../hooks/useVoiceSession';
import { AssistantOrb } from '../components/assistant/AssistantOrb';
import { MessageInput } from '../components/assistant/MessageInput';
import { StateSelector } from '../components/assistant/StateSelector';
import { ActivityDrawer } from '../components/assistant/ActivityDrawer';
import { Header } from '../components/layout/Header';
import { Container } from '../components/layout/Container';
import { ASSISTANT_STATES } from '../types/assistant';
import { Info, Sparkles, AlertCircle, Radio, PhoneOff, ShieldAlert, Compass, BookmarkCheck, Activity } from 'lucide-react';

export const LandingPage: React.FC = () => {
  // Manual state override for UI development & previewing states
  const { state: manualState, setState: setManualState } = useAssistantState('idle');
  const [manualMode, setManualMode] = useState(false);

  // LiveKit WebRTC Voice Session integration
  const {
    status: voiceStatus,
    assistantState: voiceAssistantState,
    error: voiceError,
    isMicrophoneEnabled,
    roomName,
    participantCount,
    agentJoined,
    toggleSession,
    disconnect,
  } = useVoiceSession();

  const [lastSubmission, setLastSubmission] = useState<string | null>(null);
  const [textNotice, setTextNotice] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<'opportunities' | 'pipeline' | 'telemetry' | 'notifications'>('opportunities');

  // Active assistant visual state is driven by LiveKit voice events unless manual test mode is triggered
  const effectiveState = manualMode ? manualState : voiceAssistantState;
  const metadata = ASSISTANT_STATES[effectiveState];

  const handleMessageSubmit = (text: string) => {
    setLastSubmission(text);
    setTextNotice(
      `Received text message: "${text}". (Voxara is tuned for voice interaction via Gemini Live. Click the mic button to converse!)`
    );
  };

  const handleMicClick = () => {
    // When mic button is clicked, toggle the LiveKit real-time voice session
    setManualMode(false);
    setTextNotice(null);
    toggleSession();
  };

  const handlePlusClick = () => {
    setDrawerTab('opportunities');
    setIsDrawerOpen(true);
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6] text-neutral-900 flex flex-col justify-between selection:bg-amber-200 selection:text-neutral-900">
      {/* Top Header */}
      <Container>
        <Header currentState={effectiveState} />
      </Container>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center py-6 sm:py-10">
        <Container className="flex flex-col items-center text-center">
          {/* LiveKit Voice Connection Status Badge */}
          {voiceStatus !== 'disconnected' && (
            <div className="mb-6 flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all animate-fadeIn shadow-xs bg-white/90 backdrop-blur-xs">
              {voiceStatus === 'connecting' && (
                <>
                  <div className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                  <span className="text-amber-800">Connecting to LiveKit Room...</span>
                </>
              )}
              {voiceStatus === 'connected' && (
                <>
                  <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
                  <span className="text-emerald-800 font-semibold">
                    {agentJoined ? 'Voxara AI Active (Gemini Live)' : 'LiveKit Connected (Waiting for Agent)'}
                  </span>
                  {roomName && (
                    <span className="text-neutral-400 font-normal">| {roomName}</span>
                  )}
                  {participantCount > 0 && (
                    <span className="text-neutral-400 font-normal">({participantCount} peer{participantCount > 1 ? 's' : ''})</span>
                  )}
                  <button
                    onClick={disconnect}
                    title="Disconnect Voice Session"
                    className="ml-2 flex items-center gap-1 text-red-600 hover:text-red-700 hover:underline cursor-pointer"
                  >
                    <PhoneOff className="w-3 h-3" />
                    <span>Leave</span>
                  </button>
                </>
              )}
              {voiceStatus === 'error' && (
                <>
                  <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                  <span className="text-red-700 font-medium">Session Error</span>
                </>
              )}
            </div>
          )}

          {/* Luminous Warm Gradient Orb */}
          <section
            aria-label="Assistant visual representation"
            className="mb-8 sm:mb-12 cursor-pointer transition-transform duration-300 hover:scale-[1.02]"
            onClick={() => {
              if (voiceStatus === 'disconnected') {
                // If not connected, toggle session or cycle visual state preview
                toggleSession();
              }
            }}
            title={voiceStatus === 'connected' ? 'Voice session active' : 'Click to start voice session'}
          >
            <AssistantOrb state={effectiveState} />
          </section>

          {/* Typography Section */}
          <div className="space-y-2 mb-8 max-w-lg">
            <p className="text-sm sm:text-base text-neutral-500 font-normal tracking-wide">
              Hi, I'm <span className="font-semibold text-amber-600">Voxara</span>.
            </p>
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-neutral-900 leading-tight">
              {voiceStatus === 'connected'
                ? isMicrophoneEnabled
                  ? "I'm listening to your voice"
                  : 'Voice connected (mic muted)'
                : 'How can I help you today?'}
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 font-light pt-1">
              {metadata.description}
            </p>
          </div>

          {/* Workflow Quick Access Pills */}
          <div className="flex flex-wrap items-center justify-center gap-2 mb-4 max-w-lg">
            <button
              onClick={() => {
                setDrawerTab('opportunities');
                setIsDrawerOpen(true);
              }}
              className="px-3 py-1.5 rounded-full text-xs font-medium bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200/80 transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer"
            >
              <Compass className="w-3.5 h-3.5 text-amber-600" />
              <span>Opportunity Hunter</span>
            </button>
            <button
              onClick={() => {
                setDrawerTab('pipeline');
                setIsDrawerOpen(true);
              }}
              className="px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50 hover:bg-blue-100 text-blue-900 border border-blue-200/80 transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer"
            >
              <BookmarkCheck className="w-3.5 h-3.5 text-blue-600" />
              <span>My Applications</span>
            </button>
            <button
              onClick={() => {
                setDrawerTab('telemetry');
                setIsDrawerOpen(true);
              }}
              className="px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-200/80 transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-600" />
              <span>Telemetry</span>
            </button>
          </div>

          {/* Message / Voice Input Bar */}
          <div className="w-full max-w-lg mb-6">
            <MessageInput
              onSubmit={handleMessageSubmit}
              onMicClick={handleMicClick}
              onPlusClick={handlePlusClick}
              voiceSessionStatus={voiceStatus}
              isMicrophoneActive={isMicrophoneEnabled}
              placeholder={
                voiceStatus === 'connected'
                  ? 'Voice session live. Speak freely or type...'
                  : 'Ask anything or tap mic to connect LiveKit...'
              }
            />
          </div>

          {/* Error Notice Feedback (Clear connection and permission errors) */}
          {voiceError && (
            <div
              role="alert"
              className="mt-3 max-w-md mx-auto p-4 bg-red-50/90 border border-red-200 rounded-2xl text-xs sm:text-sm text-red-900 flex items-start gap-3 text-left animate-fadeIn shadow-xs"
            >
              {voiceError.type === 'permission' ? (
                <ShieldAlert className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 space-y-1">
                <p className="font-semibold text-red-950">
                  {voiceError.type === 'permission'
                    ? 'Microphone Permission Error'
                    : voiceError.type === 'configuration'
                    ? 'LiveKit Credentials Not Configured'
                    : 'Voice Connection Error'}
                </p>
                <p className="text-red-800 text-xs leading-relaxed">{voiceError.message}</p>
                {voiceError.details && (
                  <p className="text-[11px] text-red-700/90 bg-red-100/60 p-2 rounded-lg mt-1 font-mono">
                    {voiceError.details}
                  </p>
                )}
                {voiceError.type === 'configuration' && (
                  <p className="text-[11px] text-neutral-600 pt-1">
                    Tip: Set up LiveKit keys in <code className="bg-red-100 px-1 py-0.5 rounded font-mono">backend/.env</code> and start backend with <code className="bg-red-100 px-1 py-0.5 rounded font-mono">uvicorn app.main:app</code>.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Informational Notice Feedback */}
          {textNotice && !voiceError && (
            <div
              role="status"
              className="mt-3 max-w-md mx-auto p-3.5 bg-amber-50/80 border border-amber-200/80 rounded-2xl text-xs sm:text-sm text-amber-900 flex items-start gap-2.5 text-left animate-fadeIn shadow-xs"
            >
              <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">{textNotice}</p>
                {lastSubmission && (
                  <p className="text-[11px] text-amber-700/80 mt-1">
                    Echo: <em>"{lastSubmission}"</em> &bull; LiveKit voice ready. LLM pipeline planned for next phase.
                  </p>
                )}
              </div>
            </div>
          )}
        </Container>
      </main>

      {/* Footer Area with Dev State Preview Control & Milestone Badge */}
      <footer className="w-full py-4 sm:py-6 border-t border-neutral-200/50 bg-white/40 backdrop-blur-xs">
        <Container className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-neutral-400">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span>Step 3: Gemini Live Multimodal Voice AI Integration</span>
          </div>

          {/* Small development-only state selector for testing orb states */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-neutral-400 hidden md:inline">Preview:</span>
            <StateSelector
              currentState={effectiveState}
              onStateChange={(s) => {
                setManualMode(true);
                setManualState(s);
              }}
            />
          </div>
        </Container>
      </footer>
      {/* Activity Drawer & Telemetry Panel */}
      <ActivityDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        activeTabDefault={drawerTab}
      />
    </div>
  );
};
