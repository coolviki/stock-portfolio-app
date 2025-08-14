// Broker configuration and constants for the contract note upload feature

export const DEFAULT_BROKER_ID = 'hdfc-securities';

// Popular Indian stock brokers list
export const BROKERS = [
  {
    id: 'hdfc-securities',
    name: 'HDFC Securities',
    icon: '🏦',
    supported: true,
    description: 'Fully supported - PDF parsing available'
  },
  {
    id: 'zerodha',
    name: 'Zerodha',
    icon: '⚡',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'upstox',
    name: 'Upstox',
    icon: '📈',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'angel-one',
    name: 'Angel One (Angel Broking)',
    icon: '👼',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'icici-direct',
    name: 'ICICI Direct',
    icon: '🏛️',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'kotak-securities',
    name: 'Kotak Securities',
    icon: '🏢',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'sharekhan',
    name: 'Sharekhan',
    icon: '📊',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'motilal-oswal',
    name: 'Motilal Oswal',
    icon: '🔷',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'edelweiss',
    name: 'Edelweiss',
    icon: '❄️',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: '5paisa',
    name: '5paisa',
    icon: '5️⃣',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'groww',
    name: 'Groww',
    icon: '🌱',
    supported: false,
    description: 'Coming soon'
  },
  {
    id: 'paytm-money',
    name: 'Paytm Money',
    icon: '💰',
    supported: false,
    description: 'Coming soon'
  }
];