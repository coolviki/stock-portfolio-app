import React from 'react';
import { Nav } from 'react-bootstrap';
import { useLocation, useNavigate } from 'react-router-dom';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const menuItems = [
    { path: '/dashboard', icon: '📊', label: 'Dashboard' },
    { path: '/transactions', icon: '📋', label: 'Transactions' },
    { path: '/upload', icon: '📤', label: 'Upload Contract Notes' },
    { path: '/manual-entry', icon: '✏️', label: 'Manual Entry' },
    { path: '/users', icon: '👥', label: 'Manage Users' },
    { path: '/admin', icon: '⚙️', label: 'Admin' }
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
              }`}
              onClick={() => navigate(item.path)}
              style={{ cursor: 'pointer' }}
            >
              <span className="me-2">{item.icon}</span>
              {item.label}
            </Nav.Link>
          ))}
        </Nav>
      </div>
    </div>
  );
};

export default Sidebar;