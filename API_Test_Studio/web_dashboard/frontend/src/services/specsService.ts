// src/services/specsService.ts
// Handles spec upload and listing. Uses the shared apiClient — no new Axios instances.
import apiClient from './apiClient';
import type { UploadResponse, SpecListResponse } from '../types/upload';

const specsService = {
  /**
   * POST /api/specifications/upload
   * Sends the file as multipart/form-data with field name 'file'.
   * Reports upload progress via the onProgress callback (0–100).
   */
  upload: async (
    file: File,
    onProgress?: (pct: number) => void,
  ): Promise<UploadResponse> => {
    const form = new FormData();
    form.append('file', file);

    const { data } = await apiClient.post<UploadResponse>(
      '/api/specifications/upload',
      form,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (onProgress && evt.total) {
            onProgress(Math.round((evt.loaded / evt.total) * 100));
          }
        },
      },
    );
    return data;
  },

  /** GET /api/specifications — list all uploaded spec files */
  list: async (): Promise<SpecListResponse> => {
    const { data } = await apiClient.get<SpecListResponse>('/api/specifications');
    return data;
  },
};

export default specsService;
