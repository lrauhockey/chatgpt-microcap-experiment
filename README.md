# AI-Powered Portfolio Management System

A comprehensive Python Flask web application that combines real-time stock data, AI-powered trading recommendations, automated portfolio management, and performance tracking. Features include intelligent stock analysis, automated trading execution, and advanced portfolio monitoring.

Note: this is not an offer to buy or sell stock. This is was built as an experiment to see if ChatGPT could trade or not.  
I don't endorse anyone using this to manage thier portfolo. It is a good example of testing out some APIs including Open AI API
Please invest with a professional!   This does not represent my current, past or future employment. 
All the code was written by AI (incluing the prompt to AI ) as this was also used as a demo to how to vibe code a system. 
This was in response to https://github.com/LuckyOne7777/ChatGPT-Micro-Cap-Experiment trading success. 

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
- Interactive Chart.js performance visualization with S&P 500 comparison
- Daily performance tracking with persistent CSV storage
- Portfolio vs. market benchmark analysis (SPY ETF)
- Percentage-based gain/loss charts with baseline normalization
- Real-time performance metrics and stop-loss monitoring

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

3. **Set up environment variables (.env):**
Copy the sample file and edit your values:
```bash
cp .env_sample .env
```
Then open `.env` and set at minimum:
```
OPENAI_API_KEY=your_openai_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FINHUB_API_KEY=your_finnhub_key_here

# Email (Gmail)
USERID=your_gmail_address@gmail.com
APP_PASSWORD=your_16_char_gmail_app_password
```
Notes:
- Create a Gmail App Password in Google Account → Security → 2‑Step Verification → App passwords.
- The scheduler auto-detects Gmail and uses `smtp.gmail.com:465` (SSL) and `imap.gmail.com` by default.
- You may optionally override SMTP/IMAP via env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_SSL`, `IMAP_HOST`, `IMAP_CHECK`.

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

- **`data/transactions.csv`** - All buy/sell transactions with P&L and stop-loss prices
- **`data/holdings.csv`** - Current portfolio holdings with market values
- **`data/cash.csv`** - Cash balance tracking
- **`data/cached_quotes.csv`** - 1-hour cached stock quotes including SPY
- **`data/daily_performance.csv`** - Daily portfolio and S&P 500 performance tracking

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
Environment is loaded from `.env` (see Installation step). Core variables:
```
# APIs
OPENAI_API_KEY=your_openai_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FINHUB_API_KEY=your_finnhub_key_here

# Email (Gmail)
USERID=your_gmail_address@gmail.com
APP_PASSWORD=your_16_char_gmail_app_password

# Optional SMTP/IMAP overrides
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=465
# SMTP_USE_SSL=true
# IMAP_HOST=imap.gmail.com
# IMAP_CHECK=true
# SMTP_DEBUG=false
```

#### Email Notes
- The app prefers the `certifi` CA bundle for SSL. `requirements.txt` includes `certifi`.
- If you need to bypass IMAP pre-check, set `IMAP_CHECK=false`.

### **Initial Cash Balance**
The system starts with $10,000 in cash. Modify in `portfolio_service.py` if needed.

### **Trading Schedule**
Modify `scheduler.py` to adjust trading times and frequency.

### **Daily Performance Tracking**
The system automatically creates and maintains a `daily_performance.csv` file with the following structure:
```csv
date,portfolio_value,portfolio_gain_loss,portfolio_gain_loss_pct,spy_price,spy_gain_loss,spy_gain_loss_pct
2025-09-17,9989.2,-10.80,-0.108,659.18,-0.12,-0.018
```

**Key Features:**
- **Automatic daily updates** when accessing performance charts
- **Baseline tracking** from $10,000 initial portfolio value
- **SPY benchmark comparison** using cached quote system
- **Persistent storage** for historical performance analysis
- **Accurate percentage calculations** for portfolio vs. market performance

## 📈 Performance Features

### **Daily Performance Tracking System**
- **Automated daily performance recording** in `daily_performance.csv`
- **Portfolio vs. S&P 500 comparison** using SPY ETF as benchmark
- **Baseline normalization** from $10,000 starting portfolio
- **Percentage-based performance charts** for accurate comparison
- **Persistent performance history** with CSV storage

### **Portfolio Analytics**
- **Real-time portfolio tracking** with gain/loss calculations
- **Interactive dual-line charts** (Portfolio vs. Market)
- **Stop-loss monitoring** with risk percentage display
- **Color-coded metrics** (green for gains, red for losses)
- **Transaction history** with detailed P&L and stop-loss tracking

### **Market Comparison Features**
- **SPY ETF integration** for S&P 500 market comparison
- **Cached quote system** for efficient data retrieval
- **Day-over-day performance** calculation and display
- **Risk assessment** showing downside protection percentages

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
 
