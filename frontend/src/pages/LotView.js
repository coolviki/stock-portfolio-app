import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Form, Table, Badge, Button, Modal, Alert, Spinner, Accordion } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/apiService';
import { toast } from 'react-toastify';

const LotView = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [lots, setLots] = useState([]);
  const [securities, setSecurities] = useState([]);
  const [selectedLot, setSelectedLot] = useState(null);
  const [lotAdjustments, setLotAdjustments] = useState([]);
  const [lotAllocations, setLotAllocations] = useState([]);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [filters, setFilters] = useState({
    security_id: '',
    status: ''
  });

  useEffect(() => {
    if (user?.id) {
      loadSecurities();
      loadLots();
    }
  }, [user]);

  useEffect(() => {
    if (user?.id) {
      loadLots();
    }
  }, [filters]);

  const loadSecurities = async () => {
    try {
      const data = await apiService.getSecurities();
      setSecurities(data);
    } catch (error) {
      console.error('Error loading securities:', error);
    }
  };

  const loadLots = async () => {
    if (!user?.id) return;

    try {
      setLoading(true);
      const filterParams = {};
      if (filters.security_id) filterParams.security_id = filters.security_id;
      if (filters.status) filterParams.status = filters.status;

      const data = await apiService.getLots(user.id, filterParams);
      setLots(data);
    } catch (error) {
      console.error('Error loading lots:', error);
      toast.error('Failed to load lots');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const openLotDetail = async (lot) => {
    setSelectedLot(lot);
    setShowDetailModal(true);

    try {
      const [adjustments, allocations] = await Promise.all([
        apiService.getLotAdjustments(lot.id),
        apiService.getLotSaleAllocations(lot.id)
      ]);
      setLotAdjustments(adjustments);
      setLotAllocations(allocations);
    } catch (error) {
      console.error('Error loading lot details:', error);
      toast.error('Failed to load lot details');
    }
  };

  const closeDetailModal = () => {
    setShowDetailModal(false);
    setSelectedLot(null);
    setLotAdjustments([]);
    setLotAllocations([]);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(amount || 0);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-IN');
  };

  const formatQuantity = (qty) => {
    return qty ? qty.toFixed(2) : '0.00';
  };

  const getStatusBadge = (status) => {
    const colors = {
      OPEN: 'success',
      PARTIALLY_SOLD: 'warning',
      CLOSED: 'secondary'
    };
    const labels = {
      OPEN: 'Open',
      PARTIALLY_SOLD: 'Partial',
      CLOSED: 'Closed'
    };
    return <Badge bg={colors[status] || 'secondary'}>{labels[status] || status}</Badge>;
  };

  const hasAdjustments = (lot) => {
    return lot.original_cost_per_unit !== lot.adjusted_cost_per_unit ||
           lot.original_quantity !== lot.current_quantity;
  };

  const getSecurityName = (securityId) => {
    const security = securities.find(s => s.id === securityId);
    return security ? security.security_name : `Security ${securityId}`;
  };

  // Calculate summary stats
  const summaryStats = {
    totalLots: lots.length,
    openLots: lots.filter(l => l.status === 'OPEN').length,
    partialLots: lots.filter(l => l.status === 'PARTIALLY_SOLD').length,
    closedLots: lots.filter(l => l.status === 'CLOSED').length,
    totalOriginalCost: lots.reduce((sum, l) => sum + (l.original_cost_per_unit * l.remaining_quantity), 0),
    totalAdjustedCost: lots.reduce((sum, l) => sum + (l.adjusted_cost_per_unit * l.remaining_quantity), 0),
    totalQuantity: lots.reduce((sum, l) => sum + l.remaining_quantity, 0)
  };

  if (!user) {
    return (
      <Container className="mt-4">
        <Alert variant="warning">Please log in to view your lots.</Alert>
      </Container>
    );
  }

  return (
    <Container fluid className="mt-4">
      <Row>
        <Col>
          <h2 className="mb-4">Lot View</h2>

          {/* Summary Cards */}
          <Row className="mb-4">
            <Col md={3}>
              <Card className="h-100">
                <Card.Body className="text-center">
                  <h6 className="text-muted">Total Lots</h6>
                  <h4>{summaryStats.totalLots}</h4>
                  <small className="text-muted">
                    Open: {summaryStats.openLots} | Partial: {summaryStats.partialLots} | Closed: {summaryStats.closedLots}
                  </small>
                </Card.Body>
              </Card>
            </Col>
            <Col md={3}>
              <Card className="h-100">
                <Card.Body className="text-center">
                  <h6 className="text-muted">Remaining Quantity</h6>
                  <h4>{formatQuantity(summaryStats.totalQuantity)}</h4>
                </Card.Body>
              </Card>
            </Col>
            <Col md={3}>
              <Card className="h-100">
                <Card.Body className="text-center">
                  <h6 className="text-muted">Original Cost</h6>
                  <h4>{formatCurrency(summaryStats.totalOriginalCost)}</h4>
                </Card.Body>
              </Card>
            </Col>
            <Col md={3}>
              <Card className="h-100">
                <Card.Body className="text-center">
                  <h6 className="text-muted">Adjusted Cost</h6>
                  <h4>{formatCurrency(summaryStats.totalAdjustedCost)}</h4>
                  {summaryStats.totalOriginalCost !== summaryStats.totalAdjustedCost && (
                    <small className={summaryStats.totalAdjustedCost < summaryStats.totalOriginalCost ? 'text-success' : 'text-danger'}>
                      {summaryStats.totalAdjustedCost < summaryStats.totalOriginalCost ? '(Lower after adjustments)' : '(Higher after adjustments)'}
                    </small>
                  )}
                </Card.Body>
              </Card>
            </Col>
          </Row>

          {/* Filters */}
          <Card className="mb-4">
            <Card.Body>
              <Row>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Security</Form.Label>
                    <Form.Select
                      name="security_id"
                      value={filters.security_id}
                      onChange={handleFilterChange}
                    >
                      <option value="">All Securities</option>
                      {securities.map(s => (
                        <option key={s.id} value={s.id}>{s.security_name}</option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={4}>
                  <Form.Group>
                    <Form.Label>Status</Form.Label>
                    <Form.Select
                      name="status"
                      value={filters.status}
                      onChange={handleFilterChange}
                    >
                      <option value="">All Statuses</option>
                      <option value="OPEN">Open</option>
                      <option value="PARTIALLY_SOLD">Partially Sold</option>
                      <option value="CLOSED">Closed</option>
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={4} className="d-flex align-items-end">
                  <Button variant="outline-secondary" onClick={() => setFilters({ security_id: '', status: '' })}>
                    Clear Filters
                  </Button>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Lots Table */}
          <Card>
            <Card.Body>
              {loading ? (
                <div className="text-center py-4">
                  <Spinner animation="border" variant="primary" />
                </div>
              ) : lots.length === 0 ? (
                <Alert variant="info">
                  No lots found. Lots are created from BUY transactions.
                </Alert>
              ) : (
                <Table responsive hover>
                  <thead>
                    <tr>
                      <th>Security</th>
                      <th>Purchase Date</th>
                      <th className="text-end">Original Qty</th>
                      <th className="text-end">Current Qty</th>
                      <th className="text-end">Remaining</th>
                      <th className="text-end">Original Cost</th>
                      <th className="text-end">Adjusted Cost</th>
                      <th className="text-center">Status</th>
                      <th className="text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lots.map(lot => (
                      <tr key={lot.id}>
                        <td>
                          <strong>{lot.security?.security_name || getSecurityName(lot.security_id)}</strong>
                          {hasAdjustments(lot) && (
                            <Badge bg="info" className="ms-2" title="Has corporate event adjustments">
                              Adjusted
                            </Badge>
                          )}
                        </td>
                        <td>{formatDate(lot.purchase_date)}</td>
                        <td className="text-end">{formatQuantity(lot.original_quantity)}</td>
                        <td className="text-end">
                          {formatQuantity(lot.current_quantity)}
                          {lot.current_quantity !== lot.original_quantity && (
                            <small className="text-muted d-block">
                              ({lot.current_quantity > lot.original_quantity ? '+' : ''}{formatQuantity(lot.current_quantity - lot.original_quantity)})
                            </small>
                          )}
                        </td>
                        <td className="text-end">{formatQuantity(lot.remaining_quantity)}</td>
                        <td className="text-end">{formatCurrency(lot.original_cost_per_unit)}</td>
                        <td className="text-end">
                          {formatCurrency(lot.adjusted_cost_per_unit)}
                          {lot.adjusted_cost_per_unit !== lot.original_cost_per_unit && (
                            <small className={`d-block ${lot.adjusted_cost_per_unit < lot.original_cost_per_unit ? 'text-success' : 'text-danger'}`}>
                              ({lot.adjusted_cost_per_unit < lot.original_cost_per_unit ? '-' : '+'}
                              {formatCurrency(Math.abs(lot.adjusted_cost_per_unit - lot.original_cost_per_unit))})
                            </small>
                          )}
                        </td>
                        <td className="text-center">{getStatusBadge(lot.status)}</td>
                        <td className="text-center">
                          <Button
                            variant="outline-primary"
                            size="sm"
                            onClick={() => openLotDetail(lot)}
                          >
                            Details
                          </Button>
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

      {/* Lot Detail Modal */}
      <Modal show={showDetailModal} onHide={closeDetailModal} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            Lot Details
            {selectedLot && ` - ${selectedLot.security?.security_name || ''}`}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedLot && (
            <>
              {/* Lot Summary */}
              <Card className="mb-3">
                <Card.Header>Lot Information</Card.Header>
                <Card.Body>
                  <Row>
                    <Col md={6}>
                      <p><strong>Purchase Date:</strong> {formatDate(selectedLot.purchase_date)}</p>
                      <p><strong>Exchange:</strong> {selectedLot.exchange || '-'}</p>
                      <p><strong>Status:</strong> {getStatusBadge(selectedLot.status)}</p>
                    </Col>
                    <Col md={6}>
                      <p><strong>Broker Fees:</strong> {formatCurrency(selectedLot.broker_fees)}</p>
                      <p><strong>Taxes:</strong> {formatCurrency(selectedLot.taxes)}</p>
                    </Col>
                  </Row>

                  <Table bordered size="sm" className="mt-3">
                    <thead>
                      <tr>
                        <th></th>
                        <th className="text-end">Original</th>
                        <th className="text-end">Current/Adjusted</th>
                        <th className="text-end">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Quantity</td>
                        <td className="text-end">{formatQuantity(selectedLot.original_quantity)}</td>
                        <td className="text-end">{formatQuantity(selectedLot.current_quantity)}</td>
                        <td className="text-end">
                          {selectedLot.current_quantity !== selectedLot.original_quantity ? (
                            <span className={selectedLot.current_quantity > selectedLot.original_quantity ? 'text-success' : 'text-danger'}>
                              {selectedLot.current_quantity > selectedLot.original_quantity ? '+' : ''}
                              {formatQuantity(selectedLot.current_quantity - selectedLot.original_quantity)}
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td>Cost Per Unit</td>
                        <td className="text-end">{formatCurrency(selectedLot.original_cost_per_unit)}</td>
                        <td className="text-end">{formatCurrency(selectedLot.adjusted_cost_per_unit)}</td>
                        <td className="text-end">
                          {selectedLot.adjusted_cost_per_unit !== selectedLot.original_cost_per_unit ? (
                            <span className={selectedLot.adjusted_cost_per_unit < selectedLot.original_cost_per_unit ? 'text-success' : 'text-danger'}>
                              {selectedLot.adjusted_cost_per_unit < selectedLot.original_cost_per_unit ? '-' : '+'}
                              {formatCurrency(Math.abs(selectedLot.adjusted_cost_per_unit - selectedLot.original_cost_per_unit))}
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td>Total Cost</td>
                        <td className="text-end">{formatCurrency(selectedLot.original_total_cost)}</td>
                        <td className="text-end">{formatCurrency(selectedLot.adjusted_total_cost)}</td>
                        <td className="text-end">
                          {selectedLot.adjusted_total_cost !== selectedLot.original_total_cost ? (
                            <span className={selectedLot.adjusted_total_cost < selectedLot.original_total_cost ? 'text-success' : 'text-danger'}>
                              {selectedLot.adjusted_total_cost < selectedLot.original_total_cost ? '-' : '+'}
                              {formatCurrency(Math.abs(selectedLot.adjusted_total_cost - selectedLot.original_total_cost))}
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td>Remaining Quantity</td>
                        <td className="text-end" colSpan="3">{formatQuantity(selectedLot.remaining_quantity)}</td>
                      </tr>
                    </tbody>
                  </Table>
                </Card.Body>
              </Card>

              {/* Adjustments and Allocations */}
              <Accordion defaultActiveKey="0">
                <Accordion.Item eventKey="0">
                  <Accordion.Header>
                    Adjustment History ({lotAdjustments.length})
                  </Accordion.Header>
                  <Accordion.Body>
                    {lotAdjustments.length === 0 ? (
                      <Alert variant="info" className="mb-0">
                        No adjustments for this lot.
                      </Alert>
                    ) : (
                      <Table size="sm" responsive>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Type</th>
                            <th className="text-end">Qty Before</th>
                            <th className="text-end">Qty After</th>
                            <th className="text-end">Cost Before</th>
                            <th className="text-end">Cost After</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lotAdjustments.map(adj => (
                            <tr key={adj.id}>
                              <td>{formatDate(adj.created_at)}</td>
                              <td>
                                <Badge bg="info">{adj.adjustment_type}</Badge>
                                {adj.adjustment_reason && (
                                  <small className="text-muted d-block">{adj.adjustment_reason}</small>
                                )}
                              </td>
                              <td className="text-end">{formatQuantity(adj.quantity_before)}</td>
                              <td className="text-end">{formatQuantity(adj.quantity_after)}</td>
                              <td className="text-end">{formatCurrency(adj.cost_per_unit_before)}</td>
                              <td className="text-end">{formatCurrency(adj.cost_per_unit_after)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                  </Accordion.Body>
                </Accordion.Item>

                <Accordion.Item eventKey="1">
                  <Accordion.Header>
                    Sale Allocations ({lotAllocations.length})
                  </Accordion.Header>
                  <Accordion.Body>
                    {lotAllocations.length === 0 ? (
                      <Alert variant="info" className="mb-0">
                        No sales allocated from this lot.
                      </Alert>
                    ) : (
                      <Table size="sm" responsive>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th className="text-end">Qty Sold</th>
                            <th className="text-end">Cost Basis</th>
                            <th className="text-end">Sale Price</th>
                            <th className="text-end">Gain/Loss</th>
                            <th className="text-center">Type</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lotAllocations.map(alloc => (
                            <tr key={alloc.id}>
                              <td>{formatDate(alloc.created_at)}</td>
                              <td className="text-end">{formatQuantity(alloc.quantity_sold)}</td>
                              <td className="text-end">{formatCurrency(alloc.cost_basis_per_unit)}</td>
                              <td className="text-end">{formatCurrency(alloc.sale_price_per_unit)}</td>
                              <td className="text-end">
                                <span className={alloc.realized_gain_loss >= 0 ? 'text-success' : 'text-danger'}>
                                  {formatCurrency(alloc.realized_gain_loss)}
                                </span>
                              </td>
                              <td className="text-center">
                                <Badge bg={alloc.is_long_term ? 'info' : 'warning'}>
                                  {alloc.is_long_term ? 'LTCG' : 'STCG'}
                                </Badge>
                                <small className="d-block text-muted">{alloc.holding_period_days} days</small>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                  </Accordion.Body>
                </Accordion.Item>
              </Accordion>
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={closeDetailModal}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default LotView;
