import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/authService';

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
  const [selectedUserId, setSelectedUserId] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem('user');
    
    if (userData) {
      const user = JSON.parse(userData);
      setUser(user);
      setSelectedUserId(user.id);
    }
    
    setLoading(false);
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
      setSelectedUserId(user.id);
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
      setSelectedUserId(user.id);
      return { user_data: user };
    }
  };

  const logout = () => {
    localStorage.removeItem('user');
    setUser(null);
    setSelectedUserId(null);
  };

  const switchUser = (userId) => {
    setSelectedUserId(userId);
  };

  const value = {
    user,
    selectedUserId,
    loading,
    login,
    logout,
    switchUser
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};