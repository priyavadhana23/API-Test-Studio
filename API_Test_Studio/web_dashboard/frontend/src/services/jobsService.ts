// src/services/jobsService.ts
// Async job queue — POST /api/jobs to submit, GET /api/jobs/{id} to poll.
import apiClient from './apiClient';
import type { ExecuteRequest, JobSubmitResponse, JobStatusResponse } from '../types/upload';

const jobsService = {
  /**
   * POST /api/jobs — submit a pipeline job, returns immediately with job_id.
   * Returns HTTP 202 Accepted.
   */
  submit: async (req: ExecuteRequest): Promise<JobSubmitResponse> => {
    const { data } = await apiClient.post<JobSubmitResponse>('/api/jobs', req);
    return data;
  },

  /** GET /api/jobs/{job_id} — poll current status and progress */
  getStatus: async (jobId: string): Promise<JobStatusResponse> => {
    const { data } = await apiClient.get<JobStatusResponse>(`/api/jobs/${jobId}`);
    return data;
  },
};

export default jobsService;
