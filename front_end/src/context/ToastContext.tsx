import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Toast, ToastVariant } from '@/types';

interface ToastContextValue {
  toasts: Toast[];
  showToast: (title: string, variant?: ToastVariant, message?: string) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (title: string, variant: ToastVariant = 'info', message?: string) => {
      const id = `toast-${++toastCounter}`;
      const toast: Toast = { id, title, variant, message };
      setToasts((prev) => [...prev, toast]);
      setTimeout(() => dismissToast(id), 5000);
    },
    [dismissToast],
  );

  const value = useMemo(() => ({ toasts, showToast, dismissToast }), [toasts, showToast, dismissToast]);

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
