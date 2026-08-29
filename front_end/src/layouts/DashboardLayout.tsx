import { useState, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FilePlus2,
  Activity,
  Library,
  ClipboardCheck,
  Database,
  HeartPulse,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  FileText,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/new', label: 'New Proposal', icon: FilePlus2 },
  { to: '/jobs', label: 'Active Jobs', icon: Activity },
  { to: '/library', label: 'Proposal Library', icon: Library },
  { to: '/evaluations', label: 'Evaluations', icon: ClipboardCheck },
  { to: '/knowledge', label: 'Knowledge Base', icon: Database },
  { to: '/health', label: 'System Health', icon: HeartPulse },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const pageTitle =
    NAV_ITEMS.find((n) => n.to === location.pathname)?.label ||
    (location.pathname.startsWith('/jobs/') ? 'Job Workspace' : 'RFP Platform');

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex flex-col border-r border-navy-800 bg-navy-950 transition-all duration-300 ${
          collapsed ? 'w-16' : 'w-60'
        }`}
        style={{ backgroundColor: 'var(--navy-950)' }}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 px-3">
          {!collapsed && (
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500">
                <FileText className="h-4 w-4 text-white" />
              </div>
              <span className="whitespace-nowrap text-sm font-bold text-white">RFP Responder</span>
            </div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto py-3" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg mx-2 px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-teal-500/15 text-teal-300'
                      : 'text-slate-400 hover:bg-white/5 hover:text-white'
                  } ${collapsed ? 'justify-center' : ''}`
                }
                title={collapsed ? item.label : undefined}
              >
                <Icon className="h-4.5 w-4.5 shrink-0" style={{ width: '18px', height: '18px' }} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {!collapsed && (
          <div className="border-t border-white/10 p-3">
            <p className="text-xs text-slate-500">AI Procurement Platform</p>
            <p className="text-xs text-slate-600 mt-0.5">v1.0.0</p>
          </div>
        )}
      </aside>

      {/* Main content area */}
      <div className={`flex flex-1 flex-col transition-all duration-300 ${collapsed ? 'ml-16' : 'ml-60'}`}>
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/80 px-5 backdrop-blur-sm">
          <h1 className="text-base font-semibold text-slate-800">{pageTitle}</h1>
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-500">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft" />
              Connected
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
              U
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-5 sm:p-6">
          <div className="mx-auto max-w-7xl animate-fade-in">{children}</div>
        </main>
      </div>
    </div>
  );
}
