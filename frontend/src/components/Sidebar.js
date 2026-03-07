import React from 'react';
import { Nav } from 'react-bootstrap';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const baseMenuItems = [
    { path: '/dashboard', icon: '📊', label: 'Dashboard' },
    { path: '/transactions', icon: '📋', label: 'Transactions' },
    { path: '/upload', icon: '📤', label: 'Upload Contract Notes' },
    { path: '/manual-entry', icon: '✏️', label: 'Manual Entry' },
    { path: '/lots', icon: '📦', label: 'Lot View' },
    { path: '/capital-gains', icon: '💰', label: 'Capital Gains' }
  ];

  const adminMenuItems = [
    { path: '/corporate-events', icon: '📢', label: 'Corporate Events', adminOnly: true },
    { path: '/security-master', icon: '🔐', label: 'Security Master', adminOnly: true },
    { path: '/users', icon: '👥', label: 'Manage Users', adminOnly: true },
    { path: '/price-providers', icon: '🌐', label: 'Price Providers', adminOnly: true },
    { path: '/admin', icon: '⚙️', label: 'Admin', adminOnly: true }
  ];

  const menuItems = [
    ...baseMenuItems,
    ...(isAdmin ? adminMenuItems : [])
  ];

  return (
    <div className="sidebar bg-dark text-white" style={{ width: '250px' }}>
      <div className="p-3">
        <h5 className="text-center mb-4">Menu</h5>
        <Nav className="flex-column">
          {menuItems.map((item) => (
            <Nav.Link
              key={item.path}
              className={`text-white mb-2 rounded ${
                location.pathname === item.path ? 'bg-primary' : ''
              } ${item.adminOnly ? 'admin-item' : ''}`}
              onClick={() => navigate(item.path)}
              style={{ 
                cursor: 'pointer',
                ...(item.adminOnly ? { 
                  borderLeft: '3px solid #ffc107',
                  paddingLeft: '12px'
                } : {})
              }}
              title={item.adminOnly ? 'Admin Only' : ''}
            >
              <span className="me-2">{item.icon}</span>
              {item.label}
              {item.adminOnly && <span className="ms-2 text-warning" style={{ fontSize: '0.8em' }}>👑</span>}
            </Nav.Link>
          ))}
        </Nav>
      </div>
    </div>
  );
};

export default Sidebar;