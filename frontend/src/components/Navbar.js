import React from 'react';
import { Navbar as BootstrapNavbar, Nav, Button } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';

const Navbar = ({ onToggleSidebar }) => {
  const { user, logout } = useAuth();

  return (
    <BootstrapNavbar bg="white" expand="lg" className="px-3 px-md-4 shadow-sm">
      <Button
        variant="outline-dark"
        className="hamburger-btn me-2 d-md-none"
        onClick={onToggleSidebar}
        aria-label="Toggle menu"
      >
        <span style={{ fontSize: '1.25rem' }}>&#9776;</span>
      </Button>
      <BootstrapNavbar.Brand href="#" className="text-primary">
        📈 <span className="d-none d-sm-inline">Stock Portfolio</span><span className="d-sm-none">Portfolio</span>
      </BootstrapNavbar.Brand>

      <Nav className="ms-auto align-items-center">
        <div className="me-2 me-md-3 d-flex align-items-center">
          {user?.picture_url && (
            <img
              src={user.picture_url}
              alt="Profile"
              className="rounded-circle me-2"
              width="32"
              height="32"
            />
          )}
          <span className="text-primary d-none d-sm-inline">
            Logged in as: {user?.full_name || user?.username}
          </span>
          <span className="text-primary d-sm-none" style={{ fontSize: '0.85rem' }}>
            {user?.full_name || user?.username}
          </span>
        </div>

        <Button variant="outline-danger" size="sm" className="d-md-none" onClick={logout}>
          Logout
        </Button>
        <Button variant="outline-danger" className="d-none d-md-inline-block" onClick={logout}>
          Logout
        </Button>
      </Nav>
    </BootstrapNavbar>
  );
};

export default Navbar;