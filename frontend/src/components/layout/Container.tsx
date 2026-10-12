import React from 'react';

interface ContainerProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Standard responsive layout container maintaining comfortable horizontal padding and max-width.
 */
export const Container: React.FC<ContainerProps> = ({ children, className = '' }) => {
  return (
    <div className={`w-full max-w-4xl mx-auto px-4 sm:px-6 md:px-8 ${className}`}>
      {children}
    </div>
  );
};
