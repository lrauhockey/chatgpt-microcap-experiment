# AI-Powered Portfolio Management System

A comprehensive Python Flask web application that combines real-time stock data, AI-powered trading recommendations, automated portfolio management, and performance tracking. Features include intelligent stock analysis, automated trading execution, and advanced portfolio monitoring.

## 🚀 Features

### 📊 **Real-Time Stock Data**
- Multi-API stock quote system with automatic failover
- 1-hour cached quotes system for performance optimization
- Support for 5+ free stock APIs with rotation
- Real-time price updates and market data

### 🤖 **AI-Powered Trading**
- OpenAI GPT-4 integration for intelligent stock analysis
- Automated buy/sell recommendations with reasoning
- Risk assessment and stop-loss price suggestions
- Market sentiment analysis and trend prediction

### 💼 **Portfolio Management**
- Complete portfolio tracking with CSV-based storage
- Buy/sell transaction execution with P&L calculations
- Holdings management with weighted average cost basis
- Cash balance tracking and transaction history

### 📈 **Performance Analytics**
- Interactive Chart.js performance visualization
- Gain/loss tracking over time with color-coded charts
- Portfolio value progression and trend analysis
- Real-time performance metrics and percentages

### ⏰ **Automated Trading Scheduler**
- **9:30 AM Weekdays**: AI predictor with automatic trade execution
- **10 AM, 12 PM, 2 PM, 3:30 PM**: Stop-loss monitoring and protection
- Comprehensive logging and error handling
- Weekday-only operation with market hours awareness

### 🎨 **Modern Web Interface**
- Bootstrap-powered responsive design
- Tabbed interface for different portfolio functions
- Real-time data updates and interactive charts
- Mobile-friendly and professional UI

## 🔌 **Stock APIs Supported**

- **yfinance** - No API key required, reliable data source
- **Alpha Vantage** - 25 requests/day free tier
- **pyfinviz** - Financial data scraping
- **Finnhub** - 60 calls/minute free tier
- **Free APIs** - Various backup data sources

## 📦 Installation

1. **Clone the repository and navigate to the project directory**

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your_openai_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

4. **Run the web application:**
```bash
python app.py
```

5. **Open your browser and navigate to `http://localhost:5000`**

## 🤖 Automated Trading Setup

### **Start the Trading Scheduler:**
```bash
python scheduler.py
```

### **Test Scheduler Functions:**
```bash
python test_scheduler.py
```

The scheduler will automatically:
- Execute AI-driven trades at 9:30 AM on weekdays
- Monitor stop-losses at 10 AM, 12 PM, 2 PM, and 3:30 PM
- Update cached quotes and log all activities

## 🌐 API Endpoints

### **Stock Data APIs**
- `GET /api/quote/<symbol>` - Get current stock quote
- `GET /api/historical/<symbol>?period=1mo` - Get historical data
- `GET /api/multiple?symbols=AAPL,GOOGL,TSLA` - Get multiple quotes

### **Portfolio Management APIs**
- `POST /api/portfolio/buy` - Execute buy order
- `POST /api/portfolio/sell` - Execute sell order
- `GET /api/portfolio/summary` - Get portfolio overview
- `GET /api/portfolio/transactions` - Get transaction history
- `GET /api/portfolio/performance` - Get performance chart data
- `POST /api/portfolio/refresh-quotes` - Override quote cache

### **AI Trading APIs**
- `POST /api/ai/recommendations` - Get AI trading recommendations
- `POST /api/ai/execute-trades` - Execute selected AI recommendations

## 📊 Data Storage

The system uses CSV files for data persistence:

- **`data/transactions.csv`** - All buy/sell transactions with P&L
- **`data/holdings.csv`** - Current portfolio holdings
- **`data/cash.csv`** - Cash balance tracking
- **`data/cached_quotes.csv`** - 1-hour cached stock quotes

## 🎯 Usage Examples

### **Manual Trading via Web Interface**
1. Navigate to the Portfolio tab
2. Use Buy/Sell forms to execute trades
3. View performance charts and transaction history
4. Monitor real-time portfolio value

### **AI-Powered Trading**
1. Go to the AI Predictor tab
2. Click "Get AI Recommendations"
3. Review AI analysis and suggestions
4. Select trades to execute or let scheduler handle automatically

### **Automated Trading**
1. Start the scheduler: `python scheduler.py`
2. The system will automatically:
   - Run AI analysis at market open (9:30 AM)
   - Execute recommended trades
   - Monitor stop-losses throughout the day
   - Log all activities to `scheduler.log`

## 🔧 Configuration

### **Environment Variables**
```bash
OPENAI_API_KEY=your_openai_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

### **Initial Cash Balance**
The system starts with $10,000 in cash. Modify in `portfolio_service.py` if needed.

### **Trading Schedule**
Modify `scheduler.py` to adjust trading times and frequency.

## 📈 Performance Features

- **Real-time portfolio tracking** with gain/loss calculations
- **Interactive charts** showing performance over time
- **Color-coded metrics** (green for gains, red for losses)
- **Stop-loss protection** with automatic monitoring
- **Transaction history** with detailed P&L tracking

## 🚀 Advanced Features

### **Multi-API Failover System**
The application automatically rotates through multiple stock APIs if one fails, ensuring reliable data access.

### **Intelligent Caching**
1-hour cached quotes system reduces API calls while maintaining data freshness.

### **AI Integration**
OpenAI GPT-4 analyzes market conditions, company fundamentals, and provides reasoned trading recommendations.

### **Risk Management**
- Automatic stop-loss price suggestions
- Cash balance validation before trades
- Portfolio diversification tracking

## 🔍 Monitoring & Logging

- **Web Interface**: Real-time portfolio monitoring
- **Scheduler Logs**: Detailed trading activity logs in `scheduler.log`
- **Console Output**: Live trading updates and status messages
- **Error Handling**: Comprehensive error logging and recovery

## 🛠️ Extending the System

The modular architecture makes it easy to add:
- Additional stock APIs
- New AI models or trading strategies
- Custom technical indicators
- Advanced portfolio analytics
- Integration with brokers' APIs
- Mobile app connectivity
 