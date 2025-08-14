import React, { useState, useEffect, useRef } from 'react';
import { 
  Row, Col, Card, Table, Button, Form, Modal, Badge, 
  FormControl, Dropdown, ListGroup, OverlayTrigger, Tooltip, Spinner 
} from 'react-bootstrap';
import DatePicker from 'react-datepicker';
import { format } from 'date-fns';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';
import { fetchStockPriceBySymbol, fetchStockPriceByIsin } from '../utils/apiUtils';
import 'react-datepicker/dist/react-datepicker.css';

// Helper function to get current Indian Financial Year dates
const getIndianFinancialYearDates = () => {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth(); // 0-indexed (0 = January, 3 = April)
  
  let fyStartYear, fyEndYear;
  
  if (currentMonth >= 3) { // April (3) onwards is current FY
    fyStartYear = currentYear;
    fyEndYear = currentYear + 1;
  } else { // January to March belongs to previous FY
    fyStartYear = currentYear - 1;
    fyEndYear = currentYear;
  }
  
  return {
    startDate: new Date(fyStartYear, 3, 1), // April 1st
    endDate: new Date(fyEndYear, 2, 31)     // March 31st
  };
};

const Transactions = () => {
  const [transactions, setTransactions] = useState([]);
  const [filteredTransactions, setFilteredTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  
  // Initialize filters with Indian Financial Year dates
  const { startDate, endDate } = getIndianFinancialYearDates();
  const [filters, setFilters] = useState({
    security_name: '',
    transaction_type: '',
    date_from: startDate,
    date_to: endDate
  });

  // Type-ahead search state
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimeoutRef = useRef(null);
  const suggestionRefs = useRef([]);

  // Price tooltip state
  const [priceData, setPriceData] = useState({});
  const [loadingPrice, setLoadingPrice] = useState({});

  const { user, selectedUserId, isAllUsers } = useAuth();

  useEffect(() => {
    loadTransactions();
  }, [user, selectedUserId]);

  useEffect(() => {
    applyFilters();
  }, [transactions, filters]);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      if (!selectedUserId) {
        toast.error('Please select a user first');
        return;
      }
      const data = await apiService.getTransactions(selectedUserId);
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
        t.security?.security_name?.toLowerCase().includes(filters.security_name.toLowerCase())
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

    // Handle type-ahead search for security_name
    if (field === 'security_name') {
      handleSecuritySearch(value);
    }
  };

  const handleSecuritySearch = async (query) => {
    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (!query || query.trim().length < 2) {
      setSearchSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    // Debounce search
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        setSearchLoading(true);
        const response = await apiService.searchStocks(query);
        setSearchSuggestions(response.results || []);
        setShowSuggestions(true);
      } catch (error) {
        console.error('Search error:', error);
        setSearchSuggestions([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
  };

  const handleSuggestionSelect = (suggestion) => {
    setFilters(prev => ({
      ...prev,
      security_name: suggestion.name
    }));
    setShowSuggestions(false);
    setSearchSuggestions([]);
  };

  const clearFilters = () => {
    const { startDate, endDate } = getIndianFinancialYearDates();
    setFilters({
      security_name: '',
      transaction_type: '',
      date_from: startDate,
      date_to: endDate
    });
    setSearchSuggestions([]);
    setShowSuggestions(false);
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
      
      await apiService.updateTransaction(editingTransaction.id, updatedTransaction, selectedUserId);
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
        await apiService.deleteTransaction(id, selectedUserId);
        toast.success('Transaction deleted successfully');
        loadTransactions();
      } catch (error) {
        toast.error('Error deleting transaction');
        console.error('Error deleting transaction:', error);
      }
    }
  };

  const fetchSecurityPrice = async (transaction) => {
    const transactionId = transaction.id;
    
    // Don't fetch if already loading
    if (loadingPrice[transactionId]) {
      return;
    }

    setLoadingPrice(prev => ({ ...prev, [transactionId]: true }));
    
    try {
      let price = null;
      let method = '';
      let timestamp = new Date().toLocaleString('en-IN');

      // Try waterfall price fetching: TICKER → ISIN → Security Name
      if (transaction.security?.security_ticker) {
        try {
          const response = await fetchStockPriceBySymbol(transaction.security.security_ticker);
          if (response.ok) {
            const data = await response.json();
            price = data.price;
            method = 'TICKER';
          }
        } catch (error) {
          console.log('Ticker price fetch failed:', error);
        }
      }

      // Fallback to ISIN if ticker failed
      if (!price && transaction.security?.security_ISIN) {
        try {
          const response = await fetchStockPriceByIsin(transaction.security.security_ISIN);
          if (response.ok) {
            const data = await response.json();
            price = data.price;
            method = 'ISIN';
          }
        } catch (error) {
          console.log('ISIN price fetch failed:', error);
        }
      }

      // Store the price data
      setPriceData(prev => ({
        ...prev,
        [transactionId]: {
          price: price || 'N/A',
          method,
          timestamp,
          symbol: transaction.security?.security_ticker || 'N/A',
          error: !price,
          transactionPrice: transaction.price_per_unit,
          priceChange: price ? ((price - transaction.price_per_unit) / transaction.price_per_unit * 100) : null
        }
      }));

    } catch (error) {
      console.error('Error fetching price:', error);
      setPriceData(prev => ({
        ...prev,
        [transactionId]: {
          price: 'Error',
          method: 'ERROR',
          timestamp: new Date().toLocaleString('en-IN'),
          symbol: transaction.security?.security_ticker || 'N/A',
          error: true,
          transactionPrice: transaction.price_per_unit,
          priceChange: null
        }
      }));
    } finally {
      setLoadingPrice(prev => ({ ...prev, [transactionId]: false }));
    }
  };

  const handleSecurityNameClick = (transaction) => {
    fetchSecurityPrice(transaction);
  };

  const renderPriceTooltip = (transaction) => {
    const transactionId = transaction.id;
    const loading = loadingPrice[transactionId];
    const data = priceData[transactionId];

    if (loading) {
      return (
        <Tooltip id={`price-tooltip-${transactionId}`}>
          <div className="text-center">
            <Spinner animation="border" size="sm" className="me-2" />
            Fetching current price...
          </div>
        </Tooltip>
      );
    }

    if (!data) {
      return (
        <Tooltip id={`price-tooltip-${transactionId}`}>
          <div>
            <strong>📈 Click to fetch current price</strong>
            <br />
            <small>
              Transaction Price: ₹{transaction.price_per_unit.toFixed(2)}
              <br />
              Date: {format(new Date(transaction.transaction_date), 'dd/MM/yyyy')}
              <br />
              Symbol: {transaction.security?.security_ticker || 'N/A'}
            </small>
          </div>
        </Tooltip>
      );
    }

    const priceChangeColor = data.priceChange > 0 ? '#28a745' : data.priceChange < 0 ? '#dc3545' : '#6c757d';
    const priceChangeIcon = data.priceChange > 0 ? '📈' : data.priceChange < 0 ? '📉' : '➡️';

    return (
      <Tooltip id={`price-tooltip-${transactionId}`}>
        <div>
          <strong>💰 Price Comparison</strong>
          <hr className="my-2" style={{borderColor: '#fff'}} />
          <div><strong>Security:</strong> {transaction.security?.security_name || 'Unknown Security'}</div>
          <div><strong>Symbol:</strong> {data.symbol}</div>
          
          <hr className="my-2" style={{borderColor: '#fff'}} />
          <div><strong>Transaction Price:</strong> ₹{data.transactionPrice.toFixed(2)}</div>
          <div><strong>Current Price:</strong> {data.error ? '❌ Unable to fetch' : `₹${parseFloat(data.price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}</div>
          
          {!data.error && data.priceChange !== null && (
            <div style={{color: priceChangeColor}}>
              <strong>Change:</strong> {priceChangeIcon} {data.priceChange.toFixed(2)}%
            </div>
          )}
          
          <hr className="my-2" style={{borderColor: '#fff'}} />
          <div><strong>Method:</strong> {data.method || 'FALLBACK'}</div>
          <div><strong>Updated:</strong> {data.timestamp}</div>
          <div><strong>Transaction Date:</strong> {format(new Date(transaction.transaction_date), 'dd/MM/yyyy')}</div>
          
          {!data.error && (
            <small className="text-light">
              <br />💡 Click again to refresh price
            </small>
          )}
        </div>
      </Tooltip>
    );
  };

  const exportToCSV = () => {
    const csvContent = [
      ['Date', 'Security', 'Type', 'Quantity', 'Price', 'Total Amount'],
      ...filteredTransactions.map(t => [
        format(new Date(t.transaction_date), 'yyyy-MM-dd'),
        t.security?.security_name || 'Unknown Security',
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
          <div className="d-flex justify-content-between align-items-center">
            <h5>Filters</h5>
            <small className="text-muted">💡 Click on security names in the table to see current prices</small>
          </div>
        </Card.Header>
        <Card.Body>
          <Row>
            <Col md={3}>
              <Form.Group>
                <Form.Label>Security Name</Form.Label>
                <div style={{ position: 'relative' }}>
                  <FormControl
                    type="text"
                    placeholder="Search by security..."
                    value={filters.security_name}
                    onChange={(e) => handleFilterChange('security_name', e.target.value)}
                    onFocus={() => {
                      if (searchSuggestions.length > 0) {
                        setShowSuggestions(true);
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding suggestions to allow click
                      setTimeout(() => setShowSuggestions(false), 200);
                    }}
                  />
                  {searchLoading && (
                    <div style={{ position: 'absolute', right: '10px', top: '8px', zIndex: 10 }}>
                      <div className="spinner-border spinner-border-sm text-primary" role="status">
                        <span className="visually-hidden">Searching...</span>
                      </div>
                    </div>
                  )}
                  {showSuggestions && searchSuggestions.length > 0 && (
                    <ListGroup 
                      style={{ 
                        position: 'absolute', 
                        top: '100%', 
                        left: 0, 
                        right: 0, 
                        zIndex: 1000,
                        maxHeight: '200px',
                        overflowY: 'auto',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                        border: '1px solid #dee2e6'
                      }}
                    >
                      {searchSuggestions.map((suggestion, index) => (
                        <ListGroup.Item
                          key={index}
                          action
                          onClick={() => handleSuggestionSelect(suggestion)}
                          style={{ cursor: 'pointer', padding: '8px 12px' }}
                        >
                          <div>
                            <strong>{suggestion.name}</strong>
                            <small className="text-muted d-block">{suggestion.symbol}</small>
                          </div>
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  )}
                </div>
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
                      <OverlayTrigger
                        placement="top"
                        delay={{ show: 250, hide: 400 }}
                        overlay={renderPriceTooltip(transaction)}
                        trigger={['hover', 'focus']}
                      >
                        <div>
                          <strong 
                            style={{ 
                              color: '#0d6efd', 
                              cursor: 'pointer', 
                              textDecoration: 'underline',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                            onClick={() => handleSecurityNameClick(transaction)}
                            title={`Click to fetch current price for ${transaction.security?.security_name || 'this security'}`}
                            onMouseEnter={(e) => e.target.style.color = '#0a58ca'}
                            onMouseLeave={(e) => e.target.style.color = '#0d6efd'}
                          >
                            {transaction.security?.security_name || 'Unknown Security'}
                            {loadingPrice[transaction.id] ? (
                              <Spinner animation="border" size="sm" />
                            ) : (
                              '📈'
                            )}
                          </strong>
                          {transaction.security?.security_ticker && (
                            <small className="text-muted d-block">{transaction.security.security_ticker}</small>
                          )}
                        </div>
                      </OverlayTrigger>
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
                      value={editingTransaction.security?.security_name || editingTransaction.security_name || ''}
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
                      value={editingTransaction.security?.security_ticker || editingTransaction.security_symbol || ''}
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