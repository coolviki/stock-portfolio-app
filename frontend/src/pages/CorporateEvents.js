import React, { useState, useEffect, useRef } from 'react';
import { Container, Row, Col, Card, Form, Table, Badge, Button, Modal, Alert, Spinner, ListGroup } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

// Searchable Security Select Component
const SearchableSecuritySelect = ({ securities, value, onChange, placeholder = "Search or select security...", required = false }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);

  // Get selected security name for display
  const selectedSecurity = securities.find(s => s.id === parseInt(value));

  // Filter securities based on search term
  const filteredSecurities = securities.filter(s =>
    s.security_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.security_ticker?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.security_ISIN?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset highlighted index when filtered list changes
  useEffect(() => {
    setHighlightedIndex(0);
  }, [searchTerm]);

  const handleInputChange = (e) => {
    setSearchTerm(e.target.value);
    setIsOpen(true);
    if (e.target.value === '') {
      onChange({ target: { name: 'security_id', value: '' } });
    }
  };

  const handleSelect = (security) => {
    onChange({ target: { name: 'security_id', value: security.id.toString() } });
    setSearchTerm('');
    setIsOpen(false);
  };

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => Math.min(prev + 1, filteredSecurities.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredSecurities[highlightedIndex]) {
          handleSelect(filteredSecurities[highlightedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
      default:
        break;
    }
  };

  const handleClear = () => {
    onChange({ target: { name: 'security_id', value: '' } });
    setSearchTerm('');
    inputRef.current?.focus();
  };

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div className="input-group">
        <Form.Control
          ref={inputRef}
          type="text"
          placeholder={selectedSecurity ? selectedSecurity.security_name : placeholder}
          value={searchTerm}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          required={required && !value}
          style={{
            backgroundColor: selectedSecurity && !searchTerm ? '#e8f4e8' : undefined
          }}
        />
        {(value || searchTerm) && (
          <Button
            variant="outline-secondary"
            onClick={handleClear}
            title="Clear selection"
          >
            ×
          </Button>
        )}
        <Button
          variant="outline-secondary"
          onClick={() => setIsOpen(!isOpen)}
        >
          ▼
        </Button>
      </div>
      {selectedSecurity && !searchTerm && (
        <Form.Text className="text-success">
          Selected: {selectedSecurity.security_name} ({selectedSecurity.security_ticker})
        </Form.Text>
      )}
      {isOpen && (
        <ListGroup
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            maxHeight: '250px',
            overflowY: 'auto',
            zIndex: 1050,
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
          }}
        >
          {filteredSecurities.length === 0 ? (
            <ListGroup.Item className="text-muted">
              No securities found
            </ListGroup.Item>
          ) : (
            filteredSecurities.slice(0, 50).map((security, index) => (
              <ListGroup.Item
                key={security.id}
                action
                active={index === highlightedIndex}
                onClick={() => handleSelect(security)}
                style={{ cursor: 'pointer' }}
              >
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <strong>{security.security_name}</strong>
                    <br />
                    <small className="text-muted">
                      {security.security_ticker} | {security.security_ISIN}
                    </small>
                  </div>
                  {parseInt(value) === security.id && (
                    <Badge bg="success">✓</Badge>
                  )}
                </div>
              </ListGroup.Item>
            ))
          )}
          {filteredSecurities.length > 50 && (
            <ListGroup.Item className="text-muted text-center">
              Type to filter... ({filteredSecurities.length - 50} more)
            </ListGroup.Item>
          )}
        </ListGroup>
      )}
    </div>
  );
};

const EVENT_TYPES = [
  { value: 'SPLIT', label: 'Stock Split' },
  { value: 'BONUS', label: 'Bonus Issue' },
  { value: 'DIVIDEND', label: 'Dividend' },
  { value: 'RIGHTS', label: 'Rights Issue' },
  { value: 'MERGER', label: 'Merger' },
  { value: 'DEMERGER', label: 'Demerger' }
];

const DIVIDEND_TYPES = [
  { value: 'CASH', label: 'Cash Dividend' },
  { value: 'STOCK', label: 'Stock Dividend' },
  { value: 'SPECIAL', label: 'Special Dividend' }
];

