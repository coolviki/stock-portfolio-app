import ReactGA from 'react-ga4';

// Google Analytics Measurement ID
// Can be overridden by REACT_APP_GA_MEASUREMENT_ID environment variable
const GA_MEASUREMENT_ID = process.env.REACT_APP_GA_MEASUREMENT_ID || 'G-S9YD26850T';

// Initialize Google Analytics
export const initGA = () => {
  const measurementId = GA_MEASUREMENT_ID;

  if (measurementId) {
    ReactGA.initialize(measurementId, {
      gaOptions: {
        siteSpeedSampleRate: 100
      }
    });
    console.log('Google Analytics initialized with ID:', measurementId);
    return true;
  } else {
    console.log('Google Analytics not initialized - REACT_APP_GA_MEASUREMENT_ID not set');
    return false;
  }
};

// Track page views
export const trackPageView = (path, title) => {
  if (GA_MEASUREMENT_ID) {
    ReactGA.send({
      hitType: 'pageview',
      page: path,
      title: title
    });
  }
};

// Track custom events
export const trackEvent = (category, action, label = null, value = null) => {
  if (GA_MEASUREMENT_ID) {
    ReactGA.event({
      category,
      action,
      label,
      value
    });
  }
};

// Track user login
export const trackLogin = (method) => {
  trackEvent('User', 'Login', method);
};

// Track user logout
export const trackLogout = () => {
  trackEvent('User', 'Logout');
};

// Track transaction actions
export const trackTransaction = (action, securityName) => {
  trackEvent('Transaction', action, securityName);
};

// Track report generation
export const trackReport = (reportType) => {
  trackEvent('Report', 'Generate', reportType);
};

// Track PDF/CSV export
export const trackExport = (exportType, reportType) => {
  trackEvent('Export', exportType, reportType);
};

// Track file upload
export const trackUpload = (fileCount) => {
  trackEvent('Upload', 'Contract Notes', null, fileCount);
};

// Track errors
export const trackError = (errorType, errorMessage) => {
  trackEvent('Error', errorType, errorMessage);
};

// Set user properties (for logged-in users)
export const setUserProperties = (userId, isAdmin) => {
  if (GA_MEASUREMENT_ID) {
    ReactGA.set({
      userId: userId,
      user_properties: {
        is_admin: isAdmin
      }
    });
  }
};

const analytics = {
  initGA,
  trackPageView,
  trackEvent,
  trackLogin,
  trackLogout,
  trackTransaction,
  trackReport,
  trackExport,
  trackUpload,
  trackError,
  setUserProperties
};

export default analytics;
