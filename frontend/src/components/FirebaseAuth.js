import React, { useState } from 'react';
import { Card, Alert, Button, Spinner } from 'react-bootstrap';
import { signInWithPopup, signInWithRedirect, getRedirectResult, signOut } from 'firebase/auth';
import { getAuthInstance, getGoogleProviderInstance, isFirebaseAvailable } from '../config/firebase';
import { useAuth } from '../context/AuthContext';
import { authService } from '../services/authService';
import { toast } from 'react-toastify';
import { useNavigate } from 'react-router-dom';

const FirebaseAuth = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [firebaseAvailable, setFirebaseAvailable] = useState(false);
  const [checkingFirebase, setCheckingFirebase] = useState(true);

  // Check Firebase availability and handle redirect result on component mount
  React.useEffect(() => {
    const initializeComponent = async () => {
      try {
        setCheckingFirebase(true);
        const available = await isFirebaseAvailable();
        setFirebaseAvailable(available);
        
        if (available) {
          const auth = await getAuthInstance();
          if (auth) {
            const result = await getRedirectResult(auth);
            if (result && result.user) {
              await handleFirebaseUser(result.user);
            }
          }
        }
      } catch (error) {
        console.error('Firebase initialization error:', error);
        setError('Failed to initialize authentication. Please refresh the page.');
      } finally {
        setCheckingFirebase(false);
      }
    };

    initializeComponent();
  }, []);

  const handleFirebaseUser = async (firebaseUser) => {
    try {
      // Get the Firebase ID token
      const idToken = await firebaseUser.getIdToken();
      
      // Prepare user data
      const userData = {
        firebase_uid: firebaseUser.uid,
        email: firebaseUser.email,
        name: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
        picture: firebaseUser.photoURL || '',
        email_verified: firebaseUser.emailVerified,
        id_token: idToken
      };

      // Send to backend for authentication/user creation
      const response = await authService.firebaseLogin(userData);
      
      if (response.user_data) {
        login(response.user_data);
        toast.success(`Welcome ${userData.name}!`);
      } else {
        throw new Error('Failed to authenticate with backend');
      }
    } catch (error) {
      console.error('Firebase user handling error:', error);
      setError('Authentication failed: ' + (error.message || 'Unknown error'));
      
      // Sign out from Firebase if backend auth failed
      try {
        const auth = await getAuthInstance();
        if (auth) {
          await signOut(auth);
        }
      } catch (signOutError) {
        console.error('Sign out error:', signOutError);
      }
    }
  };

  const handleGoogleSignIn = async () => {
    if (!firebaseAvailable) {
      setError('Firebase authentication is not available. Redirecting to alternative login...');
      setTimeout(() => navigate('/login'), 2000);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const auth = await getAuthInstance();
      const googleProvider = await getGoogleProviderInstance();
      
      if (!auth || !googleProvider) {
        throw new Error('Firebase services not available');
      }

      // Try popup first, fallback to redirect on mobile
      let result;
      try {
        result = await signInWithPopup(auth, googleProvider);
      } catch (popupError) {
        if (popupError.code === 'auth/popup-blocked' || 
            popupError.code === 'auth/popup-closed-by-user' ||
            popupError.code === 'auth/cancelled-popup-request') {
          // Fallback to redirect
          await signInWithRedirect(auth, googleProvider);
          return; // The redirect result will be handled in useEffect
        }
        throw popupError;
      }

      if (result && result.user) {
        await handleFirebaseUser(result.user);
      }
    } catch (error) {
      console.error('Google Sign-In Error:', error);
      
      let errorMessage = 'Sign-in failed. Please try again.';
      
      switch (error.code) {
        case 'auth/popup-blocked':
          errorMessage = 'Popup was blocked. Please allow popups for this site or try again.';
          break;
        case 'auth/popup-closed-by-user':
          errorMessage = 'Sign-in was cancelled. Please try again.';
          break;
        case 'auth/account-exists-with-different-credential':
          errorMessage = 'An account already exists with this email. Please sign in with your original method.';
          break;
        case 'auth/network-request-failed':
          errorMessage = 'Network error. Please check your connection and try again.';
          break;
        default:
          errorMessage = error.message || 'Sign-in failed. Please try again.';
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleFallbackLogin = () => {
    navigate('/login');
  };

  return (
    <div className="min-vh-100 d-flex" 
         style={{background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}}>
      
      {/* Left Side - Hero Section */}
      <div className="col-md-7 d-none d-md-flex flex-column justify-content-center align-items-center text-white p-5">
        <div className="text-center">
          <div className="mb-4">
            <span style={{fontSize: '5rem', textShadow: '2px 2px 4px rgba(0,0,0,0.3)'}}>📈</span>
          </div>
          <h1 className="display-3 fw-bold mb-4" style={{textShadow: '2px 2px 4px rgba(0,0,0,0.3)'}}>
            Stock Portfolio
          </h1>
          <h3 className="mb-4" style={{textShadow: '1px 1px 2px rgba(0,0,0,0.3)'}}>
            Professional Investment Management
          </h3>
          <p className="lead mb-5" style={{textShadow: '1px 1px 2px rgba(0,0,0,0.3)'}}>
            Track your investments, analyze performance, and make data-driven decisions with our comprehensive portfolio management platform.
          </p>
          
          {/* Feature Highlights */}
          <div className="row text-center mt-4">
            <div className="col-md-4 mb-3">
              <div className="bg-white bg-opacity-20 p-4 rounded-3 backdrop-blur h-100 d-flex flex-column justify-content-center" style={{minHeight: '160px'}}>
                <div style={{fontSize: '4rem'}} className="mb-3">📊</div>
                <h5 className="fw-bold mb-2" style={{fontSize: '1.1rem'}}>Advanced Analytics</h5>
                <p className="small mb-0" style={{fontSize: '0.9rem', lineHeight: '1.3'}}>Real-time portfolio performance tracking</p>
              </div>
            </div>
            <div className="col-md-4 mb-3">
              <div className="bg-white bg-opacity-20 p-4 rounded-3 backdrop-blur h-100 d-flex flex-column justify-content-center" style={{minHeight: '160px'}}>
                <div style={{fontSize: '4rem'}} className="mb-3">📄</div>
                <h5 className="fw-bold mb-2" style={{fontSize: '1.1rem'}}>PDF Import</h5>
                <p className="small mb-0" style={{fontSize: '0.9rem', lineHeight: '1.3'}}>Automated contract note processing</p>
              </div>
            </div>
            <div className="col-md-4 mb-3">
              <div className="bg-white bg-opacity-20 p-4 rounded-3 backdrop-blur h-100 d-flex flex-column justify-content-center" style={{minHeight: '160px'}}>
                <div style={{fontSize: '4rem'}} className="mb-3">💰</div>
                <h5 className="fw-bold mb-2" style={{fontSize: '1.1rem'}}>Tax Optimization</h5>
                <p className="small mb-0" style={{fontSize: '0.9rem', lineHeight: '1.3'}}>Capital gains calculation & reporting</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Side - Login Panel */}
      <div className="col-md-5 col-12 d-flex align-items-center justify-content-center p-4">
        <div className="w-100" style={{maxWidth: '450px'}}>
          <Card className="shadow-lg border-0" style={{borderRadius: '20px', backdropFilter: 'blur(10px)', backgroundColor: 'rgba(255,255,255,0.95)'}}>
            <Card.Body className="p-5">
              
              {/* Mobile Header (only visible on small screens) */}
              <div className="d-md-none text-center mb-4">
                <span style={{fontSize: '3rem', color: '#667eea'}}>📈</span>
                <h2 className="fw-bold text-primary mt-2 mb-3">Stock Portfolio</h2>
              </div>

              <div className="text-center mb-4">
                <h3 className="fw-bold text-dark mb-3">Welcome Back</h3>
                <p className="text-muted">Sign in to access your investment dashboard</p>
              </div>

              {checkingFirebase && (
                <Alert variant="info" className="mb-4">
                  <i className="bi bi-info-circle me-2"></i>
                  <strong>Initializing authentication...</strong>
                  <br />
                  <small>Please wait while we set up your login options.</small>
                </Alert>
              )}

              {!checkingFirebase && !firebaseAvailable && (
                <Alert variant="warning" className="mb-4">
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  <strong>Firebase authentication is not configured.</strong>
                  <br />
                  <small>You can still access the application using the alternative login method.</small>
                </Alert>
              )}

              {error && (
                <Alert variant="danger" className="mb-4">
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  {error}
                </Alert>
              )}

              {!checkingFirebase && (
                <div className="mb-4">
                  <Button
                    variant={firebaseAvailable ? "outline-primary" : "secondary"}
                    size="lg"
                    onClick={handleGoogleSignIn}
                    disabled={loading || !firebaseAvailable}
                    className="w-100 d-flex align-items-center justify-content-center py-3"
                    style={{borderRadius: '12px', border: firebaseAvailable ? '2px solid #667eea' : '2px solid #6c757d', fontSize: '1.1rem'}}
                  >
                    {loading ? (
                      <>
                        <Spinner animation="border" size="sm" className="me-3" />
                        Signing you in...
                      </>
                    ) : (
                      <>
                        <svg className="me-3" width="24" height="24" viewBox="0 0 24 24">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                        {firebaseAvailable ? 'Continue with Google' : 'Google Sign-in Unavailable'}
                      </>
                    )}
                  </Button>
                </div>
              )}

              {!checkingFirebase && !firebaseAvailable && (
                <div className="mb-4">
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={handleFallbackLogin}
                    className="w-100 d-flex align-items-center justify-content-center py-3"
                    style={{borderRadius: '12px', fontSize: '1.1rem'}}
                  >
                    <i className="bi bi-box-arrow-in-right me-3"></i>
                    Continue with Alternative Login
                  </Button>
                </div>
              )}

              <div className="text-center mb-4">
                <small className="text-muted d-flex align-items-center justify-content-center">
                  <i className="bi bi-shield-check me-2"></i>
                  {!checkingFirebase && firebaseAvailable ? 'Secured by Firebase Authentication' : 'Secure Authentication Available'}
                </small>
              </div>

              {/* Benefits Section */}
              <div className="bg-light p-4 rounded-3 mb-4">
                <h6 className="fw-bold text-dark mb-3 text-center">Why Choose Our Platform?</h6>
                <div className="small text-muted">
                  <div className="d-flex align-items-center mb-2">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                    Real-time portfolio tracking & analytics
                  </div>
                  <div className="d-flex align-items-center mb-2">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                    Automated PDF contract note processing
                  </div>
                  <div className="d-flex align-items-center mb-2">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                    Tax-optimized capital gains reporting
                  </div>
                  <div className="d-flex align-items-center">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                    Secure cloud-based data storage
                  </div>
                </div>
              </div>

              <div className="text-center">
                <small className="text-muted">
                  By signing in, you agree to our Terms of Service and Privacy Policy
                </small>
              </div>
            </Card.Body>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default FirebaseAuth;