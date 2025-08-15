import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Badge, Button, Form, Alert, Modal, Table, Spinner } from 'react-bootstrap';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

const PriceProviders = () => {
    const { user } = useAuth();
    const [providersStatus, setProvidersStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [configModal, setConfigModal] = useState({ show: false, provider: null });
    const [testModal, setTestModal] = useState({ show: false, provider: null });
    const [testResults, setTestResults] = useState(null);
    const [formData, setFormData] = useState({
        enabled: true,
        priority: 1,
        api_key: '',
        timeout: 10
    });

    useEffect(() => {
        fetchProvidersStatus();
    }, []);

    const fetchProvidersStatus = async () => {
        try {
            const response = await fetch(`http://localhost:8000/admin/price-providers/status?user_email=${encodeURIComponent(user.email)}`);
            if (response.ok) {
                const data = await response.json();
                setProvidersStatus(data);
            } else {
                toast.error('Failed to fetch provider status');
            }
        } catch (error) {
            console.error('Error fetching provider status:', error);
            toast.error('Error fetching provider status');
        } finally {
            setLoading(false);
        }
    };

    const handleConfigProvider = (providerName) => {
        const provider = providersStatus.providers[providerName];
        setFormData({
            enabled: provider.enabled,
            priority: provider.priority,
            api_key: '',
            timeout: providersStatus.configuration.providers[providerName]?.config?.timeout || 10
        });
        setConfigModal({ show: true, provider: providerName });
    };

    const handleTestProvider = (providerName) => {
        setTestModal({ show: true, provider: providerName });
        setTestResults(null);
    };

    const submitConfiguration = async () => {
        try {
            const formDataObj = new FormData();
            formDataObj.append('provider_name', configModal.provider);
            formDataObj.append('enabled', formData.enabled);
            formDataObj.append('priority', formData.priority);
            formDataObj.append('api_key', formData.api_key);
            formDataObj.append('timeout', formData.timeout);
            formDataObj.append('user_email', user.email);

            const response = await fetch('http://localhost:8000/admin/price-providers/configure', {
                method: 'POST',
                body: formDataObj
            });

            if (response.ok) {
                const result = await response.json();
                toast.success(`Provider ${configModal.provider} configured successfully`);
                setConfigModal({ show: false, provider: null });
                fetchProvidersStatus();
            } else {
                toast.error('Failed to configure provider');
            }
        } catch (error) {
            console.error('Error configuring provider:', error);
            toast.error('Error configuring provider');
        }
    };

    const runProviderTest = async (symbol = 'RELIANCE') => {
        try {
            const formDataObj = new FormData();
            formDataObj.append('provider_name', testModal.provider);
            formDataObj.append('test_symbol', symbol);
            formDataObj.append('user_email', user.email);

            const response = await fetch('http://localhost:8000/admin/price-providers/test', {
                method: 'POST',
                body: formDataObj
            });

            if (response.ok) {
                const result = await response.json();
                setTestResults(result);
            } else {
                toast.error('Failed to test provider');
            }
        } catch (error) {
            console.error('Error testing provider:', error);
            toast.error('Error testing provider');
        }
    };

    const resetConfiguration = async () => {
        if (window.confirm('Are you sure you want to reset all provider configurations to defaults?')) {
            try {
                const formDataObj = new FormData();
                formDataObj.append('user_email', user.email);

                const response = await fetch('http://localhost:8000/admin/price-providers/reset', {
                    method: 'POST',
                    body: formDataObj
                });

                if (response.ok) {
                    toast.success('Configuration reset to defaults');
                    fetchProvidersStatus();
                } else {
                    toast.error('Failed to reset configuration');
                }
            } catch (error) {
                console.error('Error resetting configuration:', error);
                toast.error('Error resetting configuration');
            }
        }
    };

    const getStatusBadge = (status) => {
        const statusMap = {
            'available': { variant: 'success', text: 'Available' },
            'unavailable': { variant: 'danger', text: 'Unavailable' },
            'error': { variant: 'warning', text: 'Error' },
            'rate_limited': { variant: 'info', text: 'Rate Limited' }
        };
        const config = statusMap[status] || { variant: 'secondary', text: status };
        return <Badge bg={config.variant}>{config.text}</Badge>;
    };

    const getPriorityBadge = (priority) => {
        const priorityMap = {
            1: { variant: 'primary', text: 'Primary' },
            2: { variant: 'secondary', text: 'Secondary' },
            3: { variant: 'info', text: 'Tertiary' }
        };
        const config = priorityMap[priority] || { variant: 'dark', text: `Priority ${priority}` };
        return <Badge bg={config.variant}>{config.text}</Badge>;
    };

    if (loading) {
        return (
            <Container className="mt-4">
                <div className="text-center">
                    <Spinner animation="border" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </Spinner>
                </div>
            </Container>
        );
    }

    return (
        <Container fluid className="mt-4">
            <Row>
                <Col>
                    <div className="d-flex justify-content-between align-items-center mb-4">
                        <h2>
                            <i className="bi bi-gear-fill me-2"></i>
                            Price Providers Management
                        </h2>
                        <Button variant="outline-danger" onClick={resetConfiguration}>
                            <i className="bi bi-arrow-clockwise me-2"></i>
                            Reset to Defaults
                        </Button>
                    </div>

                    {providersStatus && (
                        <>
                            <Row className="mb-4">
                                {Object.entries(providersStatus.providers).map(([name, provider]) => (
                                    <Col md={6} key={name} className="mb-3">
                                        <Card className={`h-100 ${!provider.enabled ? 'opacity-75' : ''}`}>
                                            <Card.Header className="d-flex justify-content-between align-items-center">
                                                <div>
                                                    <h5 className="mb-0">
                                                        {provider.name}
                                                        {provider.enabled && <i className="bi bi-check-circle-fill text-success ms-2"></i>}
                                                        {!provider.enabled && <i className="bi bi-x-circle-fill text-danger ms-2"></i>}
                                                    </h5>
                                                </div>
                                                <div>
                                                    {getStatusBadge(provider.status)}
                                                    <span className="ms-2">{getPriorityBadge(provider.priority)}</span>
                                                </div>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    <Col sm={6}>
                                                        <strong>Status:</strong> {getStatusBadge(provider.status)}
                                                    </Col>
                                                    <Col sm={6}>
                                                        <strong>Enabled:</strong> {provider.enabled ? 'Yes' : 'No'}
                                                    </Col>
                                                </Row>
                                                <Row className="mt-2">
                                                    <Col sm={6}>
                                                        <strong>Priority:</strong> {provider.priority}
                                                    </Col>
                                                    <Col sm={6}>
                                                        <strong>Errors:</strong> {provider.error_count}/{provider.max_errors}
                                                    </Col>
                                                </Row>
                                                <Row className="mt-2">
                                                    <Col sm={6}>
                                                        <strong>API Key:</strong> {provider.api_key_configured ? '✓' : '✗'}
                                                    </Col>
                                                    <Col sm={6}>
                                                        <strong>Markets:</strong> {provider.supported_markets?.join(', ')}
                                                    </Col>
                                                </Row>
                                                {provider.rate_limits && (
                                                    <Row className="mt-2">
                                                        <Col>
                                                            <small className="text-muted">
                                                                <strong>Rate Limits:</strong> {provider.rate_limits}
                                                            </small>
                                                        </Col>
                                                    </Row>
                                                )}
                                            </Card.Body>
                                            <Card.Footer>
                                                <Button 
                                                    variant="primary" 
                                                    size="sm" 
                                                    className="me-2"
                                                    onClick={() => handleConfigProvider(name)}
                                                >
                                                    <i className="bi bi-gear me-1"></i>Configure
                                                </Button>
                                                <Button 
                                                    variant="outline-secondary" 
                                                    size="sm"
                                                    onClick={() => handleTestProvider(name)}
                                                >
                                                    <i className="bi bi-play me-1"></i>Test
                                                </Button>
                                            </Card.Footer>
                                        </Card>
                                    </Col>
                                ))}
                            </Row>

                            <Card>
                                <Card.Header>
                                    <h5 className="mb-0">
                                        <i className="bi bi-list-ol me-2"></i>
                                        Provider Priority Order
                                    </h5>
                                </Card.Header>
                                <Card.Body>
                                    <Table responsive>
                                        <thead>
                                            <tr>
                                                <th>Priority</th>
                                                <th>Provider</th>
                                                <th>Status</th>
                                                <th>Enabled</th>
                                                <th>API Key</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {Object.entries(providersStatus.providers)
                                                .sort(([,a], [,b]) => a.priority - b.priority)
                                                .map(([name, provider]) => (
                                                <tr key={name}>
                                                    <td>{getPriorityBadge(provider.priority)}</td>
                                                    <td>
                                                        <strong>{provider.name}</strong>
                                                        <br />
                                                        <small className="text-muted">{provider.supported_markets?.join(', ')}</small>
                                                    </td>
                                                    <td>{getStatusBadge(provider.status)}</td>
                                                    <td>{provider.enabled ? '✓' : '✗'}</td>
                                                    <td>{provider.api_key_configured ? '✓' : '✗'}</td>
                                                    <td>
                                                        <Button 
                                                            variant="outline-primary" 
                                                            size="sm"
                                                            onClick={() => handleConfigProvider(name)}
                                                        >
                                                            Configure
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </Table>
                                </Card.Body>
                            </Card>
                        </>
                    )}
                </Col>
            </Row>

            {/* Configuration Modal */}
            <Modal show={configModal.show} onHide={() => setConfigModal({ show: false, provider: null })}>
                <Modal.Header closeButton>
                    <Modal.Title>Configure {configModal.provider}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Form>
                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Check
                                        type="switch"
                                        id="enabled-switch"
                                        label="Enabled"
                                        checked={formData.enabled}
                                        onChange={(e) => setFormData({...formData, enabled: e.target.checked})}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Priority</Form.Label>
                                    <Form.Select
                                        value={formData.priority}
                                        onChange={(e) => setFormData({...formData, priority: parseInt(e.target.value)})}
                                    >
                                        <option value={1}>1 (Primary)</option>
                                        <option value={2}>2 (Secondary)</option>
                                        <option value={3}>3 (Tertiary)</option>
                                    </Form.Select>
                                </Form.Group>
                            </Col>
                        </Row>
                        <Form.Group className="mb-3">
                            <Form.Label>API Key</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="Enter API key (leave blank to keep current)"
                                value={formData.api_key}
                                onChange={(e) => setFormData({...formData, api_key: e.target.value})}
                            />
                            <Form.Text className="text-muted">
                                Leave blank to keep the current API key unchanged.
                            </Form.Text>
                        </Form.Group>
                        <Form.Group className="mb-3">
                            <Form.Label>Timeout (seconds)</Form.Label>
                            <Form.Control
                                type="number"
                                min="5"
                                max="60"
                                value={formData.timeout}
                                onChange={(e) => setFormData({...formData, timeout: parseInt(e.target.value)})}
                            />
                        </Form.Group>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfigModal({ show: false, provider: null })}>
                        Cancel
                    </Button>
                    <Button variant="primary" onClick={submitConfiguration}>
                        Save Configuration
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Test Modal */}
            <Modal show={testModal.show} onHide={() => setTestModal({ show: false, provider: null })}>
                <Modal.Header closeButton>
                    <Modal.Title>Test {testModal.provider}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Form.Group className="mb-3">
                        <Form.Label>Test Symbol</Form.Label>
                        <Form.Control
                            type="text"
                            placeholder="Enter stock symbol (e.g., RELIANCE)"
                            defaultValue="RELIANCE"
                            id="test-symbol"
                        />
                    </Form.Group>
                    <Button 
                        variant="primary" 
                        onClick={() => runProviderTest(document.getElementById('test-symbol').value)}
                        className="mb-3"
                    >
                        Run Test
                    </Button>

                    {testResults && (
                        <Alert variant={testResults.success ? 'success' : 'danger'}>
                            <strong>Test Results:</strong>
                            <ul className="mb-0 mt-2">
                                <li><strong>Provider:</strong> {testResults.provider}</li>
                                <li><strong>Symbol:</strong> {testResults.symbol}</li>
                                <li><strong>Success:</strong> {testResults.success ? 'Yes' : 'No'}</li>
                                {testResults.price && <li><strong>Price:</strong> {testResults.price}</li>}
                                {testResults.response_time_seconds && (
                                    <li><strong>Response Time:</strong> {testResults.response_time_seconds.toFixed(2)}s</li>
                                )}
                                {testResults.error && <li><strong>Error:</strong> {testResults.error}</li>}
                                <li><strong>Provider Status:</strong> {testResults.provider_status}</li>
                            </ul>
                        </Alert>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setTestModal({ show: false, provider: null })}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </Container>
    );
};

export default PriceProviders;