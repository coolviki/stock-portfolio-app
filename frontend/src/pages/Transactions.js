import React, { useState, useEffect } from 'react';
import { 
  Row, Col, Card, Table, Button, Form, Modal, Badge, 
  InputGroup, FormControl, Dropdown 
} from 'react-bootstrap';
import DatePicker from 'react-datepicker';
import { format } from 'date-fns';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';
import 'react-datepicker/dist/react-datepicker.css';

const Transactions = () => {
  const [transactions, setTransactions] = useState([]);
  const [filteredTransactions, setFilteredTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [filters, setFilters] = useState({
    security_name: '',
    transaction_type: '',
    date_from: null,
    date_to: null
  });

  const { selectedUserId } = useAuth();

  useEffect(() => {
    loadTransactions();
  }, [selectedUserId]);

  useEffect(() => {
    applyFilters();
  }, [transactions, filters]);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await apiService.getTransactions({ 
        user_id: selectedUserId 
      });
      setTransactions(data);
    } catch (error) {
      toast.error('Error loading transactions');
      console.error('Error loading transactions:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...transactions];

    if (filters.security_name) {
      filtered = filtered.filter(t => 
        t.security_name.toLowerCase().includes(filters.security_name.toLowerCase())
      );
    }

    if (filters.transaction_type) {
      filtered = filtered.filter(t => 
        t.transaction_type === filters.transaction_type
      );
    }

    if (filters.date_from) {
      filtered = filtered.filter(t => 
        new Date(t.transaction_date) >= filters.date_from
      );
    }

    if (filters.date_to) {
      filtered = filtered.filter(t => 
        new Date(t.transaction_date) <= filters.date_to
      );
    }

    setFilteredTransactions(filtered);
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const clearFilters = () => {
    setFilters({
      security_name: '',
      transaction_type: '',
      date_from: null,
      date_to: null
    });
  };

  const handleEdit = (transaction) => {
    setEditingTransaction({
      ...transaction,
      transaction_date: new Date(transaction.transaction_date),
      order_date: new Date(transaction.order_date)
    });
    setShowEditModal(true);
  };

  const handleSaveEdit = async () => {
    try {
      const updatedTransaction = {
        ...editingTransaction,
        transaction_date: editingTransaction.transaction_date.toISOString(),
        order_date: editingTransaction.order_date.toISOString()
      };
      
      await apiService.updateTransaction(editingTransaction.id, updatedTransaction);
      toast.success('Transaction updated successfully');
      setShowEditModal(false);
      setEditingTransaction(null);
      loadTransactions();
    } catch (error) {
      toast.error('Error updating transaction');
      console.error('Error updating transaction:', error);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this transaction?')) {
      try {
        await apiService.deleteTransaction(id);
        toast.success('Transaction deleted successfully');
        loadTransactions();
      } catch (error) {
        toast.error('Error deleting transaction');
        console.error('Error deleting transaction:', error);
      }
    }
  };

  const exportToCSV = () => {
    const csvContent = [
      ['Date', 'Security', 'Type', 'Quantity', 'Price', 'Total Amount'],
      ...filteredTransactions.map(t => [
        format(new Date(t.transaction_date), 'yyyy-MM-dd'),
        t.security_name,
        t.transaction_type,
        t.quantity,
        t.price_per_unit,
        t.total_amount
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transactions.csv';
    a.click();
    window.URL.revokeObjectURL(url);
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
        <h2>📋 Transactions</h2>
        <Button variant="success" onClick={exportToCSV}>
          Export to CSV
        </Button>
      </div>

      {/* Filters */}
      <Card className="mb-4">
        <Card.Header>
          <h5>Filters</h5>
        </Card.Header>
        <Card.Body>
          <Row>
            <Col md={3}>
              <Form.Group>
                <Form.Label>Security Name</Form.Label>
                <FormControl
                  type="text"
                  placeholder="Search by security..."
                  value={filters.security_name}
                  onChange={(e) => handleFilterChange('security_name', e.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={2}>
              <Form.Group>
                <Form.Label>Type</Form.Label>
                <Form.Select
                  value={filters.transaction_type}
                  onChange={(e) => handleFilterChange('transaction_type', e.target.value)}
                >
                  <option value="">All</option>
                  <option value="BUY">Buy</option>
                  <option value="SELL">Sell</option>
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={2}>
              <Form.Group>
                <Form.Label>From Date</Form.Label>
                <DatePicker
                  selected={filters.date_from}
                  onChange={(date) => handleFilterChange('date_from', date)}
                  className="form-control"
                  placeholderText="From date"
                  dateFormat="yyyy-MM-dd"
                />
              </Form.Group>
            </Col>
            <Col md={2}>
              <Form.Group>
                <Form.Label>To Date</Form.Label>
                <DatePicker
                  selected={filters.date_to}
                  onChange={(date) => handleFilterChange('date_to', date)}
                  className="form-control"
                  placeholderText="To date"
                  dateFormat="yyyy-MM-dd"
                />
              </Form.Group>
            </Col>
            <Col md={3} className="d-flex align-items-end">
              <Button variant="outline-secondary" onClick={clearFilters}>
                Clear Filters
              </Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {/* Transactions Table */}
      <Card>
        <Card.Header>
          <h5>Transaction History ({filteredTransactions.length} records)</h5>
        </Card.Header>
        <Card.Body>
          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Security</th>
                  <th>Type</th>
                  <th>Quantity</th>
                  <th>Price</th>
                  <th>Total Amount</th>
                  <th>Exchange</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTransactions.map(transaction => (
                  <tr key={transaction.id} className="transaction-row">
                    <td>{format(new Date(transaction.transaction_date), 'dd/MM/yyyy')}</td>
                    <td>
                      <strong>{transaction.security_name}</strong>
                      {transaction.security_symbol && (
                        <small className="text-muted d-block">{transaction.security_symbol}</small>
                      )}
                    </td>
                    <td>
                      <Badge bg={transaction.transaction_type === 'BUY' ? 'success' : 'danger'}>
                        {transaction.transaction_type}
                      </Badge>
                    </td>
                    <td>{transaction.quantity}</td>
                    <td>₹{transaction.price_per_unit.toFixed(2)}</td>
                    <td>₹{transaction.total_amount.toLocaleString('en-IN')}</td>
                    <td>{transaction.exchange || 'NSE'}</td>
                    <td>
                      <Dropdown>
                        <Dropdown.Toggle variant="outline-primary" size="sm">
                          Actions
                        </Dropdown.Toggle>
                        <Dropdown.Menu>
                          <Dropdown.Item onClick={() => handleEdit(transaction)}>
                            Edit
                          </Dropdown.Item>
                          <Dropdown.Item 
                            onClick={() => handleDelete(transaction.id)}
                            className="text-danger"
                          >
                            Delete
                          </Dropdown.Item>
                        </Dropdown.Menu>
                      </Dropdown>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {filteredTransactions.length === 0 && (
            <p className="text-center text-muted mt-3">
              {transactions.length === 0 ? 'No transactions found' : 'No transactions match the current filters'}
            </p>
          )}
        </Card.Body>
      </Card>

      {/* Edit Transaction Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Edit Transaction</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {editingTransaction && (
            <Form>
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Security Name</Form.Label>
                    <Form.Control
                      type="text"
                      value={editingTransaction.security_name}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        security_name: e.target.value
                      })}
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Security Symbol</Form.Label>
                    <Form.Control
                      type="text"
                      value={editingTransaction.security_symbol || ''}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        security_symbol: e.target.value
                      })}
                    />
                  </Form.Group>
                </Col>
              </Row>
              
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Transaction Type</Form.Label>
                    <Form.Select
                      value={editingTransaction.transaction_type}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        transaction_type: e.target.value
                      })}
                    >
                      <option value="BUY">Buy</option>
                      <option value="SELL">Sell</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Quantity</Form.Label>
                    <Form.Control
                      type="number"
                      step="0.01"
                      value={editingTransaction.quantity}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        quantity: parseFloat(e.target.value)
                      })}
                    />
                  </Form.Group>
                </Col>
              </Row>
              
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Price per Unit</Form.Label>
                    <Form.Control
                      type="number"
                      step="0.01"
                      value={editingTransaction.price_per_unit}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        price_per_unit: parseFloat(e.target.value)
                      })}
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Total Amount</Form.Label>
                    <Form.Control
                      type="number"
                      step="0.01"
                      value={editingTransaction.total_amount}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        total_amount: parseFloat(e.target.value)
                      })}
                    />
                  </Form.Group>
                </Col>
              </Row>
              
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Transaction Date</Form.Label>
                    <DatePicker
                      selected={editingTransaction.transaction_date}
                      onChange={(date) => setEditingTransaction({
                        ...editingTransaction,
                        transaction_date: date
                      })}
                      className="form-control"
                      dateFormat="yyyy-MM-dd"
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Exchange</Form.Label>
                    <Form.Control
                      type="text"
                      value={editingTransaction.exchange || ''}
                      onChange={(e) => setEditingTransaction({
                        ...editingTransaction,
                        exchange: e.target.value
                      })}
                    />
                  </Form.Group>
                </Col>
              </Row>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEditModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSaveEdit}>
            Save Changes
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default Transactions;