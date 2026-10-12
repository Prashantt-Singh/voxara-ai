/**
 * Utility helper to join conditional class names safely without heavy external dependencies.
 */
export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ');
}
