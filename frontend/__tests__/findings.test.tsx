import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import FindingsPage from '../app/(app)/findings/page';
import * as api from '@/lib/api';

vi.mock('@/components/TopBar', () => ({
  default: ({ title, subtitle, children }: any) => (
    <div data-testid="topbar">
      <span>{title}</span>
      <span>{subtitle}</span>
      {children}
    </div>
  ),
}));

vi.mock('@/lib/AuthContext', () => ({
  useAuthContext: () => ({
    isAuthenticated: true,
    authReady: true,
    user: { id: 1, username: 'admin', role: 'admin' },
  }),
}));

const mockFindings: api.FindingRow[] = [
  {
    id: 1,
    rule_id: 'aws_access_key',
    category: 'CREDENTIALS',
    severity: 'CRITICAL',
    confidence: 1.0,
    risk_score: 85,
    file_name: 'config.env',
    evidence_redacted: 'AKIA***EXAMPLE',
    occurrence_count: 3,
    status: 'OPEN',
    created_at: '2026-10-16T08:00:00Z',
    last_seen_at: '2026-10-16T08:30:00Z',
  },
  {
    id: 2,
    rule_id: 'pan_card',
    category: 'PII',
    severity: 'HIGH',
    confidence: 1.0,
    risk_score: 70,
    file_name: 'users.csv',
    evidence_redacted: 'ABCDE***F',
    occurrence_count: 1,
    status: 'RESOLVED',
    created_at: '2026-10-16T07:00:00Z',
    last_seen_at: '2026-10-16T07:00:00Z',
  },
];

const mockStats: api.FindingStats = {
  total: 2,
  open: 1,
  acknowledged: 0,
  resolved: 1,
  false_positive: 0,
  by_severity: { CRITICAL: 1, HIGH: 1 },
  by_category: { CREDENTIALS: 1, PII: 1 },
};

describe('FindingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api, 'fetchFindings').mockResolvedValue({
      items: mockFindings,
      total: 2,
      page: 1,
      per_page: 15,
      pages: 1,
    });
    vi.spyOn(api, 'fetchFindingStats').mockResolvedValue(mockStats);
    vi.spyOn(api, 'patchFindingStatus').mockResolvedValue({
      ...mockFindings[0],
      status: 'ACKNOWLEDGED',
    });
  });

  it('renders KPI summary cards and table headers', async () => {
    render(<FindingsPage />);

    expect(screen.getByText('DLP Findings')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Total Findings')).toBeInTheDocument();
      expect(screen.getByText('Open Issues')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });

    // Verify findings row data
    expect(screen.getByText('aws_access_key')).toBeInTheDocument();
    expect(screen.getByText('AKIA***EXAMPLE')).toBeInTheDocument();
    expect(screen.getByText('config.env')).toBeInTheDocument();
  });

  it('calls patchFindingStatus when status is changed', async () => {
    render(<FindingsPage />);

    await waitFor(() => {
      expect(screen.getByText('aws_access_key')).toBeInTheDocument();
    });

    const selects = screen.getAllByRole('combobox');
    // First 3 selects are toolbar filters (Severity, Status, Category), remaining are row status dropdowns
    const rowStatusSelect = selects[3];
    fireEvent.change(rowStatusSelect, { target: { value: 'ACKNOWLEDGED' } });

    await waitFor(() => {
      expect(api.patchFindingStatus).toHaveBeenCalledWith(1, 'ACKNOWLEDGED');
    });
  });

  it('opens details drawer when details button is clicked', async () => {
    render(<FindingsPage />);

    await waitFor(() => {
      expect(screen.getByText('aws_access_key')).toBeInTheDocument();
    });

    const detailsButtons = screen.getAllByText('Details');
    fireEvent.click(detailsButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Finding #1')).toBeInTheDocument();
      expect(screen.getByText('Redacted Evidence (Non-Plaintext)')).toBeInTheDocument();
    });
  });
});
