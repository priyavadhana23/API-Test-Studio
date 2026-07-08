import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  Box, Drawer, AppBar, Toolbar, Typography, List, ListItemButton,
  ListItemIcon, ListItemText, IconButton, Tooltip, Divider, useTheme,
  useMediaQuery, Chip,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PlaylistPlayIcon from '@mui/icons-material/PlaylistPlay';
import BarChartIcon from '@mui/icons-material/BarChart';
import MenuIcon from '@mui/icons-material/Menu';
import ScienceIcon from '@mui/icons-material/Science';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

const DRAWER_WIDTH = 230;

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon /> },
  { label: 'Upload',    path: '/upload',    icon: <CloudUploadIcon /> },
  { label: 'Runs',      path: '/runs',      icon: <PlaylistPlayIcon /> },
  { label: 'Analytics', path: '/analytics', icon: <BarChartIcon /> },
];

export default function MainLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo */}
      <Box sx={{ px: 2.5, py: 2.5, display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <ScienceIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="subtitle1" sx={{ lineHeight: 1.2, fontWeight: 700, color: 'text.primary' }}>
            API Test Studio
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Enterprise Testing
          </Typography>
        </Box>
      </Box>

      <Divider />

      {/* Nav items */}
      <List sx={{ px: 1, pt: 1, flex: 1 }}>
        {NAV_ITEMS.map(({ label, path, icon }) => {
          const active = location.pathname.startsWith(path);
          return (
            <ListItemButton
              key={path}
              component={NavLink}
              to={path}
              onClick={() => isMobile && setMobileOpen(false)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: active ? 'primary.main' : 'text.secondary',
                bgcolor: active ? 'primary.main' + '14' : 'transparent',
                '&:hover': { bgcolor: 'action.hover' },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: 'inherit' }}>{icon}</ListItemIcon>
              <ListItemText primary={label} primaryTypographyProps={{ fontWeight: active ? 600 : 400 }} />
            </ListItemButton>
          );
        })}
      </List>

      <Divider />
      <Box sx={{ px: 2.5, py: 1.5 }}>
        <Typography variant="caption" color="text.disabled">Phase 9.6 — Upload &amp; Execute</Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* App bar */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          zIndex: theme.zIndex.drawer + 1,
          bgcolor: 'background.paper',
          borderBottom: '1px solid #e8eaed',
          color: 'text.primary',
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
        }}
      >
        <Toolbar sx={{ gap: 1 }}>
          {isMobile && (
            <IconButton edge="start" onClick={() => setMobileOpen(true)} size="small">
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" sx={{ flex: 1, fontWeight: 600, fontSize: '1rem' }}>
            {NAV_ITEMS.find(n => location.pathname.startsWith(n.path))?.label ?? 'API Test Studio'}
          </Typography>
          <Chip label="v1.0.0" size="small" variant="outlined" color="primary" />
        </Toolbar>
      </AppBar>

      {/* Sidebar drawer */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            sx={{ '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' } }}
          >
            {drawerContent}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              '& .MuiDrawer-paper': {
                width: DRAWER_WIDTH,
                boxSizing: 'border-box',
                border: 'none',
                borderRight: '1px solid #e8eaed',
              },
            }}
            open
          >
            {drawerContent}
          </Drawer>
        )}
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          pt: { xs: 7, md: 8 },
          minHeight: 0,
        }}
      >
        <Box sx={{ flex: 1, p: { xs: 2, md: 3 } }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