const CorporateEvents = () => {
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState([]);
  const [securities, setSecurities] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [filters, setFilters] = useState({
    security_id: '',
    event_type: '',
    is_applied: ''
  });

  const [formData, setFormData] = useState({
    security_id: '',
    event_type: 'SPLIT',
    event_date: '',
    record_date: '',
    ex_date: '',
    ratio_numerator: '',
    ratio_denominator: '',
    dividend_per_share: '',
    dividend_type: 'CASH',
    description: '',
    source: 'MANUAL'
  });

  useEffect(() => {
    loadSecurities();
    loadEvents();
  }, []);

  useEffect(() => {
    loadEvents();
  }, [filters]);

  const loadSecurities = async () => {
    try {
      const data = await apiService.getSecurities();
      setSecurities(data);
    } catch (error) {
      console.error('Error loading securities:', error);
    }
  };

  const loadEvents = async () => {
    try {
      setLoading(true);
      const filterParams = {};
      if (filters.security_id) filterParams.security_id = filters.security_id;
      if (filters.event_type) filterParams.event_type = filters.event_type;
      if (filters.is_applied !== '') filterParams.is_applied = filters.is_applied === 'true';

      const data = await apiService.getCorporateEvents(filterParams);
      setEvents(data);
    } catch (error) {
      console.error('Error loading events:', error);
      toast.error('Failed to load corporate events');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const resetForm = () => {
    setFormData({
      security_id: '',
      event_type: 'SPLIT',
      event_date: '',
      record_date: '',
      ex_date: '',
      ratio_numerator: '',
      ratio_denominator: '',
      dividend_per_share: '',
      dividend_type: 'CASH',
      description: '',
      source: 'MANUAL'
    });
    setEditingEvent(null);
  };

  const openCreateModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (event) => {
    setEditingEvent(event);
    setFormData({
      security_id: event.security_id,
      event_type: event.event_type,
      event_date: event.event_date ? event.event_date.split('T')[0] : '',
      record_date: event.record_date ? event.record_date.split('T')[0] : '',
      ex_date: event.ex_date ? event.ex_date.split('T')[0] : '',
      ratio_numerator: event.ratio_numerator || '',
      ratio_denominator: event.ratio_denominator || '',
      dividend_per_share: event.dividend_per_share || '',
      dividend_type: event.dividend_type || 'CASH',
      description: event.description || '',
      source: event.source || 'MANUAL'
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!isAdmin) {
      toast.error('Admin access required');
      return;
    }

    try {
      setLoading(true);

      // Helper to convert date string to datetime string for backend
      const toDatetime = (dateStr) => {
        if (!dateStr) return null;
        return `${dateStr}T00:00:00`;
      };

      const eventData = {
        security_id: parseInt(formData.security_id),
        event_type: formData.event_type,
        event_date: toDatetime(formData.event_date),
        record_date: toDatetime(formData.record_date),
        ex_date: toDatetime(formData.ex_date),
        description: formData.description || null,
        source: formData.source
      };

      // Add type-specific fields
      if (['SPLIT', 'BONUS', 'RIGHTS'].includes(formData.event_type)) {
        eventData.ratio_numerator = parseInt(formData.ratio_numerator);
        eventData.ratio_denominator = parseInt(formData.ratio_denominator);
      }

      if (formData.event_type === 'DIVIDEND') {
        eventData.dividend_per_share = parseFloat(formData.dividend_per_share);
        eventData.dividend_type = formData.dividend_type;
      }

      if (editingEvent) {
        await apiService.updateCorporateEvent(editingEvent.id, eventData, user.email);
        toast.success('Corporate event updated');
      } else {
        await apiService.createCorporateEvent(eventData, user.email);
        toast.success('Corporate event created');
      }

      setShowModal(false);
      resetForm();
      loadEvents();
    } catch (error) {
      console.error('Error saving event:', error);
      toast.error(error.response?.data?.detail || 'Failed to save event');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async (eventId) => {
    if (!isAdmin) {
      toast.error('Admin access required');
      return;
    }

    if (!window.confirm('Are you sure you want to apply this corporate event? This will adjust cost basis for all affected lots.')) {
      return;
    }

    try {
      setLoading(true);
      const result = await apiService.applyCorporateEvent(eventId, user.email);
      toast.success(result.message);
      loadEvents();
    } catch (error) {
      console.error('Error applying event:', error);
      toast.error(error.response?.data?.detail || 'Failed to apply event');
    } finally {
      setLoading(false);
    }
  };

  const handleRevert = async (eventId) => {
    if (!isAdmin) {
      toast.error('Admin access required');
      return;
    }

    if (!window.confirm('Are you sure you want to revert this corporate event? This will undo cost basis adjustments.')) {
      return;
    }

    try {
      setLoading(true);
      const result = await apiService.revertCorporateEvent(eventId, user.email);
      toast.success(result.message);
      loadEvents();
    } catch (error) {
      console.error('Error reverting event:', error);
      toast.error(error.response?.data?.detail || 'Failed to revert event');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (eventId) => {
    if (!isAdmin) {
      toast.error('Admin access required');
      return;
    }

    if (!window.confirm('Are you sure you want to delete this corporate event?')) {
      return;
    }

    try {
      setLoading(true);
      await apiService.deleteCorporateEvent(eventId, user.email);
      toast.success('Corporate event deleted');
      loadEvents();
    } catch (error) {
      console.error('Error deleting event:', error);
      toast.error(error.response?.data?.detail || 'Failed to delete event');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-IN');
  };

  const getEventTypeBadge = (eventType) => {
    const colors = {
      SPLIT: 'primary',
      BONUS: 'success',
      DIVIDEND: 'info',
      RIGHTS: 'warning',
      MERGER: 'secondary',
      DEMERGER: 'dark'
    };
    return <Badge bg={colors[eventType] || 'secondary'}>{eventType}</Badge>;
  };

  const getRatioDisplay = (event) => {
    if (event.ratio_numerator && event.ratio_denominator) {
      return `${event.ratio_numerator}:${event.ratio_denominator}`;
    }
    if (event.dividend_per_share) {
      return `Rs. ${event.dividend_per_share}/share`;
    }
    return '-';
  };

  const getSecurityName = (securityId) => {
    const security = securities.find(s => s.id === securityId);
    return security ? security.security_name : `Security ${securityId}`;
  };

  if (!isAdmin) {
    return (
      <Container className="mt-4">
        <Alert variant="warning">
          <Alert.Heading>Admin Access Required</Alert.Heading>
          <p>You need admin privileges to manage corporate events.</p>
        </Alert>
      </Container>
    );
  }

  return (
    <Container fluid className="mt-4">
      <Row>
        <Col>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2>Corporate Events</h2>
            <Button variant="primary" onClick={openCreateModal}>
              Add Corporate Event
            </Button>
          </div>

          {/* Filters */}
          <Card className="mb-4">
            <Card.Body>
              <Row>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Security</Form.Label>
                    <SearchableSecuritySelect
                      securities={securities}
                      value={filters.security_id}
                      onChange={handleFilterChange}
                      placeholder="All Securities - type to search..."
                    />
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Event Type</Form.Label>
                    <Form.Select
                      name="event_type"
                      value={filters.event_type}
                      onChange={handleFilterChange}
                    >
                      <option value="">All Types</option>
                      {EVENT_TYPES.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Status</Form.Label>
                    <Form.Select
                      name="is_applied"
                      value={filters.is_applied}
                      onChange={handleFilterChange}
                    >
                      <option value="">All</option>
                      <option value="true">Applied</option>
                      <option value="false">Pending</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Events Table */}
          <Card>
            <Card.Body>
              {loading ? (
                <div className="text-center py-4">
                  <Spinner animation="border" variant="primary" />
                </div>
              ) : events.length === 0 ? (
                <Alert variant="info">
                  No corporate events found. Click "Add Corporate Event" to create one.
                </Alert>
              ) : (
                <Table responsive hover>
                  <thead>
                    <tr>
                      <th>Security</th>
                      <th>Type</th>
                      <th>Event Date</th>
                      <th>Ratio/Value</th>
                      <th>Status</th>
                      <th>Source</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map(event => (
                      <tr key={event.id}>
                        <td>
                          <strong>{getSecurityName(event.security_id)}</strong>
                          {event.description && (
                            <div className="text-muted small">{event.description}</div>
                          )}
                        </td>
                        <td>{getEventTypeBadge(event.event_type)}</td>
                        <td>{formatDate(event.event_date)}</td>
                        <td>{getRatioDisplay(event)}</td>
                        <td>
                          {event.is_applied ? (
                            <Badge bg="success">Applied</Badge>
                          ) : (
                            <Badge bg="warning">Pending</Badge>
                          )}
                        </td>
                        <td>{event.source}</td>
                        <td>
                          {event.is_applied ? (
                            <Button
                              variant="outline-warning"
                              size="sm"
                              onClick={() => handleRevert(event.id)}
                            >
                              Revert
                            </Button>
                          ) : (
                            <>
                              <Button
                                variant="outline-success"
                                size="sm"
                                className="me-1"
                                onClick={() => handleApply(event.id)}
                              >
                                Apply
                              </Button>
                              <Button
                                variant="outline-primary"
                                size="sm"
                                className="me-1"
                                onClick={() => openEditModal(event)}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="outline-danger"
                                size="sm"
                                onClick={() => handleDelete(event.id)}
                              >
                                Delete
                              </Button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Create/Edit Modal */}
      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            {editingEvent ? 'Edit Corporate Event' : 'Create Corporate Event'}
          </Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleSubmit}>
          <Modal.Body>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Security *</Form.Label>
                  <SearchableSecuritySelect
                    securities={securities}
                    value={formData.security_id}
                    onChange={handleFormChange}
                    placeholder="Type to search security..."
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Event Type *</Form.Label>
                  <Form.Select
                    name="event_type"
                    value={formData.event_type}
                    onChange={handleFormChange}
                    required
                  >
                    {EVENT_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Event Date *</Form.Label>
                  <Form.Control
                    type="date"
                    name="event_date"
                    value={formData.event_date}
                    onChange={handleFormChange}
                    required
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Record Date</Form.Label>
                  <Form.Control
                    type="date"
                    name="record_date"
                    value={formData.record_date}
                    onChange={handleFormChange}
                  />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3">
                  <Form.Label>Ex-Date</Form.Label>
                  <Form.Control
                    type="date"
                    name="ex_date"
                    value={formData.ex_date}
                    onChange={handleFormChange}
                  />
                </Form.Group>
              </Col>
            </Row>

            {['SPLIT', 'BONUS', 'RIGHTS'].includes(formData.event_type) && (
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Ratio Numerator *</Form.Label>
                    <Form.Control
                      type="number"
                      name="ratio_numerator"
                      value={formData.ratio_numerator}
                      onChange={handleFormChange}
                      placeholder="e.g., 2 for 2:1 split"
                      min="1"
                      required
                    />
                    <Form.Text className="text-muted">
                      {formData.event_type === 'SPLIT' && 'New shares per old share (e.g., 2 for 2:1 split)'}
                      {formData.event_type === 'BONUS' && 'Bonus shares (e.g., 1 for 1:2 bonus)'}
                      {formData.event_type === 'RIGHTS' && 'Rights shares offered'}
                    </Form.Text>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Ratio Denominator *</Form.Label>
                    <Form.Control
                      type="number"
                      name="ratio_denominator"
                      value={formData.ratio_denominator}
                      onChange={handleFormChange}
                      placeholder="e.g., 1 for 2:1 split"
                      min="1"
                      required
                    />
                    <Form.Text className="text-muted">
                      {formData.event_type === 'SPLIT' && 'Old shares (e.g., 1 for 2:1 split)'}
                      {formData.event_type === 'BONUS' && 'Shares held (e.g., 2 for 1:2 bonus)'}
                      {formData.event_type === 'RIGHTS' && 'Shares held for entitlement'}
                    </Form.Text>
                  </Form.Group>
                </Col>
              </Row>
            )}

            {formData.event_type === 'DIVIDEND' && (
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Dividend Per Share *</Form.Label>
                    <Form.Control
                      type="number"
                      step="0.01"
                      name="dividend_per_share"
                      value={formData.dividend_per_share}
                      onChange={handleFormChange}
                      placeholder="e.g., 5.00"
                      required
                    />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Dividend Type *</Form.Label>
                    <Form.Select
                      name="dividend_type"
                      value={formData.dividend_type}
                      onChange={handleFormChange}
                      required
                    >
                      {DIVIDEND_TYPES.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
              </Row>
            )}

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Source</Form.Label>
                  <Form.Select
                    name="source"
                    value={formData.source}
                    onChange={handleFormChange}
                  >
                    <option value="MANUAL">Manual Entry</option>
                    <option value="NSE">NSE</option>
                    <option value="BSE">BSE</option>
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Description</Form.Label>
                  <Form.Control
                    type="text"
                    name="description"
                    value={formData.description}
                    onChange={handleFormChange}
                    placeholder="Optional description"
                  />
                </Form.Group>
              </Col>
            </Row>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={loading}>
              {loading ? 'Saving...' : (editingEvent ? 'Update' : 'Create')}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
};

export default CorporateEvents;
