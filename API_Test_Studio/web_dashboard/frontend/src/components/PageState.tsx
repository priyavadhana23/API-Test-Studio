// Handles loading spinner, error alert, and empty state consistently across every page.
import { Box, CircularProgress, Typography, Alert, Button, LinearProgress } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import InboxIcon from '@mui/icons-material/Inbox';

interface Props {
  loading?: boolean;
  /** Optional label shown below the spinner when loading */
  loadingMessage?: string;
  error?: string | null;
  empty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
}

export default function PageState({ loading, loadingMessage, error, empty, emptyMessage, onRetry }: Props) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', py: 10, gap: 2 }}>
        <CircularProgress size={48} thickness={3} />
        {loadingMessage && (
          <Typography variant="body2" color="text.secondary">{loadingMessage}</Typography>
        )}
        <LinearProgress sx={{ width: 200, borderRadius: 2, opacity: 0.4 }} />
      </Box>
    );
  }
  if (error) {
    return (
      <Alert
        severity="error"
        sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}
        action={onRetry && <Button color="inherit" size="small" onClick={onRetry}>Retry</Button>}
      >
        {error}
      </Alert>
    );
  }
  if (empty) {
    // Show the upload call-to-action icon when there are no runs yet
    const isNoRuns = (emptyMessage ?? '').toLowerCase().includes('upload') ||
                     (emptyMessage ?? '').toLowerCase().includes('execution');
    return (
      <Box sx={{ textAlign: 'center', py: 10, color: 'text.secondary' }}>
        {isNoRuns
          ? <CloudUploadIcon sx={{ fontSize: 64, mb: 2, opacity: 0.25 }} />
          : <InboxIcon sx={{ fontSize: 56, mb: 1, opacity: 0.3 }} />}
        <Typography variant="body1" fontWeight={500} gutterBottom>
          {emptyMessage ?? 'No data available.'}
        </Typography>
        {isNoRuns && (
          <Typography variant="body2" color="text.disabled" sx={{ maxWidth: 420, mx: 'auto' }}>
            Upload an OpenAPI or Swagger specification to begin automated testing.
          </Typography>
        )}
      </Box>
    );
  }
  return null;
}
