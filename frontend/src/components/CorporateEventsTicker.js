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

  if (loading) {
    return null;
  }

  // Show placeholder if no events
  const hasEvents = events.length > 0;

  // Duplicate events for seamless loop, or use placeholder
  const tickerEvents = hasEvents
    ? [...events, ...events]
    : [];

  return (
    <div className="corporate-events-ticker">
      <div className="ticker-label">
        <span>Corporate Events</span>
      </div>
      <div className="ticker-wrapper">
        <div className={`ticker-content ${!hasEvents ? 'no-animation' : ''}`}>
          {hasEvents ? (
            tickerEvents.map((event, index) => (
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
            ))
          ) : (
            <span className="ticker-placeholder">
              Corporate events for your holdings (stock splits, bonuses, dividends) will appear here when available. Fetch events from Security Master to populate this ticker.
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default CorporateEventsTicker;
