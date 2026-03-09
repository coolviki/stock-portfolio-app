import React from 'react';
import { Nav, Button } from 'react-bootstrap';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Sidebar = ({ isOpen, onClose }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const handleNavClick = (path) => {
    navigate(path);
    onClose();
  };

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
    <div className={`sidebar bg-dark text-white ${isOpen ? 'open' : ''}`} style={{ width: '250px' }}>
      <div className="p-3">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h5 className="mb-0 text-center flex-grow-1">Menu</h5>
          <Button
            variant="outline-light"
            size="sm"
            className="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close menu"
          >
            &times;
          </Button>
        </div>
        <Nav className="flex-column">
          {menuItems.map((item) => (
            <Nav.Link
              key={item.path}
              className={`text-white mb-2 rounded ${
                location.pathname === item.path ? 'bg-primary' : ''
              } ${item.adminOnly ? 'admin-item' : ''}`}
              onClick={() => handleNavClick(item.path)}
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