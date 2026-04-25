import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import { useAuth } from './context/AuthContext';
import { authService } from './services/authService';
import { initGA, trackPageView, setUserProperties } from './utils/analytics';
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
import DBAdmin from './pages/DBAdmin';
import CapitalGains from './pages/CapitalGains';
import SecurityMaster from './pages/SecurityMaster';
import PriceProviders from './pages/PriceProviders';
import CorporateEvents from './pages/CorporateEvents';
import LotView from './pages/LotView';
import CorporateEventsTicker from './components/CorporateEventsTicker';
import Reports from './pages/Reports';
import BenchmarkComparison from './pages/BenchmarkComparison';

function App() {
  const { user, loading, isAdmin } = useAuth();
  const [authConfig, setAuthConfig] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen);
  const closeSidebar = () => setSidebarOpen(false);

  // Initialize Google Analytics on app load
  useEffect(() => {
    initGA();
  }, []);

  // Track page views on route change
  useEffect(() => {
    const pageTitles = {
      '/': 'Dashboard',
      '/dashboard': 'Dashboard',
      '/transactions': 'Transactions',
      '/upload': 'Upload Contract Notes',
      '/manual-entry': 'Manual Entry',
      '/lots': 'Lot View',
      '/capital-gains': 'Capital Gains',
      '/reports': 'Reports',
      '/benchmark-comparison': 'Benchmark Comparison',
      '/corporate-events': 'Corporate Events',
      '/security-master': 'Security Master',
      '/users': 'Manage Users',
      '/price-providers': 'Price Providers',
      '/admin': 'Admin',
      '/db-admin': 'DB Admin',
      '/login': 'Login',
      '/register': 'Register',
      '/firebase-auth': 'Firebase Auth'
    };
    const pageTitle = pageTitles[location.pathname] || 'Stock Portfolio';
    trackPageView(location.pathname, pageTitle);
  }, [location]);

  // Set user properties when user logs in
  useEffect(() => {
    if (user) {
      setUserProperties(user.id, isAdmin);
    }
  }, [user, isAdmin]);

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
        <div
          className={`sidebar-overlay ${!sidebarOpen ? 'hidden' : ''}`}
          onClick={closeSidebar}
        />
        <Sidebar isOpen={sidebarOpen} onClose={closeSidebar} />
        <div className="flex-grow-1">
          <Navbar onToggleSidebar={toggleSidebar} />
          <div className="main-content">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/transactions" element={<Transactions />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/manual-entry" element={<ManualEntry />} />
                <Route path="/lots" element={<LotView />} />
                <Route path="/capital-gains" element={<CapitalGains />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/benchmark-comparison" element={<BenchmarkComparison />} />
                <Route path="/corporate-events" element={<CorporateEvents />} />
                <Route path="/security-master" element={<SecurityMaster />} />
                <Route path="/users" element={<ManageUsers />} />
                <Route path="/price-providers" element={<PriceProviders />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/db-admin" element={<DBAdmin />} />
                <Route path="*" element={<Navigate to="/dashboard" />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </div>
      </div>
      <CorporateEventsTicker />
      <ToastContainer position="top-right" autoClose={3000} />
    </div>
  );
}

export default App;