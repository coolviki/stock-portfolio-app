import React, { useState, useEffect } from 'react';
import { apiService } from '../services/apiService';
import { useAuth } from '../context/AuthContext';
import './CorporateEventsTicker.css';

const CorporateEventsTicker = () => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    loadEvents();
  }, [user]);

  const loadEvents = async () => {
    try {
      if (!user?.id) return;
      const data = await apiService.getCorporateEventsForUserHoldings(user.id);
      setEvents(data.events || []);
    } catch (error) {
      console.error('Error loading corporate events:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || events.length === 0) {
    return null;
  }

  // Duplicate events for seamless loop
  const tickerEvents = [...events, ...events];

  return (
    <div className="corporate-events-ticker">
      <div className="ticker-label">
        <span>Corporate Events</span>
      </div>
      <div className="ticker-wrapper">
        <div className="ticker-content">
          {tickerEvents.map((event, index) => (
            <span key={`${event.id}-${index}`} className="ticker-item">
              <span className={`ticker-badge ${event.event_type.toLowerCase()}`}>
                {event.event_type}
              </span>
              <span className="ticker-stock">{event.security_ticker || event.security_name}</span>
              <span className="ticker-text">{event.event_text}</span>
              <span className={`ticker-date ${event.is_upcoming ? 'upcoming' : 'past'}`}>
                {event.event_date}
                {event.is_upcoming && ' (Upcoming)'}
              </span>
              <span className="ticker-separator">|</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CorporateEventsTicker;
