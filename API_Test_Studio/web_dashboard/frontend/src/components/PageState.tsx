// Handles loading spinner, error alert, and empty state consistently across every page.
import { Box, CircularProgress, Typography, Alert, Button } from '@mui/material';
import InboxIcon from '@mui/icons-material/Inbox';

interface Props {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
}

export default function PageState({ loading, error, empty, emptyMessage, onRetry }: Props) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 10 }}>
        <CircularProgress />
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
    return (
      <Box sx={{ textAlign: 'center', py: 10, color: 'text.secondary' }}>
        <InboxIcon sx={{ fontSize: 56, mb: 1, opacity: 0.3 }} />
        <Typography variant="body1">{emptyMessage ?? 'No data available.'}</Typography>
      </Box>
    );
  }
  return null;
}
