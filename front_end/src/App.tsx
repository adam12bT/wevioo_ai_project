import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { wakeHostedSpaces } from '@/api/wakeSpaces';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { NewProposalPage } from '@/pages/NewProposalPage';
import { JobsListPage } from '@/pages/JobsListPage';
import { JobWorkspacePage } from '@/pages/JobWorkspacePage';
import { ProposalLibraryPage } from '@/pages/ProposalLibraryPage';
import { EvaluationsPage } from '@/pages/EvaluationsPage';
import { KnowledgeBasePage } from '@/pages/KnowledgeBasePage';
import { SystemHealthPage } from '@/pages/SystemHealthPage';
import { SettingsPage } from '@/pages/SettingsPage';

function App() {
  useEffect(() => {
    wakeHostedSpaces();
  }, []);

  return (
    <BrowserRouter>
      <DashboardLayout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/new" element={<NewProposalPage />} />
          <Route path="/jobs" element={<JobsListPage />} />
          <Route path="/jobs/:jobId" element={<JobWorkspacePage />} />
          <Route path="/library" element={<ProposalLibraryPage />} />
          <Route path="/evaluations" element={<EvaluationsPage />} />
          <Route path="/knowledge" element={<KnowledgeBasePage />} />
          <Route path="/health" element={<SystemHealthPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </DashboardLayout>
    </BrowserRouter>
  );
}

export default App;
