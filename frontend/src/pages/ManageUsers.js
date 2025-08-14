import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Alert, Badge } from 'react-bootstrap';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';
import { useAuth } from '../context/AuthContext';

const ManageUsers = () => {
  const { user, isAdmin } = useAuth();
  const [adminUsers, setAdminUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRemoveModal, setShowRemoveModal] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState('');
  const [newAdminEmail, setNewAdminEmail] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isAdmin) {
      loadAdminUsers();
    } else {
      setLoading(false);
    }
  }, [isAdmin]);

  const loadAdminUsers = async () => {
    try {
      setLoading(true);
      const data = await apiService.getAdminUsers();
      setAdminUsers(data.admin_users || []);
    } catch (error) {
      toast.error('Error loading admin users');
      console.error('Error loading admin users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddAdmin = async () => {
    if (!newAdminEmail || !newAdminEmail.includes('@')) {
      toast.error('Please enter a valid email address');
      return;
    }

    setSaving(true);
    try {
      const result = await apiService.addAdminUser(newAdminEmail);
      if (result.success) {
        toast.success(result.message);
        setNewAdminEmail('');
        setShowAddModal(false);
        loadAdminUsers();
      } else {
        toast.warning(result.message);
      }
    } catch (error) {
      toast.error('Error adding admin user: ' + (error.response?.data?.detail || error.message));
      console.error('Error adding admin user:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveAdmin = async () => {
    if (!selectedEmail) return;

    setSaving(true);
    try {
      const result = await apiService.removeAdminUser(selectedEmail);
      toast.success(result.message);
      setShowRemoveModal(false);
      setSelectedEmail('');
      loadAdminUsers();
    } catch (error) {
      toast.error('Error removing admin user: ' + (error.response?.data?.detail || error.message));
      console.error('Error removing admin user:', error);
    } finally {
      setSaving(false);
    }
  };

  const openRemoveModal = (email) => {
    setSelectedEmail(email);
    setShowRemoveModal(true);
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

  if (!isAdmin) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <Alert variant="danger" className="text-center">
          <Alert.Heading>🔒 Access Denied</Alert.Heading>
          <p>
            You do not have admin privileges to manage users.
            <br />
            Please contact an administrator if you need access.
          </p>
          <hr />
          <p className="mb-0">
            <strong>Current user:</strong> {user?.email || user?.username || 'Unknown'}
          </p>
        </Alert>
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2>👥 Manage Users</h2>
        <Button variant="primary" onClick={() => setShowAddModal(true)}>
          Add Admin User
        </Button>
      </div>

      <Card>
        <Card.Header>
          <h5>Admin Users ({adminUsers.length})</h5>
        </Card.Header>
        <Card.Body>
          <Alert variant="info">
            <strong>Admin User Management:</strong> Control who has access to administrative features like Security Master, User Management, and Admin panel.
            <br />
            <strong>⚠️ Warning:</strong> Be careful when removing admin users. Ensure at least one admin user remains.
          </Alert>

          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Email Address</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {adminUsers.map((email, index) => (
                  <tr key={email}>
                    <td>
                      <Badge bg="secondary">{index + 1}</Badge>
                    </td>
                    <td>
                      <strong>{email}</strong>
                      {user?.email === email && (
                        <span className="ms-2">
                          <Badge bg="success">You</Badge>
                        </span>
                      )}
                    </td>
                    <td>
                      <Badge bg="success">Active Admin</Badge>
                    </td>
                    <td>
                      <Button 
                        variant="outline-danger" 
                        size="sm"
                        onClick={() => openRemoveModal(email)}
                        disabled={adminUsers.length === 1}
                        title={adminUsers.length === 1 ? "Cannot remove the last admin user" : "Remove admin access"}
                      >
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {adminUsers.length === 0 && (
            <p className="text-center text-muted mt-3">
              No admin users found
            </p>
          )}
        </Card.Body>
      </Card>

      {/* Admin Statistics */}
      <Card className="mt-4">
        <Card.Header>
          <h5>Admin Statistics</h5>
        </Card.Header>
        <Card.Body>
          <div className="row text-center">
            <div className="col-md-4">
              <div className="card bg-primary text-white">
                <div className="card-body">
                  <h3>{adminUsers.length}</h3>
                  <p>Total Admin Users</p>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-success text-white">
                <div className="card-body">
                  <h3>{adminUsers.filter(email => email === user?.email).length}</h3>
                  <p>You Are Admin</p>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-info text-white">
                <div className="card-body">
                  <h3>{adminUsers.length > 1 ? adminUsers.length - 1 : 0}</h3>
                  <p>Other Admins</p>
                </div>
              </div>
            </div>
          </div>
        </Card.Body>
      </Card>

      {/* Add Admin Modal */}
      <Modal show={showAddModal} onHide={() => setShowAddModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Add Admin User</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Email Address *</Form.Label>
              <Form.Control
                type="email"
                placeholder="Enter email address"
                value={newAdminEmail}
                onChange={(e) => setNewAdminEmail(e.target.value)}
              />
              <Form.Text className="text-muted">
                Enter the email address of the user you want to grant admin access to.
              </Form.Text>
            </Form.Group>

            <Alert variant="warning">
              <small>
                <strong>Note:</strong> The user must be registered in the system with this email address to gain admin access.
              </small>
            </Alert>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleAddAdmin}
            disabled={saving}
          >
            {saving ? 'Adding...' : 'Add Admin'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Remove Admin Confirmation Modal */}
      <Modal show={showRemoveModal} onHide={() => setShowRemoveModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>⚠️ Remove Admin Access</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger">
            <strong>Warning!</strong> This action cannot be undone.
          </Alert>
          <p>
            Are you sure you want to remove admin access for <strong>'{selectedEmail}'</strong>?
          </p>
          <p className="text-danger">
            <strong>Note:</strong> The user will lose access to all administrative features immediately.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowRemoveModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="danger" 
            onClick={handleRemoveAdmin}
            disabled={saving}
          >
            {saving ? 'Removing...' : 'Yes, Remove Admin Access'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default ManageUsers;