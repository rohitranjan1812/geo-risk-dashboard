import { Loader2 } from 'lucide-react';

export function LoadingSpinner({ size = 24, text }: { size?: number; text?: string }) {
  return (
    <div className="loading-spinner">
      <Loader2 size={size} className="spin" />
      {text && <span>{text}</span>}
    </div>
  );
}
