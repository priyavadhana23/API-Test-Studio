import { Card, CardContent, CardHeader, Divider } from '@mui/material';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  subheader?: string;
  children: ReactNode;
  action?: ReactNode;
}

export default function SectionCard({ title, subheader, children, action }: Props) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardHeader
        title={title}
        subheader={subheader}
        action={action}
        titleTypographyProps={{ variant: 'subtitle1' }}
        subheaderTypographyProps={{ variant: 'caption' }}
        sx={{ pb: 0 }}
      />
      <Divider sx={{ mt: 1 }} />
      <CardContent sx={{ pt: 2 }}>{children}</CardContent>
    </Card>
  );
}
