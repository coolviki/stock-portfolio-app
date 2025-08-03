import React, { useState } from 'react';
import { Card, Form, Button, Row, Col, Alert } from 'react-bootstrap';
import DatePicker from 'react-datepicker';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';
import 'react-datepicker/dist/react-datepicker.css';

const ManualEntry = () => {
  const { selectedUserId } = useAuth();
  const [formData, setFormData] = useState({
    security_name: '',
    security_symbol: '',
    transaction_type: 'BUY',
    quantity: '',
    price_per_unit: '',
    total_amount: '',
    transaction_date: new Date(),
    order_date: new Date(),
    exchange: 'NSE',
    broker_fees: '',
    taxes: ''
  });
  
  const [saving, setSaving] = useState(false);
  const [autoCalculate, setAutoCalculate] = useState(true);

  const handleChange = (field, value) => {
    setFormData(prev => {
      const updated = { ...prev, [field]: value };
      
      // Auto-calculate total amount if enabled
      if (autoCalculate && (field === 'quantity' || field === 'price_per_unit')) {
        const quantity = parseFloat(field === 'quantity' ? value : updated.quantity) || 0;
        const price = parseFloat(field === 'price_per_unit' ? value : updated.price_per_unit) || 0;
        updated.total_amount = (quantity * price).toFixed(2);
      }
      
      return updated;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedUserId) {
      toast.error('Please log in to add transactions');
      return;
    }
    
    setSaving(true);

    try {
      const transactionData = {
        ...formData,
        quantity: parseFloat(formData.quantity),
        price_per_unit: parseFloat(formData.price_per_unit),
        total_amount: parseFloat(formData.total_amount),
        broker_fees: parseFloat(formData.broker_fees) || 0,
        taxes: parseFloat(formData.taxes) || 0,
        transaction_date: formData.transaction_date.toISOString(),
        order_date: formData.order_date.toISOString()
      };

      await apiService.createTransaction(transactionData, selectedUserId);
      toast.success('Transaction added successfully!');
      
      // Reset form
      setFormData({
        security_name: '',
        security_symbol: '',
        transaction_type: 'BUY',
        quantity: '',
        price_per_unit: '',
        total_amount: '',
        transaction_date: new Date(),
        order_date: new Date(),
        exchange: 'NSE',
        broker_fees: '',
        taxes: ''
      });
    } catch (error) {
      toast.error('Error adding transaction: ' + (error.response?.data?.detail || error.message));
      console.error('Error adding transaction:', error);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setFormData({
      security_name: '',
      security_symbol: '',
      transaction_type: 'BUY',
      quantity: '',
      price_per_unit: '',
      total_amount: '',
      transaction_date: new Date(),
      order_date: new Date(),
      exchange: 'NSE',
      broker_fees: '',
      taxes: ''
    });
  };

  return (
    <div>
      <h2 className="mb-4">✏️ Manual Transaction Entry</h2>

      <Card>
        <Card.Header>
          <h5>Add New Transaction</h5>
        </Card.Header>
        <Card.Body>
          <Alert variant="info">
            <strong>Tip:</strong> Fill in the security name, transaction type, quantity, and price. 
            The total amount will be calculated automatically.
          </Alert>

          <Form onSubmit={handleSubmit}>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Security Name *</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., Reliance Industries Limited"
                    value={formData.security_name}
                    onChange={(e) => handleChange('security_name', e.target.value)}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Security Symbol</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., RELIANCE"
                    value={formData.security_symbol}
                    onChange={(e) => handleChange('security_symbol', e.target.value)}
                  />
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Transaction Type *</Form.Label>
                  <Form.Select
                    value={formData.transaction_type}
                    onChange={(e) => handleChange('transaction_type', e.target.value)}
                  >
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Exchange</Form.Label>
                  <Form.Select
                    value={formData.exchange}
                    onChange={(e) => handleChange('exchange', e.target.value)}
                  >
                    <option value="NSE">NSE</option>
                    <option value="BSE">BSE</option>
                    <option value="MCX">MCX</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Quantity *</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="e.g., 100"
                    value={formData.quantity}
                    onChange={(e) => handleChange('quantity', e.target.value)}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Price per Unit (₹) *</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="e.g., 2450.50"
                    value={formData.price_per_unit}
                    onChange={(e) => handleChange('price_per_unit', e.target.value)}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Total Amount (₹) *</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="Auto-calculated"
                    value={formData.total_amount}
                    onChange={(e) => handleChange('total_amount', e.target.value)}
                    disabled={autoCalculate}
                    required
                  />
                  <Form.Check
                    type="checkbox"
                    label="Auto-calculate"
                    checked={autoCalculate}
                    onChange={(e) => setAutoCalculate(e.target.checked)}
                    className="mt-1"
                  />
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Transaction Date *</Form.Label>
                  <DatePicker
                    selected={formData.transaction_date}
                    onChange={(date) => handleChange('transaction_date', date)}
                    className="form-control"
                    dateFormat="dd/MM/yyyy"
                    maxDate={new Date()}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Order Date *</Form.Label>
                  <DatePicker
                    selected={formData.order_date}
                    onChange={(date) => handleChange('order_date', date)}
                    className="form-control"
                    dateFormat="dd/MM/yyyy"
                    maxDate={new Date()}
                  />
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Broker Fees (₹)</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="e.g., 20.00"
                    value={formData.broker_fees}
                    onChange={(e) => handleChange('broker_fees', e.target.value)}
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Taxes (₹)</Form.Label>
                  <Form.Control
                    type="number"
                    step="0.01"
                    placeholder="e.g., 50.00"
                    value={formData.taxes}
                    onChange={(e) => handleChange('taxes', e.target.value)}
                  />
                </Form.Group>
              </Col>
            </Row>

            <div className="d-flex gap-2">
              <Button
                type="submit"
                variant="primary"
                disabled={saving}
              >
                {saving ? 'Adding Transaction...' : 'Add Transaction'}
              </Button>
              
              <Button
                type="button"
                variant="outline-secondary"
                onClick={resetForm}
              >
                Reset Form
              </Button>
            </div>
          </Form>
        </Card.Body>
      </Card>

      {/* Quick Add Section */}
      <Card className="mt-4">
        <Card.Header>
          <h5>Quick Add Tips</h5>
        </Card.Header>
        <Card.Body>
          <Row>
            <Col md={6}>
              <h6>📝 Required Fields:</h6>
              <ul>
                <li>Security Name</li>
                <li>Transaction Type (Buy/Sell)</li>
                <li>Quantity</li>
                <li>Price per Unit</li>
                <li>Transaction Date</li>
              </ul>
            </Col>
            <Col md={6}>
              <h6>💡 Pro Tips:</h6>
              <ul>
                <li>Use consistent security names for better tracking</li>
                <li>Add security symbols for easier identification</li>
                <li>Include broker fees and taxes for accurate P&L</li>
                <li>Order date can be same as transaction date</li>
              </ul>
            </Col>
          </Row>
        </Card.Body>
      </Card>
    </div>
  );
};

export default ManualEntry;