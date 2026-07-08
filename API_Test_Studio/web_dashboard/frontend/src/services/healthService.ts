// src/services/healthService.ts
import apiClient from './apiClient';
import type { HealthResponse } from '../types/api';

const healthService = {
  /** GET /api/health — component health probe */
  getHealth: async (): Promise<HealthResponse> => {
    const { data } = await apiClient.get<HealthResponse>('/api/health');
    return data;
  },
};

export default healthService;
