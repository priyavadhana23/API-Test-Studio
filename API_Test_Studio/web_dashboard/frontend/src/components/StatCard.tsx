import { Card, CardContent, Typography, Box, Skeleton } from '@mui/material';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  value: string | number | null | undefined;
  subtitle?: string;
  icon?: ReactNode;
  color?: string;
  loading?: boolean;
}

export default function StatCard({ title, value, subtitle, icon, color = '#1a73e8', loading }: Props) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: 2.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={80} height={40} sx={{ mt: 0.5 }} />
            ) : (
              <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color }}>
                {value ?? '—'}
              </Typography>
            )}
            {subtitle && (
              <Typography variant="caption" color="text.secondary">{subtitle}</Typography>
            )}
          </Box>
          {icon && (
            <Box sx={{
              width: 44, height: 44, borderRadius: 2,
              bgcolor: color + '18',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color,
            }}>
              {icon}
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
