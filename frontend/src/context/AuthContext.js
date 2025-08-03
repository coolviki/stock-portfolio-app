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

  const login = async (username) => {
    const response = await authService.login(username);
    const userData = { 
      id: response.user_data.id, 
      username: response.user_data.username,
      created_at: response.user_data.created_at
    };
    
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    setSelectedUserId(userData.id);
    
    return response;
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