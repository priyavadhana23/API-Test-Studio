// src/services/apiClient.ts
// Central Axios instance. All services import from here — never from 'axios' directly.

import axios from 'axios';

const apiClient = axios.create({
  // Empty baseURL: Vite's dev proxy rewrites /api/* → http://127.0.0.1:8000/api/*
  // In production, set VITE_API_BASE_URL env var to the backend origin.
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// ── Response interceptor: normalise errors ──────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message: string =
      error.response?.data?.message ??
      error.response?.data?.detail ??
      error.message ??
      'An unexpected error occurred.';
    return Promise.reject(new Error(message));
  },
);

export default apiClient;
