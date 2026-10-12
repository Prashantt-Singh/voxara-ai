import { motion, useReducedMotion } from 'framer-motion';
import type { Transition } from 'framer-motion';
import type { AssistantState } from '../../types/assistant';

interface AssistantOrbProps {
  /** Current visual state of the assistant */
  state: AssistantState;
  /** Optional custom CSS classes for sizing or positioning */
  className?: string;
  /** Accessible label */
  ariaLabel?: string;
}

/**
 * Animated visual representation of Voxara AI.
 *
 * Inspired by tactile, luminous organic gradients.
 * Uses Framer Motion for organic scaling, pulsing, and rotational drift,
 * with graceful fallbacks when prefers-reduced-motion is active.
 */
export const AssistantOrb: React.FC<AssistantOrbProps> = ({
  state,
  className = '',
  ariaLabel,
}) => {
  const shouldReduceMotion = useReducedMotion();

  // Dynamic animation configurations keyed by state
  const getAnimationVariants = (): { animate: Record<string, number | number[]>; transition: Transition } => {
    if (shouldReduceMotion) {
      return {
        animate: { scale: 1, rotate: 0 },
        transition: { duration: 0.1 },
      };
    }

    switch (state) {
      case 'listening':
        return {
          animate: {
            scale: [1, 1.06, 0.98, 1.04, 1],
            rotate: [0, 4, -4, 2, 0],
          },
          transition: {
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        };
      case 'thinking':
        return {
          animate: {
            scale: [1, 0.95, 1.03, 0.97, 1],
            rotate: [0, 180, 360],
          },
          transition: {
            duration: 5,
            repeat: Infinity,
            ease: 'linear',
          },
        };
      case 'executing':
        return {
          animate: {
            scale: [1, 1.04, 1, 1.04, 1],
            rotate: [0, -10, 10, -5, 0],
          },
          transition: {
            duration: 2.2,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        };
      case 'speaking':
        return {
          animate: {
            scale: [1, 1.08, 0.96, 1.07, 1],
            rotate: [0, 3, -2, 4, 0],
          },
          transition: {
            duration: 1.8,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        };
      case 'error':
        return {
          animate: {
            scale: [1, 0.98, 1.01, 1],
            x: [0, -3, 3, -2, 2, 0],
          },
          transition: {
            duration: 0.8,
            repeat: 2,
            ease: 'easeInOut',
          },
        };
      case 'idle':
      default:
        return {
          animate: {
            scale: [1, 1.025, 1],
            rotate: [0, 2, -2, 0],
          },
          transition: {
            duration: 5,
            repeat: Infinity,
            ease: 'easeInOut',
          },
        };
    }
  };

  // Color gradient definitions per state
  const getGradients = () => {
    switch (state) {
      case 'error':
        return {
          outerGlow: 'radial-gradient(circle, rgba(239, 68, 68, 0.35) 0%, rgba(248, 113, 113, 0) 70%)',
          coreGradient: 'linear-gradient(135deg, #FF6B6B 0%, #F87171 28%, #EF4444 65%, #DC2626 100%)',
          swirlColor: 'radial-gradient(circle at 35% 35%, #FCA5A5 0%, #EF4444 45%, #991B1B 95%)',
        };
      case 'thinking':
        return {
          outerGlow: 'radial-gradient(circle, rgba(249, 115, 22, 0.35) 0%, rgba(251, 146, 60, 0) 70%)',
          coreGradient: 'linear-gradient(135deg, #FFE169 0%, #FFB020 30%, #F97316 65%, #C2410C 100%)',
          swirlColor: 'radial-gradient(circle at 40% 30%, #FEF08A 0%, #F59E0B 50%, #EA580C 100%)',
        };
      case 'listening':
        return {
          outerGlow: 'radial-gradient(circle, rgba(250, 204, 21, 0.45) 0%, rgba(234, 179, 8, 0) 70%)',
          coreGradient: 'linear-gradient(135deg, #FEF08A 0%, #FACC15 35%, #FB923C 75%, #F97316 100%)',
          swirlColor: 'radial-gradient(circle at 30% 25%, #FEF9C3 0%, #FACC15 45%, #F97316 95%)',
        };
      case 'executing':
        return {
          outerGlow: 'radial-gradient(circle, rgba(251, 146, 60, 0.4) 0%, rgba(249, 115, 22, 0) 70%)',
          coreGradient: 'linear-gradient(140deg, #FDE047 0%, #FB923C 40%, #EA580C 80%, #C2410C 100%)',
          swirlColor: 'radial-gradient(circle at 45% 35%, #FEF08A 0%, #FB923C 55%, #EA580C 100%)',
        };
      case 'speaking':
        return {
          outerGlow: 'radial-gradient(circle, rgba(251, 191, 36, 0.45) 0%, rgba(245, 158, 11, 0) 70%)',
          coreGradient: 'linear-gradient(130deg, #FEF08A 0%, #FDE047 25%, #F59E0B 60%, #EA580C 100%)',
          swirlColor: 'radial-gradient(circle at 35% 30%, #FFFBEB 0%, #FBBF24 50%, #D97706 95%)',
        };
      case 'idle':
      default:
        // Faithful reproduction of the reference image: rich golden yellow with deep warm amber-orange sweep
        return {
          outerGlow: 'radial-gradient(circle, rgba(251, 191, 36, 0.3) 0%, rgba(245, 158, 11, 0) 70%)',
          coreGradient: 'linear-gradient(135deg, #FEF08A 0%, #FDE047 22%, #F59E0B 55%, #EA580C 88%, #C2410C 100%)',
          swirlColor: 'radial-gradient(circle at 32% 28%, #FFFBEB 0%, #FDE047 30%, #F59E0B 65%, #D97706 95%)',
        };
    }
  };

  const anim = getAnimationVariants();
  const gradients = getGradients();

  return (
    <div
      role="img"
      aria-label={ariaLabel || `Voxara Assistant status: ${state}`}
      className={`relative flex items-center justify-center select-none ${className}`}
    >
      {/* Outer ambient soft glow */}
      <motion.div
        className="absolute inset-[-18%] rounded-full pointer-events-none filter blur-2xl opacity-75"
        style={{ background: gradients.outerGlow }}
        animate={
          shouldReduceMotion
            ? {}
            : {
                scale: [1, 1.08, 1],
                opacity: state === 'listening' || state === 'speaking' ? [0.6, 0.9, 0.6] : [0.5, 0.7, 0.5],
              }
        }
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Main Orb Sphere */}
      <motion.div
        className="relative w-56 h-56 sm:w-64 sm:h-64 md:w-72 md:h-72 rounded-full shadow-[0_20px_50px_rgba(245,158,11,0.25)] overflow-hidden"
        style={{
          background: gradients.coreGradient,
        }}
        animate={anim.animate}
        transition={anim.transition}
      >
        {/* Internal organic illumination layer (creating the warm radial depth from the reference image) */}
        <div
          className="absolute inset-0 rounded-full mix-blend-screen opacity-90 filter blur-sm"
          style={{ background: gradients.swirlColor }}
        />

        {/* Diagonal soft lighting crease/shimmer inspired by reference image */}
        <motion.div
          className="absolute -inset-1/2 rounded-full opacity-65 mix-blend-overlay filter blur-md"
          style={{
            background:
              'radial-gradient(ellipse at 45% 45%, rgba(255, 255, 255, 0.85) 0%, rgba(254, 240, 138, 0.4) 35%, transparent 70%)',
          }}
          animate={
            shouldReduceMotion
              ? {}
              : {
                  rotate: [0, 15, -15, 0],
                  scale: [1, 1.05, 0.95, 1],
                }
          }
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Gentle specular rim highlight */}
        <div className="absolute inset-0 rounded-full border border-white/20 shadow-inner pointer-events-none" />
      </motion.div>
    </div>
  );
};
