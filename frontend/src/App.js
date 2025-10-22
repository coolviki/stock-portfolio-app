import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import { useAuth } from './context/AuthContext';
import { authService } from './services/authService';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import ErrorBoundary from './components/ErrorBoundary';
import FirebaseAuth from './components/FirebaseAuth';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Upload from './pages/Upload';
import ManualEntry from './pages/ManualEntry';
import ManageUsers from './pages/ManageUsers';
import Admin from './pages/Admin';
import CapitalGains from './pages/CapitalGains';
import SecurityMaster from './pages/SecurityMaster';
import PriceProviders from './pages/PriceProviders';

function App() {
  const { user, loading } = useAuth();
  const [authConfig, setAuthConfig] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);

  useEffect(() => {
    // Fetch auth configuration from backend
    const fetchAuthConfig = async () => {
      try {
        const config = await authService.getAuthConfig();
        setAuthConfig(config);
      } catch (error) {
        console.error('Error fetching auth config:', error);
        // Default to simple auth if config fetch fails
        setAuthConfig({ authMode: 'simple', allowsSimpleLogin: true, requiresFirebase: false });
      } finally {
        setConfigLoading(false);
      }
    };

    fetchAuthConfig();
  }, []);

  if (loading || configLoading) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    // Determine default route based on auth mode
    const defaultRoute = authConfig?.requiresFirebase ? '/firebase-auth' : '/login';

    return (
      <div className="App">
        <Routes>
          {authConfig?.allowsSimpleLogin && (
            <>
              <Route path="/login" element={<Login authConfig={authConfig} />} />
              <Route path="/register" element={<Register authConfig={authConfig} />} />
            </>
          )}
          <Route path="/firebase-auth" element={<FirebaseAuth />} />
          <Route path="*" element={<Navigate to={defaultRoute} />} />
        </Routes>
        <ToastContainer position="top-right" autoClose={3000} />
      </div>
    );
  }

  return (
    <div className="App">
      <div className="d-flex">
        <Sidebar />
        <div className="flex-grow-1">
          <Navbar />
          <div className="main-content">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/transactions" element={<Transactions />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/manual-entry" element={<ManualEntry />} />
                <Route path="/capital-gains" element={<CapitalGains />} />
                <Route path="/security-master" element={<SecurityMaster />} />
                <Route path="/users" element={<ManageUsers />} />
                <Route path="/price-providers" element={<PriceProviders />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="*" element={<Navigate to="/dashboard" />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </div>
      </div>
      <ToastContainer position="top-right" autoClose={3000} />
    </div>
  );
}

export default App;