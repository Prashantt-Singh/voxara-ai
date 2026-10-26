import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { ShieldCheck, ArrowLeft, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';

interface OtpVerificationProps {
  email: string;
  onBackToLogin: () => void;
  onSuccess?: () => void;
  initialType?: 'signup' | 'email';
}

export const OtpVerification: React.FC<OtpVerificationProps> = ({
  email,
  onBackToLogin,
  onSuccess,
  initialType = 'signup',
}) => {
  const { verifyOtp, resendOtp } = useAuth();

  // 6 individual digit inputs
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Verification states
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifySuccess, setVerifySuccess] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isExpired, setIsExpired] = useState<boolean>(false);
  const [isInvalid, setIsInvalid] = useState<boolean>(false);

  // Resend cooldown timer (60 seconds standard for Supabase rate limit protection)
  const [resendCooldown, setResendCooldown] = useState<number>(60);
  const [isResending, setIsResending] = useState<boolean>(false);
  const [resendNotice, setResendNotice] = useState<string | null>(null);

  // Focus first input on mount
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  // Cooldown countdown effect
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const handleDigitChange = (index: number, value: string) => {
    // Only accept numeric digits
    const cleaned = value.replace(/\D/g, '');
    if (!cleaned) {
      const updated = [...digits];
      updated[index] = '';
      setDigits(updated);
      return;
    }

    // Handle single digit
    const updated = [...digits];
    updated[index] = cleaned[cleaned.length - 1]; // take the latest character
    setDigits(updated);
    setErrorMessage(null);
    setIsInvalid(false);
    setIsExpired(false);

    // Auto-advance to next input
    if (index < 5 && cleaned.length > 0) {
      inputRefs.current[index + 1]?.focus();
    }

    // If all 6 digits are filled, automatically submit
    const fullCode = updated.join('');
    if (fullCode.length === 6 && !updated.includes('')) {
      handleVerify(fullCode);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').trim().replace(/\D/g, '');
    if (!pastedData) return;

    const newDigits = [...digits];
    for (let i = 0; i < 6; i++) {
      newDigits[i] = pastedData[i] || '';
    }
    setDigits(newDigits);
    setErrorMessage(null);
    setIsInvalid(false);
    setIsExpired(false);

    // Focus appropriate field
    const nextEmptyIndex = newDigits.findIndex((d) => d === '');
    if (nextEmptyIndex !== -1) {
      inputRefs.current[nextEmptyIndex]?.focus();
    } else {
      inputRefs.current[5]?.focus();
      // Auto verify full 6 digit code
      handleVerify(newDigits.join(''));
    }
  };

  const handleVerify = async (codeToVerify?: string) => {
    const code = codeToVerify || digits.join('');
    if (code.length !== 6) {
      setErrorMessage('Please enter the complete 6-digit code.');
      setIsInvalid(true);
      return;
    }

    setIsVerifying(true);
    setErrorMessage(null);
    setIsInvalid(false);
    setIsExpired(false);

    try {
      const res = await verifyOtp(email, code, initialType);
      if (res.success) {
        setVerifySuccess(true);
        if (onSuccess) {
          setTimeout(onSuccess, 600);
        }
      } else {
        setErrorMessage(res.error || 'Verification failed.');
        setIsExpired(Boolean(res.isExpired));
        setIsInvalid(Boolean(res.isInvalid));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0 || isResending) return;

    setIsResending(true);
    setResendNotice(null);
    setErrorMessage(null);
    setIsInvalid(false);
    setIsExpired(false);

    try {
      const res = await resendOtp(email, initialType);
      if (res.success) {
        setResendNotice('A new 6-digit confirmation code has been sent to your email.');
        setResendCooldown(60); // Reset rate limit timer
      } else {
        setErrorMessage(res.error || 'Failed to resend confirmation code.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="w-full">
      {/* Back button */}
      <button
        onClick={onBackToLogin}
        className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-800 transition-colors mb-6 cursor-pointer"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to sign in</span>
      </button>

      {/* Screen Header */}
      <div className="text-center mb-6">
        <div className="mx-auto w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200/80 flex items-center justify-center mb-3 text-amber-600 shadow-2xs">
          <ShieldCheck className="w-6 h-6" />
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-neutral-900 tracking-tight">
          Verify Your Email
        </h2>
        <p className="text-xs sm:text-sm text-neutral-500 mt-1.5 max-w-xs mx-auto">
          We sent a 6-digit verification code to
          <br />
          <span className="font-semibold text-neutral-800 break-all">{email}</span>
        </p>
      </div>

      {/* Success Notification */}
      {verifySuccess && (
        <div
          role="status"
          className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs sm:text-sm flex items-center gap-3 animate-fadeIn"
        >
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="font-medium">Email confirmed successfully! Signing you into Voxara...</span>
        </div>
      )}

      {/* Error Notification */}
      {errorMessage && !verifySuccess && (
        <div
          role="alert"
          className="mb-6 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs sm:text-sm flex items-start gap-2.5 animate-fadeIn"
        >
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium">{errorMessage}</p>
            {isExpired && (
              <p className="text-[11px] text-red-700 mt-1">
                Codes expire after a short period. Click "Resend Code" below to receive a fresh OTP.
              </p>
            )}
            {isInvalid && (
              <p className="text-[11px] text-red-700 mt-1">
                Please double check the 6 digits in your inbox.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Resend Notice */}
      {resendNotice && !errorMessage && (
        <div
          role="status"
          className="mb-6 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2 animate-fadeIn"
        >
          <CheckCircle2 className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{resendNotice}</span>
        </div>
      )}

      {/* 6-Digit OTP Inputs */}
      <div className="flex items-center justify-center gap-2 sm:gap-3 mb-6">
        {digits.map((digit, idx) => (
          <input
            key={idx}
            ref={(el) => {
              inputRefs.current[idx] = el;
            }}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={1}
            value={digit}
            onChange={(e) => handleDigitChange(idx, e.target.value)}
            onKeyDown={(e) => handleKeyDown(idx, e)}
            onPaste={handlePaste}
            disabled={isVerifying || verifySuccess}
            aria-label={`Digit ${idx + 1}`}
            className={`w-11 h-13 sm:w-12 sm:h-14 text-center text-xl sm:text-2xl font-bold rounded-xl border transition-all outline-hidden ${
              verifySuccess
                ? 'border-emerald-500 bg-emerald-50/40 text-emerald-900'
                : errorMessage
                ? 'border-red-300 bg-red-50/30 text-red-900 focus:border-red-500 focus:ring-2 focus:ring-red-200'
                : 'border-neutral-200/90 bg-white text-neutral-900 focus:border-amber-500 focus:ring-2 focus:ring-amber-200'
            } shadow-2xs`}
          />
        ))}
      </div>

      {/* Verify Button */}
      <button
        onClick={() => handleVerify()}
        disabled={isVerifying || verifySuccess || digits.join('').length !== 6}
        className="w-full py-3 px-4 rounded-xl font-medium text-sm text-neutral-900 bg-amber-400 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer"
      >
        {isVerifying ? (
          <>
            <div className="w-4 h-4 border-2 border-neutral-900 border-t-transparent rounded-full animate-spin" />
            <span>Verifying code...</span>
          </>
        ) : verifySuccess ? (
          <>
            <CheckCircle2 className="w-4 h-4 text-neutral-900" />
            <span>Verified!</span>
          </>
        ) : (
          <span>Verify & Continue</span>
        )}
      </button>

      {/* Resend Code Section */}
      <div className="mt-6 text-center text-xs text-neutral-500">
        <p>Didn't receive the email code?</p>
        <button
          type="button"
          onClick={handleResend}
          disabled={resendCooldown > 0 || isResending || verifySuccess}
          className="mt-1.5 font-medium text-amber-600 hover:text-amber-700 disabled:text-neutral-400 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-1.5 cursor-pointer"
        >
          {isResending ? (
            <>
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Sending new code...</span>
            </>
          ) : resendCooldown > 0 ? (
            <span>Resend code in {resendCooldown}s</span>
          ) : (
            <>
              <RefreshCw className="w-3 h-3" />
              <span>Resend 6-digit code</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
