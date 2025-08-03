import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Alert, Badge } from 'react-bootstrap';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: ''
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await apiService.getUsers();
      setUsers(data);
    } catch (error) {
      toast.error('Error loading users');
      console.error('Error loading users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUser.username || !newUser.email || !newUser.password) {
      toast.error('Please fill in all fields');
      return;
    }

    setCreating(true);
    try {
      await apiService.createUser(newUser);
      toast.success('User created successfully!');
      setShowCreateModal(false);
      setNewUser({ username: '', email: '', password: '' });
      loadUsers();
    } catch (error) {
      toast.error('Error creating user: ' + (error.response?.data?.detail || error.message));
      console.error('Error creating user:', error);
    } finally {
      setCreating(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2>👥 Manage Users</h2>
        <Button variant="primary" onClick={() => setShowCreateModal(true)}>
          Create New User
        </Button>
      </div>

      <Card>
        <Card.Header>
          <h5>System Users ({users.length})</h5>
        </Card.Header>
        <Card.Body>
          <Alert variant="info">
            <strong>User Management:</strong> Create and manage users who can access the stock portfolio system. 
            Each user will have their own separate portfolio and transaction data.
          </Alert>

          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>
                      <strong>{user.username}</strong>
                    </td>
                    <td>{user.email}</td>
                    <td>
                      <Badge bg={user.is_active ? 'success' : 'danger'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td>{formatDate(user.created_at)}</td>
                    <td>
                      <Button 
                        variant="outline-primary" 
                        size="sm"
                        onClick={() => toast.info('User management features coming soon!')}
                      >
                        Manage
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {users.length === 0 && (
            <p className="text-center text-muted mt-3">No users found</p>
          )}
        </Card.Body>
      </Card>

      {/* User Statistics */}
      <Card className="mt-4">
        <Card.Header>
          <h5>User Statistics</h5>
        </Card.Header>
        <Card.Body>
          <div className="row text-center">
            <div className="col-md-3">
              <div className="card bg-primary text-white">
                <div className="card-body">
                  <h3>{users.length}</h3>
                  <p>Total Users</p>
                </div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="card bg-success text-white">
                <div className="card-body">
                  <h3>{users.filter(u => u.is_active).length}</h3>
                  <p>Active Users</p>
                </div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="card bg-warning text-white">
                <div className="card-body">
                  <h3>{users.filter(u => !u.is_active).length}</h3>
                  <p>Inactive Users</p>
                </div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="card bg-info text-white">
                <div className="card-body">
                  <h3>{users.filter(u => new Date(u.created_at) > new Date(Date.now() - 7*24*60*60*1000)).length}</h3>
                  <p>New This Week</p>
                </div>
              </div>
            </div>
          </div>
        </Card.Body>
      </Card>

      {/* Create User Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Create New User</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Username *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter username"
                value={newUser.username}
                onChange={(e) => setNewUser({...newUser, username: e.target.value})}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Email *</Form.Label>
              <Form.Control
                type="email"
                placeholder="Enter email address"
                value={newUser.email}
                onChange={(e) => setNewUser({...newUser, email: e.target.value})}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Password *</Form.Label>
              <Form.Control
                type="password"
                placeholder="Enter password"
                value={newUser.password}
                onChange={(e) => setNewUser({...newUser, password: e.target.value})}
              />
            </Form.Group>

            <Alert variant="info">
              <small>
                The new user will be able to log in immediately after creation and will have their own separate portfolio data.
              </small>
            </Alert>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleCreateUser}
            disabled={creating}
          >
            {creating ? 'Creating...' : 'Create User'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default Users;