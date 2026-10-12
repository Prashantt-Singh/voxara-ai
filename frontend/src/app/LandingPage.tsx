import React, { useState } from 'react';
import { useAssistantState } from '../hooks/useAssistantState';
import { AssistantOrb } from '../components/assistant/AssistantOrb';
import { MessageInput } from '../components/assistant/MessageInput';
import { StateSelector } from '../components/assistant/StateSelector';
import { Header } from '../components/layout/Header';
import { Container } from '../components/layout/Container';
import { Info, Sparkles } from 'lucide-react';

export const LandingPage: React.FC = () => {
  const { state, setState, metadata } = useAssistantState('idle');
  const [lastSubmission, setLastSubmission] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const handleMessageSubmit = (text: string) => {
    setLastSubmission(text);
    // Cycle state briefly to visually demonstrate input reception, then return to idle
    setState('thinking');
    setNoticeMessage(
      `Received message: "${text}". (Step 1 Foundation: Real-time LLM streaming and voice synthesis will be connected in subsequent phases).`
    );

    setTimeout(() => {
      setState('idle');
    }, 2400);
  };

  const handleMicClick = () => {
    setState('listening');
    setNoticeMessage(
      'Microphone input triggered. (Step 1 Foundation: Audio capture pipeline will be activated in Step 2).'
    );
    setTimeout(() => {
      setState('idle');
    }, 3000);
  };

  const handlePlusClick = () => {
    setNoticeMessage(
      'Action / Attachment menu triggered. (MCP tools and workflow attachments will be connected in Step 6).'
    );
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6] text-neutral-900 flex flex-col justify-between selection:bg-amber-200 selection:text-neutral-900">
      {/* Top Header */}
      <Container>
        <Header currentState={state} />
      </Container>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center py-6 sm:py-10">
        <Container className="flex flex-col items-center text-center">
          {/* Luminous Warm Gradient Orb */}
          <section
            aria-label="Assistant visual representation"
            className="mb-8 sm:mb-12 cursor-pointer transition-transform duration-300 hover:scale-[1.02]"
            onClick={() => {
              // Clicking the orb cycles to the next state for quick interactive testing
              const states = ['idle', 'listening', 'thinking', 'executing', 'speaking'] as const;
              const nextIndex = (states.indexOf(state as typeof states[number]) + 1) % states.length;
              setState(states[nextIndex] || 'idle');
            }}
            title="Click orb to cycle visual states"
          >
            <AssistantOrb state={state} />
          </section>

          {/* Typography Section */}
          <div className="space-y-2 mb-8 max-w-lg">
            <p className="text-sm sm:text-base text-neutral-500 font-normal tracking-wide">
              Hi, I'm <span className="font-semibold text-amber-600">Voxara</span>.
            </p>
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-neutral-900 leading-tight">
              How can I help you today?
            </h1>
            <p className="text-xs sm:text-sm text-neutral-400 font-light pt-1">
              {metadata.description}
            </p>
          </div>

          {/* Message / Voice Input Bar */}
          <div className="w-full max-w-lg mb-6">
            <MessageInput
              onSubmit={handleMessageSubmit}
              onMicClick={handleMicClick}
              onPlusClick={handlePlusClick}
              placeholder="Ask anything or tap mic to speak..."
            />
          </div>

          {/* Local Non-fabricated Notice Feedback */}
          {noticeMessage && (
            <div
              role="status"
              className="mt-3 max-w-md mx-auto p-3.5 bg-amber-50/80 border border-amber-200/80 rounded-2xl text-xs sm:text-sm text-amber-900 flex items-start gap-2.5 text-left animate-fadeIn shadow-xs"
            >
              <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">{noticeMessage}</p>
                {lastSubmission && (
                  <p className="text-[11px] text-amber-700/80 mt-1">
                    Echo: <em>"{lastSubmission}"</em> &bull; No LLM connected yet.
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
            <span>Step 1: Project Foundation & UI Prototype</span>
          </div>

          {/* Small development-only state selector */}
          <div className="flex items-center">
            <StateSelector currentState={state} onStateChange={setState} />
          </div>
        </Container>
      </footer>
    </div>
  );
};
