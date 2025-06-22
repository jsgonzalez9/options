# Options Trading Dashboard

A modern, responsive options trading dashboard built with React, TypeScript, and Tailwind CSS. This dashboard provides comprehensive tools for monitoring options positions, analyzing volatility, and tracking portfolio performance.

## Features

### 📊 **Portfolio Overview**
- Real-time portfolio value and P&L tracking
- Performance metrics including win rate and theta decay
- Interactive charts showing cumulative returns over time

### 📈 **Volatility Analysis**
- Implied vs Historical volatility comparison
- IV Rank tracking for better entry timing
- Multi-timeframe volatility charts

### 💼 **Position Management**
- Comprehensive positions table with Greeks
- Strategy-based position grouping
- Real-time P&L and risk metrics

### 👀 **Watchlist**
- Track favorite symbols with real-time prices
- Implied volatility monitoring
- Quick access to options chains

### 🎨 **Modern UI/UX**
- Clean, professional design inspired by modern trading platforms
- Responsive layout that works on all devices
- Intuitive navigation and user experience

## Technology Stack

- **Frontend**: React 18 with TypeScript
- **Styling**: Tailwind CSS with custom design system
- **Charts**: Recharts for data visualization
- **Icons**: Lucide React for consistent iconography
- **Build Tool**: Create React App

## Getting Started

### Prerequisites

- Node.js (version 16 or higher)
- npm or yarn package manager

### Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start the development server**:
   ```bash
   npm start
   ```

3. **Open your browser** and navigate to `http://localhost:3000`

### Available Scripts

- `npm start` - Runs the app in development mode
- `npm build` - Builds the app for production
- `npm test` - Launches the test runner
- `npm eject` - Ejects from Create React App (one-way operation)

## Project Structure

```
src/
├── components/
│   ├── Dashboard.tsx          # Main dashboard layout
│   ├── Header.tsx             # Top navigation bar
│   ├── Sidebar.tsx            # Side navigation menu
│   ├── MetricsGrid.tsx        # Key performance indicators
│   ├── OptionsChart.tsx       # Portfolio performance chart
│   ├── VolatilityChart.tsx    # Volatility analysis chart
│   ├── PositionsTable.tsx     # Active positions table
│   └── WatchlistCard.tsx      # Symbol watchlist
├── App.tsx                    # Main application component
├── index.tsx                  # Application entry point
└── index.css                  # Global styles and Tailwind imports
```

## Key Components

### Dashboard
The main dashboard provides a comprehensive overview of your options trading activity with:
- Portfolio metrics grid
- Performance charts
- Active positions table
- Symbol watchlist

### Charts
- **Portfolio Performance**: Tracks cumulative P&L over time
- **Volatility Analysis**: Compares implied vs historical volatility with IV rank

### Data Tables
- **Positions Table**: Shows all active options positions with Greeks and P&L
- **Watchlist**: Tracks favorite symbols with real-time data

## Customization

### Styling
The project uses Tailwind CSS with a custom design system. Key design tokens are defined in `tailwind.config.js`:

- **Colors**: Primary blue palette with success/danger variants
- **Typography**: Inter font family for clean readability
- **Shadows**: Soft shadows for depth and hierarchy

### Adding New Features
1. Create new components in the `src/components/` directory
2. Follow the existing TypeScript patterns and interfaces
3. Use the established design system for consistency
4. Add proper error handling and loading states

## Data Integration

Currently, the dashboard uses mock data for demonstration purposes. To integrate with real market data:

1. **Replace mock data** in components with API calls
2. **Add data fetching logic** using fetch or axios
3. **Implement real-time updates** using WebSockets
4. **Add error handling** for network requests

### Recommended APIs
- **Market Data**: Alpha Vantage, IEX Cloud, or Polygon.io
- **Options Data**: CBOE, TradierAPI, or Interactive Brokers API
- **Real-time**: WebSocket connections for live updates

## Performance Considerations

- **Lazy Loading**: Consider implementing lazy loading for large datasets
- **Memoization**: Use React.memo and useMemo for expensive calculations
- **Virtual Scrolling**: For large tables with many positions
- **Data Caching**: Implement caching for frequently accessed data

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

This dashboard is for educational and demonstration purposes only. It should not be used for actual trading decisions without proper testing and validation. Always consult with financial professionals before making investment decisions.