// Reusable ⓘ tooltip for metric explanations.
import { Tooltip, IconButton } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

interface Props {
  text: string;
  size?: 'small' | 'inherit';
}

export default function MetricTooltip({ text, size = 'small' }: Props) {
  return (
    <Tooltip title={text} placement="top" arrow>
      <IconButton
        size="small"
        disableRipple
        sx={{
          p: 0,
          ml: 0.5,
          verticalAlign: 'middle',
          color: 'text.disabled',
          '&:hover': { color: 'text.secondary' },
        }}
        aria-label="More information"
      >
        <InfoOutlinedIcon sx={{ fontSize: size === 'small' ? 14 : 16 }} />
      </IconButton>
    </Tooltip>
  );
}
