import React, { useState, useEffect } from 'react';
import { Navbar as BootstrapNavbar, Nav, Dropdown, Button } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';

const Navbar = () => {
  const { user, logout, selectedUserId, switchUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [showAllUsers, setShowAllUsers] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const response = await apiService.getUsers();
      setUsers(response);
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const handleUserSwitch = (userId) => {
    if (userId === 'all') {
      setShowAllUsers(true);
      switchUser(null);
    } else {
      setShowAllUsers(false);
      switchUser(userId);
    }
  };

  const getCurrentUserName = () => {
    if (showAllUsers) return 'All Users';
    if (selectedUserId === user?.id) return user?.username;
    const selectedUser = users.find(u => u.id === selectedUserId);
    return selectedUser?.username || user?.username;
  };

  return (
    <BootstrapNavbar bg="white" expand="lg" className="px-4 shadow-sm">
      <BootstrapNavbar.Brand href="#" className="text-primary">
        📈 Stock Portfolio
      </BootstrapNavbar.Brand>
      
      <Nav className="ms-auto align-items-center">
        <Dropdown className="me-3">
          <Dropdown.Toggle variant="outline-primary" id="user-dropdown">
            👤 {getCurrentUserName()}
          </Dropdown.Toggle>
          
          <Dropdown.Menu>
            <Dropdown.Item onClick={() => handleUserSwitch(user.id)}>
              {user.username} (Me)
            </Dropdown.Item>
            <Dropdown.Divider />
            {users.filter(u => u.id !== user.id).map(u => (
              <Dropdown.Item key={u.id} onClick={() => handleUserSwitch(u.id)}>
                {u.username}
              </Dropdown.Item>
            ))}
            <Dropdown.Divider />
            <Dropdown.Item onClick={() => handleUserSwitch('all')}>
              All Users
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>
        
        <Button variant="outline-danger" onClick={logout}>
          Logout
        </Button>
      </Nav>
    </BootstrapNavbar>
  );
};

export default Navbar;