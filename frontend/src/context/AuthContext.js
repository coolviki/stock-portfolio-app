import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/authService';
import { apiService } from '../services/apiService';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const initializeUser = async () => {
      const userData = localStorage.getItem('user');
      
      if (userData) {
        const user = JSON.parse(userData);
        setUser(user);
        
        // Check admin status if user has email
        if (user.email) {
          try {
            const adminCheck = await apiService.checkAdminAccess(user.email);
            setIsAdmin(adminCheck.is_admin);
          } catch (error) {
            console.error('Error checking admin status:', error);
            setIsAdmin(false);
          }
        }
      }
      
      setLoading(false);
    };
    
    initializeUser();
  }, []);

  const login = async (userData) => {
    let response;
    
    if (typeof userData === 'string') {
      // Username-based login (legacy)
      response = await authService.login(userData);
      const user = { 
        id: response.user_data.id, 
        username: response.user_data.username,
        email: response.user_data.email,
        full_name: response.user_data.full_name,
        picture_url: response.user_data.picture_url,
        is_firebase_user: response.user_data.is_firebase_user || false,
        created_at: response.user_data.created_at
      };
      
      localStorage.setItem('user', JSON.stringify(user));
      setUser(user);
      
      // Check admin status
      if (user.email) {
        try {
          const adminCheck = await apiService.checkAdminAccess(user.email);
          setIsAdmin(adminCheck.is_admin);
        } catch (error) {
          console.error('Error checking admin status:', error);
          setIsAdmin(false);
        }
      }
      
      return response;
    } else {
      // Firebase auth login (user object passed directly)
      const user = { 
        id: userData.id, 
        username: userData.username,
        email: userData.email,
        full_name: userData.full_name,
        picture_url: userData.picture_url,
        firebase_uid: userData.firebase_uid,
        is_firebase_user: userData.is_firebase_user || true,
        email_verified: userData.email_verified || false,
        created_at: userData.created_at
      };
      
      localStorage.setItem('user', JSON.stringify(user));
      setUser(user);
      
      // Check admin status
      if (user.email) {
        try {
          const adminCheck = await apiService.checkAdminAccess(user.email);
          setIsAdmin(adminCheck.is_admin);
        } catch (error) {
          console.error('Error checking admin status:', error);
          setIsAdmin(false);
        }
      }
      
      return { user_data: user };
    }
  };

  const logout = () => {
    localStorage.removeItem('user');
    setUser(null);
    setIsAdmin(false);
  };

  const value = {
    user,
    loading,
    isAdmin,
    login,
    logout
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};