// src/services/runsService.ts
import apiClient from './apiClient';
import type { RunListResponse, RunDetailResponse, ResultsSummary } from '../types/api';

export interface ListRunsParams {
  page?: number;
  page_size?: number;
  api_name?: string;
  environment?: string;
}

const runsService = {
  /** GET /api/runs — paginated run history with optional filters */
  listRuns: async (params: ListRunsParams = {}): Promise<RunListResponse> => {
    const { data } = await apiClient.get<RunListResponse>('/api/runs', { params });
    return data;
  },

  /** GET /api/runs/{run_id} — full run detail + validation summary */
  getRun: async (runId: string): Promise<RunDetailResponse> => {
    const { data } = await apiClient.get<RunDetailResponse>(`/api/runs/${runId}`);
    return data;
  },

  /** GET /api/runs/{run_id}/results/summary — aggregated breakdown */
  getResultsSummary: async (runId: string): Promise<ResultsSummary> => {
    const { data } = await apiClient.get<ResultsSummary>(
      `/api/runs/${runId}/results/summary`,
    );
    return data;
  },
};

export default runsService;
