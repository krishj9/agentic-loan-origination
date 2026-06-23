/**
 * Card component for content grouping.
 */

import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
}

export function Card({ children, title, className = '' }: CardProps) {
  return (
    <div className={`card ${className}`}>
      {title && <div className="card__header"><h3 className="card__title">{title}</h3></div>}
      <div className="card__content">{children}</div>
    </div>
  );
}
