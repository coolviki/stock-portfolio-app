import React from 'react';
import { Navbar as BootstrapNavbar, Nav, Button } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';

const Navbar = () => {
  const { user, logout } = useAuth();

  return (
    <BootstrapNavbar bg="white" expand="lg" className="px-4 shadow-sm">
      <BootstrapNavbar.Brand href="#" className="text-primary">
        📈 Stock Portfolio
      </BootstrapNavbar.Brand>
      
      <Nav className="ms-auto align-items-center">
        <div className="me-3 d-flex align-items-center">
          {user?.picture_url && (
            <img 
              src={user.picture_url} 
              alt="Profile" 
              className="rounded-circle me-2" 
              width="32" 
              height="32"
            />
          )}
          <span className="text-primary">
            👤 {user?.full_name || user?.username}
          </span>
        </div>
        
        <Button variant="outline-danger" onClick={logout}>
          Logout
        </Button>
      </Nav>
    </BootstrapNavbar>
  );
};

export default Navbar;