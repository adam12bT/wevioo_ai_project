import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import type { ToastVariant } from '@/types';

const TOAST_STYLES: Record<ToastVariant, { bg: string; icon: typeof Info; iconColor: string }> = {
  success: { bg: 'border-emerald-200', icon: CheckCircle2, iconColor: 'text-emerald-500' },
  error: { bg: 'border-rose-200', icon: AlertCircle, iconColor: 'text-rose-500' },
  warning: { bg: 'border-amber-200', icon: AlertTriangle, iconColor: 'text-amber-500' },
  info: { bg: 'border-blue-200', icon: Info, iconColor: 'text-blue-500' },
};

export function ToastContainer() {
  const { toasts, dismissToast } = useToast();

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((toast) => {
        const style = TOAST_STYLES[toast.variant];
        const Icon = style.icon;
        return (
          <div
            key={toast.id}
            className={`flex items-start gap-3 rounded-lg border bg-white p-3.5 shadow-lg animate-slide-in ${style.bg}`}
            role="alert"
          >
            <Icon className={`h-5 w-5 shrink-0 ${style.iconColor}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-800">{toast.title}</p>
              {toast.message && <p className="mt-0.5 text-xs text-slate-500">{toast.message}</p>}
            </div>
            <button
              onClick={() => dismissToast(toast.id)}
              className="shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
