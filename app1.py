from flask import Flask, render_template, request, jsonify
import yfinance as yf
import requests
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import time
from pyfinviz.quote import Quote

# Load environment variables
load_dotenv()

app = Flask(__name__)

class MultiAPIStockService:
    """Service class that uses multiple APIs with fallback logic"""
    
    def __init__(self):
        # API keys from environment variables
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.iex_key = os.getenv('IEX_CLOUD_API_KEY')
        
        # Define available APIs with their methods
        self.apis = [
            {'name': 'yfinance', 'method': self._get_yfinance_quote},
            {'name': 'pyfinviz', 'method': self._get_pyfinviz_quote},
            {'name': 'alpha_vantage', 'method': self._get_alpha_vantage_quote},
            {'name': 'finnhub', 'method': self._get_finnhub_quote},
            {'name': 'free_api', 'method': self._get_free_api_quote}
        ]
    
    def get_stock_quote(self, symbol):
        """Get stock quote using multiple APIs with random selection and fallback"""
        # Shuffle APIs for random selection
        apis_to_try = self.apis.copy()
        random.shuffle(apis_to_try)
        
        for api in apis_to_try:
            try:
                print(f"Trying {api['name']} for {symbol}...")
                result = api['method'](symbol)
                if result:
                    result['api_source'] = api['name']
                    print(f"Successfully got data from {api['name']}")
                    return result
            except Exception as e:
                print(f"Failed with {api['name']}: {str(e)}")
                continue
        
        print(f"All APIs failed for {symbol}")
        return None
    
    def _get_yfinance_quote(self, symbol):
        """Get quote from yfinance"""
        stock = yf.Ticker(symbol.upper())
        info = stock.info
        hist = stock.history(period="1d")
        
        if hist.empty:
            return None
            
        current_price = hist['Close'].iloc[-1]
        previous_close = info.get('previousClose', current_price)
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
        
        return {
            'symbol': symbol.upper(),
            'name': info.get('longName', symbol.upper()),
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': info.get('volume', 0),
            'market_cap': info.get('marketCap', 0),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _get_pyfinviz_quote(self, symbol):
        """Get quote from pyfinviz"""
        quote = Quote(ticker=symbol.upper())
        
        if not quote.exists:
            raise Exception("Stock symbol not found in pyfinviz")
        
        current_price = float(quote.price)
        
        # pyfinviz doesn't provide previous close directly, so we'll use current price as fallback
        # In a real implementation, you might want to get this from another source or cache it
        previous_close = current_price  # Fallback - could be enhanced
        change = 0  # Will be 0 without previous close data
        change_percent = 0
        
        # Try to get additional data if available
        volume = 0
        market_cap = 0
        company_name = symbol.upper()
        
        try:
            # pyfinviz Quote object may have additional attributes
            if hasattr(quote, 'volume') and quote.volume:
                volume = int(float(quote.volume.replace(',', '').replace('M', '000000').replace('K', '000')))
            if hasattr(quote, 'market_cap') and quote.market_cap:
                market_cap_str = quote.market_cap.replace('B', '000000000').replace('M', '000000').replace('K', '000')
                market_cap = int(float(market_cap_str))
            if hasattr(quote, 'company') and quote.company:
                company_name = quote.company
        except:
            pass  # Use defaults if parsing fails
        
        return {
            'symbol': symbol.upper(),
            'name': company_name,
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': volume,
            'market_cap': market_cap,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _get_alpha_vantage_quote(self, symbol):
        """Get quote from Alpha Vantage"""
        if not self.alpha_vantage_key:
            raise Exception("Alpha Vantage API key not provided")
            
        url = f"https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol.upper(),
            'apikey': self.alpha_vantage_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'Global Quote' not in data:
            raise Exception("Invalid response from Alpha Vantage")
        
        quote = data['Global Quote']
        current_price = float(quote['05. price'])
        previous_close = float(quote['08. previous close'])
        change = float(quote['09. change'])
        change_percent = float(quote['10. change percent'].replace('%', ''))
        
        return {
            'symbol': symbol.upper(),
            'name': symbol.upper(),
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': int(quote['06. volume']),
            'market_cap': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _get_finnhub_quote(self, symbol):
        """Get quote from Finnhub"""
        if not self.finnhub_key:
            raise Exception("Finnhub API key not provided")
            
        url = f"https://finnhub.io/api/v1/quote"
        params = {
            'symbol': symbol.upper(),
            'token': self.finnhub_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'c' not in data or data['c'] == 0:
            raise Exception("Invalid response from Finnhub")
        
        current_price = data['c']
        previous_close = data['pc']
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
        
        return {
            'symbol': symbol.upper(),
            'name': symbol.upper(),
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': 0,
            'market_cap': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _get_free_api_quote(self, symbol):
        """Get quote from a free API (financialmodelingprep)"""
        url = f"https://financialmodelingprep.com/api/v3/quote-short/{symbol.upper()}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data or len(data) == 0:
            raise Exception("Invalid response from free API")
        
        quote = data[0]
        current_price = quote['price']
        
        # Get previous day data for change calculation
        hist_url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries=2"
        hist_response = requests.get(hist_url, timeout=10)
        hist_data = hist_response.json()
        
        previous_close = current_price  # Default fallback
        if 'historical' in hist_data and len(hist_data['historical']) > 1:
            previous_close = hist_data['historical'][1]['close']
        
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
        
        return {
            'symbol': symbol.upper(),
            'name': symbol.upper(),
            'current_price': round(current_price, 2),
            'previous_close': round(previous_close, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': quote.get('volume', 0),
            'market_cap': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_historical_data(self, symbol, period="1mo"):
        """Get historical data with fallback logic"""
        # Try yfinance first for historical data as it's most reliable for this
        try:
            stock = yf.Ticker(symbol.upper())
            hist = stock.history(period=period)
            
            if not hist.empty:
                data = []
                for date, row in hist.iterrows():
                    data.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'open': round(row['Open'], 2),
                        'high': round(row['High'], 2),
                        'low': round(row['Low'], 2),
                        'close': round(row['Close'], 2),
                        'volume': int(row['Volume'])
                    })
                return data
        except Exception as e:
            print(f"yfinance historical data failed: {str(e)}")
        
        # Fallback to free API for historical data
        try:
            days = {'1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365}.get(period, 30)
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries={days}"
            
            response = requests.get(url, timeout=15)
            data = response.json()
            
            if 'historical' in data:
                historical_data = []
                for item in reversed(data['historical']):  # Reverse to get chronological order
                    historical_data.append({
                        'date': item['date'],
                        'open': round(item['open'], 2),
                        'high': round(item['high'], 2),
                        'low': round(item['low'], 2),
                        'close': round(item['close'], 2),
                        'volume': int(item['volume'])
                    })
                return historical_data
        except Exception as e:
            print(f"Free API historical data failed: {str(e)}")
        
        return None

# Initialize the multi-API service
stock_service = MultiAPIStockService()

# Import and initialize portfolio service
from portfolio_service import PortfolioService
portfolio_service = PortfolioService()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/quote/<symbol>')
def get_quote(symbol):
    """API endpoint to get stock quote"""
    quote = stock_service.get_stock_quote(symbol)
    if quote:
        return jsonify(quote)
    else:
        return jsonify({'error': f'Could not fetch data for symbol {symbol}'}), 404

@app.route('/api/historical/<symbol>')
def get_historical(symbol):
    """API endpoint to get historical data"""
    period = request.args.get('period', '1mo')
    data = stock_service.get_historical_data(symbol, period)
    if data:
        return jsonify({'symbol': symbol.upper(), 'data': data})
    else:
        return jsonify({'error': f'Could not fetch historical data for symbol {symbol}'}), 404

@app.route('/api/multiple')
def get_multiple_quotes():
    """API endpoint to get multiple stock quotes"""
    symbols = request.args.get('symbols', '').split(',')
    symbols = [s.strip() for s in symbols if s.strip()]
    
    if not symbols:
        return jsonify({'error': 'No symbols provided'}), 400
    
    quotes = []
    for symbol in symbols:
        quote = stock_service.get_stock_quote(symbol)
        if quote:
            quotes.append(quote)
    
    return jsonify({'quotes': quotes})

@app.route('/api/portfolio/buy', methods=['POST'])
def buy_stock():
    """API endpoint to buy stock"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        quantity = int(data.get('quantity', 0))
        reason = data.get('reason', '').strip()
        stop_price = data.get('stop_price')
        
        if not ticker or quantity <= 0:
            return jsonify({'error': 'Invalid ticker or quantity'}), 400
        
        # Get current stock price
        quote = stock_service.get_stock_quote(ticker)
        if not quote:
            return jsonify({'error': f'Could not get quote for {ticker}'}), 404
        
        current_price = quote['current_price']
        
        # Execute buy transaction
        result = portfolio_service.buy_stock(
            ticker=ticker,
            quantity=quantity,
            price=current_price,
            reason=reason,
            stop_price=float(stop_price) if stop_price else None
        )
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Transaction failed: {str(e)}'}), 500

@app.route('/api/portfolio/sell', methods=['POST'])
def sell_stock():
    """API endpoint to sell stock"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        quantity = int(data.get('quantity', 0))
        reason = data.get('reason', '').strip()
        
        if not ticker or quantity <= 0:
            return jsonify({'error': 'Invalid ticker or quantity'}), 400
        
        # Get current stock price
        quote = stock_service.get_stock_quote(ticker)
        if not quote:
            return jsonify({'error': f'Could not get quote for {ticker}'}), 404
        
        current_price = quote['current_price']
        
        # Execute sell transaction
        result = portfolio_service.sell_stock(
            ticker=ticker,
            quantity=quantity,
            price=current_price,
            reason=reason
        )
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Transaction failed: {str(e)}'}), 500

@app.route('/api/portfolio/summary')
def get_portfolio_summary():
    """API endpoint to get portfolio summary"""
    try:
        summary = portfolio_service.get_portfolio_summary(stock_service)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': f'Failed to get portfolio summary: {str(e)}'}), 500

@app.route('/api/portfolio/transactions')
def get_transactions():
    """API endpoint to get all transactions"""
    try:
        transactions = portfolio_service.get_transactions()
        return jsonify({'transactions': transactions})
    except Exception as e:
        return jsonify({'error': f'Failed to get transactions: {str(e)}'}), 500

@app.route('/api/portfolio/cash')
def get_cash_balance():
    """API endpoint to get cash balance"""
    try:
        cash = portfolio_service.get_cash_balance()
        return jsonify({'cash_balance': cash})
    except Exception as e:
        return jsonify({'error': f'Failed to get cash balance: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5007)
