import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, TextField, InputAdornment, MenuItem, Select,
  FormControl, InputLabel, Stack, Chip, Tooltip, IconButton,
} from '@mui/material';
import { DataGrid, type GridColDef, type GridRenderCellParams } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PageState from '../components/PageState';
import StatusChip from '../components/StatusChip';
import { useAsync } from '../hooks/useAsync';
import runsService from '../services/runsService';
import type { RunSummary } from '../types/api';

function fmt(ts: string | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}

export default function RunsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'pass' | 'fail'>('all');

  const { data, loading, error, refetch } = useAsync(
    () => runsService.listRuns({ page: 1, page_size: 100 }),
    [],
  );

  const filtered = (data?.runs ?? []).filter((r) => {
    const matchSearch =
      !search ||
      r.api_name.toLowerCase().includes(search.toLowerCase()) ||
      r.run_id.toLowerCase().includes(search.toLowerCase()) ||
      (r.environment ?? '').toLowerCase().includes(search.toLowerCase());
    const matchStatus =
      statusFilter === 'all' ||
      (statusFilter === 'pass' && r.pass_percentage >= 80) ||
      (statusFilter === 'fail' && r.pass_percentage < 80);
    return matchSearch && matchStatus;
  });

  const columns: GridColDef<RunSummary>[] = [
    {
      field: 'run_id',
      headerName: 'Run ID',
      width: 170,
      renderCell: ({ value }: GridRenderCellParams<RunSummary, string>) => (
        <Tooltip title={value}>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
            {(value ?? '').slice(0, 13)}…
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'api_name',
      headerName: 'API Name',
      flex: 1,
      minWidth: 160,
    },
    {
      field: 'environment',
      headerName: 'Environment',
      width: 130,
      renderCell: ({ value }: GridRenderCellParams<RunSummary, string | null>) =>
        value ? <Chip label={value} size="small" variant="outlined" /> : <span>—</span>,
    },
    {
      field: 'execution_timestamp',
      headerName: 'Date',
      width: 160,
      renderCell: ({ value }: GridRenderCellParams<RunSummary, string | null>) => (
        <span>{fmt(value ?? null)}</span>
      ),
    },
    {
      field: 'total_executed',
      headerName: 'Tests',
      width: 80,
      type: 'number',
    },
    {
      field: 'pass_percentage',
      headerName: 'Pass %',
      width: 110,
      renderCell: ({ value }: GridRenderCellParams<RunSummary, number>) => (
        <StatusChip value={value} />
      ),
    },
    {
      field: 'health_score',
      headerName: 'Health',
      width: 110,
      renderCell: ({ value }: GridRenderCellParams<RunSummary, number | null>) =>
        value != null
          ? <StatusChip value={value} label={value.toFixed(0)} />
          : <span>—</span>,
    },
    {
      field: 'avg_response_time_ms',
      headerName: 'Avg RT (ms)',
      width: 120,
      type: 'number',
      renderCell: ({ value }: GridRenderCellParams<RunSummary, number | null>) => (
        <span>{value != null ? value.toFixed(0) : '—'}</span>
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      renderCell: ({ row }: GridRenderCellParams<RunSummary>) => (
        <Tooltip title="View Details">
          <IconButton size="small" onClick={() => navigate(`/runs/${row.run_id}`)}>
            <OpenInNewIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Runs</Typography>

      {/* Filters */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2.5 }}>
        <TextField
          size="small"
          placeholder="Search by API name, run ID or environment…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ flex: 1, maxWidth: 440 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" color="action" />
              </InputAdornment>
            ),
          }}
        />
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="pass">Pass ≥ 80%</MenuItem>
            <MenuItem value="fail">Pass &lt; 80%</MenuItem>
          </Select>
        </FormControl>
        <Typography variant="body2" color="text.secondary" sx={{ alignSelf: 'center' }}>
          {filtered.length} run{filtered.length !== 1 ? 's' : ''}
        </Typography>
      </Stack>

      {loading || error ? (
        <PageState loading={loading} error={error} onRetry={refetch} />
      ) : (
        <DataGrid
          rows={filtered}
          columns={columns}
          getRowId={(r) => r.run_id}
          pageSizeOptions={[20, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 20 } } }}
          onRowClick={({ row }) => navigate(`/runs/${row.run_id}`)}
          sx={{
            bgcolor: 'background.paper',
            border: '1px solid #e8eaed',
            borderRadius: 2,
            '& .MuiDataGrid-row': { cursor: 'pointer' },
            '& .MuiDataGrid-columnHeaders': { bgcolor: '#f8f9fa' },
          }}
          disableRowSelectionOnClick
          autoHeight
        />
      )}
    </Box>
  );
}
