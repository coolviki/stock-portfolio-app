import React, { useState, useCallback } from 'react';
import { Card, Form, Button, Row, Col, Alert, Dropdown, ListGroup } from 'react-bootstrap';
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
    isin: '',
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
  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchTimeoutId, setSearchTimeoutId] = useState(null);

  const handleStockSearch = useCallback(async (query, sourceField) => {
    if (searchTimeoutId) {
      clearTimeout(searchTimeoutId);
    }

    const timeoutId = setTimeout(async () => {
      try {
        if (!query || query.length < 2) {
          setSearchResults([]);
          setShowDropdown(false);
          return;
        }

        const response = await apiService.searchStocks(query);
        setSearchResults(response.results || []);
        setShowDropdown(response.results?.length > 0);
      } catch (error) {
        console.error('Stock search error:', error);
        setSearchResults([]);
        setShowDropdown(false);
      }
    }, 300);

    setSearchTimeoutId(timeoutId);
  }, [searchTimeoutId]);

  const handleStockSelect = async (stock) => {
    try {
      // First, enrich the security data to get missing ISIN/ticker info
      const enrichedData = await apiService.enrichSecurityData(
        stock.name,
        stock.symbol,
        stock.isin
      );
      
      setFormData(prev => ({
        ...prev,
        security_name: enrichedData.security_name || stock.name,
        security_symbol: enrichedData.ticker || stock.symbol,
        isin: enrichedData.isin || stock.isin || ''
      }));
    } catch (error) {
      console.error('Error enriching security data:', error);
      // Fallback to original data if enrichment fails
      setFormData(prev => ({
        ...prev,
        security_name: stock.name,
        security_symbol: stock.symbol,
        isin: stock.isin || ''
      }));
    }
    
    setShowDropdown(false);
    setSearchResults([]);
  };

  const handleChange = (field, value) => {
    setFormData(prev => {
      const updated = { ...prev, [field]: value };
      
      // Auto-calculate total amount if enabled
      if (autoCalculate && (field === 'quantity' || field === 'price_per_unit')) {
        const quantity = parseFloat(field === 'quantity' ? value : updated.quantity) || 0;
        const price = parseFloat(field === 'price_per_unit' ? value : updated.price_per_unit) || 0;
        updated.total_amount = (quantity * price).toFixed(2);
      }
      
      // Trigger stock search for name or symbol fields
      if (field === 'security_name' || field === 'security_symbol') {
        handleStockSearch(value, field);
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

      // Use legacy endpoint for backward compatibility with new security model
      const response = await fetch('/api/transactions/legacy/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(transactionData)
      });
      
      if (!response.ok) {
        throw new Error('Failed to create transaction');
      }
      toast.success('Transaction added successfully!');
      
      // Reset form
      setFormData({
        security_name: '',
        security_symbol: '',
        isin: '',
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
      isin: '',
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
                <Form.Group className="mb-3" style={{ position: 'relative' }}>
                  <Form.Label>Security Name *</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., Reliance Industries Limited"
                    value={formData.security_name}
                    onChange={(e) => handleChange('security_name', e.target.value)}
                    onFocus={() => {
                      if (formData.security_name.length >= 2) {
                        handleStockSearch(formData.security_name, 'security_name');
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding dropdown to allow clicks
                      setTimeout(() => setShowDropdown(false), 200);
                    }}
                    autoComplete="off"
                    required
                  />
                  {showDropdown && searchResults.length > 0 && (
                    <div
                      className="position-absolute w-100 bg-white border rounded shadow-sm"
                      style={{ zIndex: 1000, top: '100%', maxHeight: '200px', overflowY: 'auto' }}
                    >
                      <ListGroup variant="flush">
                        {searchResults.map((stock, index) => (
                          <ListGroup.Item
                            key={index}
                            action
                            onClick={() => handleStockSelect(stock)}
                            className="py-2 border-0"
                            style={{ cursor: 'pointer' }}
                          >
                            <div className="d-flex justify-content-between align-items-center">
                              <div>
                                <div className="fw-bold text-primary">{stock.symbol}</div>
                                <div className="text-muted small">{stock.name}</div>
                              </div>
                            </div>
                          </ListGroup.Item>
                        ))}
                      </ListGroup>
                    </div>
                  )}
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3" style={{ position: 'relative' }}>
                  <Form.Label>Security Symbol</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., RELIANCE"
                    value={formData.security_symbol}
                    onChange={(e) => handleChange('security_symbol', e.target.value)}
                    onFocus={() => {
                      if (formData.security_symbol.length >= 2) {
                        handleStockSearch(formData.security_symbol, 'security_symbol');
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding dropdown to allow clicks
                      setTimeout(() => setShowDropdown(false), 200);
                    }}
                    autoComplete="off"
                  />
                  {showDropdown && searchResults.length > 0 && (
                    <div
                      className="position-absolute w-100 bg-white border rounded shadow-sm"
                      style={{ zIndex: 1000, top: '100%', maxHeight: '200px', overflowY: 'auto' }}
                    >
                      <ListGroup variant="flush">
                        {searchResults.map((stock, index) => (
                          <ListGroup.Item
                            key={index}
                            action
                            onClick={() => handleStockSelect(stock)}
                            className="py-2 border-0"
                            style={{ cursor: 'pointer' }}
                          >
                            <div className="d-flex justify-content-between align-items-center">
                              <div>
                                <div className="fw-bold text-primary">{stock.symbol}</div>
                                <div className="text-muted small">{stock.name}</div>
                              </div>
                            </div>
                          </ListGroup.Item>
                        ))}
                      </ListGroup>
                    </div>
                  )}
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={12}>
                <Form.Group className="mb-3">
                  <Form.Label>ISIN Code</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g., INE002A01018"
                    value={formData.isin}
                    onChange={(e) => handleChange('isin', e.target.value)}
                    maxLength={12}
                  />
                  <Form.Text className="text-muted">
                    International Securities Identification Number (auto-filled from search)
                  </Form.Text>
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
                <li>Start typing in Security Name or Symbol fields for auto-suggestions</li>
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