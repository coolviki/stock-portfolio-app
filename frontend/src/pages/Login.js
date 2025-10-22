import React, { useState } from 'react';
import { Container, Row, Col, Card, Form, Button, Alert } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'react-toastify';

const Login = ({ authConfig }) => {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(username);
      toast.success('Login successful!');
    } catch (error) {
      setError(error.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container fluid className="min-vh-100 d-flex align-items-center justify-content-center bg-light">
      <Row className="w-100 justify-content-center">
        <Col md={6} lg={4}>
          <Card className="shadow-lg border-0">
            <Card.Body className="p-5">
              <div className="text-center mb-4">
                <h2 className="text-primary mb-2">📈 Stock Portfolio</h2>
                <p className="text-muted">Enter your username to continue</p>
              </div>

              {error && <Alert variant="danger">{error}</Alert>}

              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-4">
                  <Form.Label>Username</Form.Label>
                  <Form.Control
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    placeholder="Enter your username"
                  />
                  <Form.Text className="text-muted">
                    If this is your first time, a new account will be created automatically.
                  </Form.Text>
                </Form.Group>

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-100 mb-3"
                  disabled={loading || !username.trim()}
                >
                  {loading ? 'Signing in...' : 'Continue'}
                </Button>
              </Form>

              <div className="text-center mt-3">
                <p className="text-muted">
                  Don't have an account?{' '}
                  <Link to="/register" className="text-primary text-decoration-none">
                    Sign up here
                  </Link>
                </p>
                {!authConfig?.requiresFirebase && (
                  <p className="text-muted small">
                    Or{' '}
                    <Link to="/firebase-auth" className="text-primary text-decoration-none">
                      sign in with Google
                    </Link>
                  </p>
                )}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default Login;