// src/services/analyticsService.ts
import apiClient from './apiClient';
import type { AnalyticsSummary } from '../types/api';

const analyticsService = {
  /** GET /api/analytics — analytics for the most recent run */
  getLatest: async (): Promise<AnalyticsSummary> => {
    const { data } = await apiClient.get<AnalyticsSummary>('/api/analytics');
    return data;
  },

  /** GET /api/analytics/{run_id} — analytics for a specific run */
  getForRun: async (runId: string): Promise<AnalyticsSummary> => {
    const { data } = await apiClient.get<AnalyticsSummary>(`/api/analytics/${runId}`);
    return data;
  },
};

export default analyticsService;
