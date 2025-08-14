import React, { useState, useEffect } from 'react';
import { Navbar as BootstrapNavbar, Nav, Button, NavDropdown } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';

const Navbar = () => {
  const { user, logout, selectedUserId, isAllUsers, switchUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoadingUsers(true);
      const data = await apiService.getUsers();
      setUsers(data);
    } catch (error) {
      console.error('Error loading users:', error);
    } finally {
      setLoadingUsers(false);
    }
  };

  const getSelectedUserDisplay = () => {
    if (isAllUsers) {
      return 'All Users';
    }
    if (selectedUserId) {
      const selectedUser = users.find(u => u.id === selectedUserId);
      return selectedUser ? selectedUser.username : 'Unknown User';
    }
    return user?.username || 'Select User';
  };

  return (
    <BootstrapNavbar bg="white" expand="lg" className="px-4 shadow-sm">
      <BootstrapNavbar.Brand href="#" className="text-primary">
        📈 Stock Portfolio
      </BootstrapNavbar.Brand>
      
      <Nav className="ms-auto align-items-center">
        {/* User Switching Dropdown */}
        <NavDropdown 
          title={`👤 ${getSelectedUserDisplay()}`} 
          id="user-dropdown"
          className="me-3"
          disabled={loadingUsers}
        >
          <NavDropdown.Item onClick={() => switchUser('all')}>
            🌐 All Users
          </NavDropdown.Item>
          <NavDropdown.Divider />
          {users.map(u => (
            <NavDropdown.Item 
              key={u.id} 
              onClick={() => switchUser(u.id.toString())}
              active={selectedUserId === u.id}
            >
              👤 {u.username}
            </NavDropdown.Item>
          ))}
        </NavDropdown>

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
            Logged in as: {user?.full_name || user?.username}
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