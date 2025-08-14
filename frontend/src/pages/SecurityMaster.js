import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Alert, Badge, InputGroup, OverlayTrigger, Tooltip, Spinner } from 'react-bootstrap';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';
import { fetchStockPriceBySymbol, fetchStockPriceByIsin } from '../utils/apiUtils';
import { useAuth } from '../context/AuthContext';

const SecurityMaster = () => {
  const { user, isAdmin } = useAuth();
  const [securities, setSecurities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedSecurity, setSelectedSecurity] = useState(null);
  const [formData, setFormData] = useState({
    security_name: '',
    security_ISIN: '',
    security_ticker: ''
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [priceData, setPriceData] = useState({});
  const [loadingPrice, setLoadingPrice] = useState({});

  useEffect(() => {
    loadSecurities();
  }, []);

  const loadSecurities = async () => {
    try {
      setLoading(true);
      const data = await apiService.getSecurities(0, 1000); // Load up to 1000 securities
      setSecurities(data);
    } catch (error) {
      toast.error('Error loading securities');
      console.error('Error loading securities:', error);
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      security_name: '',
      security_ISIN: '',
      security_ticker: ''
    });
  };

  const handleCreateSecurity = async () => {
    if (!formData.security_name || !formData.security_ISIN || !formData.security_ticker) {
      toast.error('Please fill in all fields');
      return;
    }

    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setSaving(true);
    try {
      await apiService.createSecurity(formData, user.email);
      toast.success('Security created successfully!');
      setShowCreateModal(false);
      resetForm();
      loadSecurities();
    } catch (error) {
      toast.error('Error creating security: ' + (error.response?.data?.detail || error.message));
      console.error('Error creating security:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleEditSecurity = async () => {
    if (!formData.security_name || !formData.security_ISIN || !formData.security_ticker) {
      toast.error('Please fill in all fields');
      return;
    }

    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setSaving(true);
    try {
      await apiService.updateSecurity(selectedSecurity.id, formData, user.email);
      toast.success('Security updated successfully!');
      setShowEditModal(false);
      setSelectedSecurity(null);
      resetForm();
      loadSecurities();
    } catch (error) {
      toast.error('Error updating security: ' + (error.response?.data?.detail || error.message));
      console.error('Error updating security:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSecurity = async () => {
    if (!selectedSecurity) return;

    if (!user?.email) {
      toast.error('User email is required for admin operations');
      return;
    }

    setDeleting(true);
    try {
      await apiService.deleteSecurity(selectedSecurity.id, user.email);
      toast.success(`Security '${selectedSecurity.security_name}' deleted successfully!`);
      setShowDeleteModal(false);
      setSelectedSecurity(null);
      loadSecurities();
    } catch (error) {
      toast.error('Error deleting security: ' + (error.response?.data?.detail || error.message));
      console.error('Error deleting security:', error);
    } finally {
      setDeleting(false);
    }
  };

  const openEditModal = (security) => {
    setSelectedSecurity(security);
    setFormData({
      security_name: security.security_name,
      security_ISIN: security.security_ISIN,
      security_ticker: security.security_ticker
    });
    setShowEditModal(true);
  };

  const openDeleteModal = (security) => {
    setSelectedSecurity(security);
    setShowDeleteModal(true);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const fetchSecurityPrice = async (security) => {
    const securityId = security.id;
    
    // Don't fetch if already loading
    if (loadingPrice[securityId]) {
      return;
    }

    setLoadingPrice(prev => ({ ...prev, [securityId]: true }));
    
    try {
      let price = null;
      let method = '';
      let timestamp = new Date().toLocaleString('en-IN');

      // Try waterfall price fetching: TICKER → ISIN → Security Name
      if (security.security_ticker) {
        try {
          const response = await fetchStockPriceBySymbol(security.security_ticker);
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
      if (!price && security.security_ISIN) {
        try {
          const response = await fetchStockPriceByIsin(security.security_ISIN);
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
        [securityId]: {
          price: price || 'N/A',
          method,
          timestamp,
          symbol: security.security_ticker || 'N/A',
          error: !price
        }
      }));

    } catch (error) {
      console.error('Error fetching price:', error);
      setPriceData(prev => ({
        ...prev,
        [securityId]: {
          price: 'Error',
          method: 'ERROR',
          timestamp: new Date().toLocaleString('en-IN'),
          symbol: security.security_ticker || 'N/A',
          error: true
        }
      }));
    } finally {
      setLoadingPrice(prev => ({ ...prev, [securityId]: false }));
    }
  };

  const handleSecurityNameClick = (security) => {
    fetchSecurityPrice(security);
  };

  const renderPriceTooltip = (security) => {
    const securityId = security.id;
    const loading = loadingPrice[securityId];
    const data = priceData[securityId];

    if (loading) {
      return (
        <Tooltip id={`price-tooltip-${securityId}`}>
          <div className="text-center">
            <Spinner animation="border" size="sm" className="me-2" />
            Fetching price...
          </div>
        </Tooltip>
      );
    }

    if (!data) {
      return (
        <Tooltip id={`price-tooltip-${securityId}`}>
          <div>
            <strong>📈 Click to fetch latest price</strong>
            <br />
            <small>Price will be fetched using waterfall method:<br />
            1. Ticker Symbol ({security.security_ticker || 'N/A'})<br />
            2. ISIN Code ({security.security_ISIN || 'N/A'})<br />
            3. Fallback pricing</small>
          </div>
        </Tooltip>
      );
    }

    return (
      <Tooltip id={`price-tooltip-${securityId}`}>
        <div>
          <strong>💰 Latest Price Information</strong>
          <hr className="my-2" style={{borderColor: '#fff'}} />
          <div><strong>Security:</strong> {security.security_name}</div>
          <div><strong>Symbol:</strong> {data.symbol}</div>
          <div><strong>Price:</strong> {data.error ? '❌ Unable to fetch' : `₹${parseFloat(data.price).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}</div>
          <div><strong>Method:</strong> {data.method || 'FALLBACK'}</div>
          <div><strong>Updated:</strong> {data.timestamp}</div>
          {!data.error && (
            <small className="text-light">
              <br />💡 Click again to refresh price
            </small>
          )}
        </div>
      </Tooltip>
    );
  };

  const filteredSecurities = securities.filter(security => 
    security.security_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    security.security_ISIN.toLowerCase().includes(searchTerm.toLowerCase()) ||
    security.security_ticker.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
            You do not have admin privileges to access the Security Master.
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
        <h2>🔐 Security Master</h2>
        <Button variant="primary" onClick={() => setShowCreateModal(true)}>
          Add New Security
        </Button>
      </div>

      <Card>
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h5>Securities Database ({filteredSecurities.length} of {securities.length})</h5>
            <InputGroup style={{ width: '300px' }}>
              <Form.Control
                type="text"
                placeholder="Search securities..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </InputGroup>
          </div>
        </Card.Header>
        <Card.Body>
          <Alert variant="info">
            <strong>Security Master:</strong> Manage the master list of securities for accurate transaction recording. 
            Each security has a unique name, ISIN code, and ticker symbol for precise identification.
            <br />
            <strong>💡 Tip:</strong> Click on any security name to fetch its latest price, or hover to see price tooltip with waterfall fetching details.
          </Alert>

          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Security Name</th>
                  <th>ISIN</th>
                  <th>Ticker</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSecurities.map(security => (
                  <tr key={security.id}>
                    <td>
                      <Badge bg="secondary">{security.id}</Badge>
                    </td>
                    <td>
                      <OverlayTrigger
                        placement="top"
                        delay={{ show: 250, hide: 400 }}
                        overlay={renderPriceTooltip(security)}
                        trigger={['hover', 'focus']}
                      >
                        <strong 
                          style={{ 
                            color: '#0d6efd', 
                            cursor: 'pointer', 
                            textDecoration: 'underline',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                          onClick={() => handleSecurityNameClick(security)}
                          title={`Click to fetch latest price for ${security.security_name}`}
                          onMouseEnter={(e) => e.target.style.color = '#0a58ca'}
                          onMouseLeave={(e) => e.target.style.color = '#0d6efd'}
                        >
                          {security.security_name}
                          {loadingPrice[security.id] ? (
                            <Spinner animation="border" size="sm" />
                          ) : (
                            '📈'
                          )}
                        </strong>
                      </OverlayTrigger>
                    </td>
                    <td>
                      <code>{security.security_ISIN}</code>
                    </td>
                    <td>
                      <Badge bg="primary">{security.security_ticker}</Badge>
                    </td>
                    <td>{formatDate(security.created_at)}</td>
                    <td>{formatDate(security.updated_at)}</td>
                    <td>
                      <div className="d-flex gap-2">
                        <Button 
                          variant="outline-primary" 
                          size="sm"
                          onClick={() => openEditModal(security)}
                          title="Edit security details"
                        >
                          Edit
                        </Button>
                        <Button 
                          variant="outline-danger" 
                          size="sm"
                          onClick={() => openDeleteModal(security)}
                          title="Delete security"
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {filteredSecurities.length === 0 && (
            <p className="text-center text-muted mt-3">
              {searchTerm ? 'No securities match your search criteria' : 'No securities found'}
            </p>
          )}
        </Card.Body>
      </Card>

      {/* Security Statistics */}
      <Card className="mt-4">
        <Card.Header>
          <h5>Security Statistics</h5>
        </Card.Header>
        <Card.Body>
          <div className="row text-center">
            <div className="col-md-4">
              <div className="card bg-primary text-white">
                <div className="card-body">
                  <h3>{securities.length}</h3>
                  <p>Total Securities</p>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-success text-white">
                <div className="card-body">
                  <h3>{securities.filter(s => s.security_ISIN && s.security_ISIN.length > 0).length}</h3>
                  <p>With ISIN</p>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-info text-white">
                <div className="card-body">
                  <h3>{securities.filter(s => new Date(s.created_at) > new Date(Date.now() - 7*24*60*60*1000)).length}</h3>
                  <p>Added This Week</p>
                </div>
              </div>
            </div>
          </div>
        </Card.Body>
      </Card>

      {/* Create Security Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Add New Security</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Security Name *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter full security name"
                value={formData.security_name}
                onChange={(e) => setFormData({...formData, security_name: e.target.value})}
              />
              <Form.Text className="text-muted">
                Full name of the security (e.g., "Reliance Industries Limited")
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>ISIN Code *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter ISIN code"
                value={formData.security_ISIN}
                onChange={(e) => setFormData({...formData, security_ISIN: e.target.value.toUpperCase()})}
                maxLength="12"
              />
              <Form.Text className="text-muted">
                International Securities Identification Number (e.g., "INE002A01018")
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Ticker Symbol *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter ticker symbol"
                value={formData.security_ticker}
                onChange={(e) => setFormData({...formData, security_ticker: e.target.value.toUpperCase()})}
              />
              <Form.Text className="text-muted">
                Stock exchange ticker symbol (e.g., "RELIANCE")
              </Form.Text>
            </Form.Group>

            <Alert variant="info">
              <small>
                <strong>Note:</strong> All fields are required. Make sure ISIN and ticker symbols are accurate for proper price fetching.
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
            onClick={handleCreateSecurity}
            disabled={saving}
          >
            {saving ? 'Adding...' : 'Add Security'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Edit Security Modal */}
      <Modal show={showEditModal} onHide={() => setShowEditModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Edit Security</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Security Name *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter full security name"
                value={formData.security_name}
                onChange={(e) => setFormData({...formData, security_name: e.target.value})}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>ISIN Code *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter ISIN code"
                value={formData.security_ISIN}
                onChange={(e) => setFormData({...formData, security_ISIN: e.target.value.toUpperCase()})}
                maxLength="12"
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Ticker Symbol *</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter ticker symbol"
                value={formData.security_ticker}
                onChange={(e) => setFormData({...formData, security_ticker: e.target.value.toUpperCase()})}
              />
            </Form.Group>

            <Alert variant="warning">
              <small>
                <strong>Caution:</strong> Editing security details may affect historical transaction data and price fetching accuracy.
              </small>
            </Alert>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowEditModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleEditSecurity}
            disabled={saving}
          >
            {saving ? 'Updating...' : 'Update Security'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Delete Security Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>⚠️ Delete Security</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger">
            <strong>Warning!</strong> This action cannot be undone.
          </Alert>
          <p>
            Are you sure you want to delete the security <strong>'{selectedSecurity?.security_name}'</strong>?
          </p>
          <p className="text-danger">
            <strong>Note:</strong> You cannot delete a security that is referenced by existing transactions.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
            Cancel
          </Button>
          <Button 
            variant="danger" 
            onClick={handleDeleteSecurity}
            disabled={deleting}
          >
            {deleting ? 'Deleting...' : 'Yes, Delete Security'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default SecurityMaster;