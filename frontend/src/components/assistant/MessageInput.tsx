import React, { useState } from 'react';
import { Plus, Mic, ArrowUp } from 'lucide-react';

interface MessageInputProps {
  /** Callback fired when a message or voice input is initiated */
  onSubmit?: (content: string) => void;
  /** Callback when plus button (action attachment) is clicked */
  onPlusClick?: () => void;
  /** Callback when microphone button is clicked */
  onMicClick?: () => void;
  /** Current placeholder text */
  placeholder?: string;
  /** Disabled state */
  disabled?: boolean;
}

/**
 * Message input component for Voxara AI.
 * Provides accessible text input, attachment/plus trigger, voice trigger, and submission control.
 */
export const MessageInput: React.FC<MessageInputProps> = ({
  onSubmit,
  onPlusClick,
  onMicClick,
  placeholder = 'Ask anything or type a prompt...',
  disabled = false,
}) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || disabled) return;

    if (onSubmit) {
      onSubmit(trimmed);
    }
    setQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-xl mx-auto"
      role="search"
      aria-label="Assistant message input"
    >
      <div className="relative flex items-center bg-white/90 backdrop-blur-md rounded-full border border-neutral-200/90 shadow-[0_4px_24px_rgba(0,0,0,0.06)] hover:border-neutral-300 focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-200/50 transition-all px-2.5 py-1.5 sm:px-3 sm:py-2">
        {/* Plus / Add Action Button */}
        <button
          type="button"
          onClick={onPlusClick}
          aria-label="Add attachment or action"
          className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-full text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        >
          <Plus className="w-4 h-4 sm:w-5 sm:h-5" />
        </button>

        {/* Text Input Field */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="Message Voxara"
          className="flex-1 min-w-0 bg-transparent px-3 py-1.5 text-sm sm:text-base text-neutral-800 placeholder-neutral-400 focus:outline-none font-normal"
        />

        {/* Right Action: Send Button if query exists, else Microphone Button */}
        {query.trim().length > 0 ? (
          <button
            type="submit"
            aria-label="Send message"
            className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-neutral-900 text-white hover:bg-neutral-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            <ArrowUp className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onMicClick}
            aria-label="Start voice interaction"
            className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-full text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            <Mic className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
        )}
      </div>
    </form>
  );
};
