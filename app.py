from flask import Flask, render_template, request, jsonify
import yfinance as yf
import requests
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import time
from pyfinviz.quote import Quote
import pandas as pd
import csv

# Load environment variables.
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
        
        print(f"=== API ROTATION LOG for {symbol} ===")
        print(f"API order: {[api['name'] for api in apis_to_try]}")
        
        for i, api in enumerate(apis_to_try):
            try:
                print(f"[{i+1}/{len(apis_to_try)}] 🔄 Trying {api['name']} API for {symbol}...")
                result = api['method'](symbol)
                if result:
                    result['api_source'] = api['name']
                    print(f"✅ SUCCESS: Got data from {api['name']} for {symbol}")
                    print(f"   Price: ${result.get('current_price', 'N/A')}")
                    return result
                else:
                    print(f"❌ FAILED: {api['name']} returned None for {symbol}")
            except Exception as e:
                print(f"❌ ERROR: {api['name']} failed for {symbol}: {str(e)}")
                continue
        
        print(f"🚨 ALL APIs FAILED for {symbol}")
        return None
    
    def get_current_price(self, symbol):
        """Get just the current price for a symbol - used by AI predictor"""
        print(f"=== GET_CURRENT_PRICE called for {symbol} ===")
        quote = self.get_stock_quote(symbol)
        if quote and 'current_price' in quote:
            price = quote['current_price']
            print(f"✅ Current price for {symbol}: ${price}")
            return price
        else:
            print(f"❌ Failed to get current price for {symbol}")
            return None
    
    def get_cached_quote(self, symbol, force_refresh=False):
        """Get cached stock quote or fetch fresh if expired"""
        cache_file = 'data/cached_quotes.csv'
        
        # Create cache file if it doesn't exist
        if not os.path.exists(cache_file):
            with open(cache_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ticker', 'current_price', 'timestamp', 'api_source'])
        
        # Read existing cache
        cached_quotes = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['ticker']:  # Skip empty rows
                            cached_quotes[row['ticker']] = {
                                'current_price': float(row['current_price']),
                                'timestamp': row['timestamp'],
                                'api_source': row['api_source']
                            }
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Check if we have valid cached data
        if not force_refresh and symbol in cached_quotes:
            try:
                cached_time = datetime.fromisoformat(cached_quotes[symbol]['timestamp'])
                if datetime.now() - cached_time < timedelta(hours=1):
                    print(f"📋 Using cached quote for {symbol}: ${cached_quotes[symbol]['current_price']}")
                    return cached_quotes[symbol]
            except Exception as e:
                print(f"Error parsing cached timestamp for {symbol}: {e}")
        
        # Fetch fresh quote
        print(f"🔄 Fetching fresh quote for {symbol}...")
        quote = self.get_stock_quote(symbol)
        if quote:
            # Update cache
            cached_quotes[symbol] = {
                'current_price': quote['current_price'],
                'timestamp': datetime.now().isoformat(),
                'api_source': quote['api_source']
            }
            
            # Write updated cache
            try:
                with open(cache_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ticker', 'current_price', 'timestamp', 'api_source'])
                    for ticker, data in cached_quotes.items():
                        writer.writerow([ticker, data['current_price'], data['timestamp'], data['api_source']])
                print(f"💾 Cached quote for {symbol}: ${quote['current_price']}")
            except Exception as e:
                print(f"Error writing cache: {e}")
            
            return quote
        
        return None
    
    def _update_cache(self, symbol, price, api_source):
        """Update the cache file with new quote data"""
        cache_file = 'data/cached_quotes.csv'
        current_time = datetime.now().isoformat()
        
        # Read existing cache
        cached_data = []
        try:
            with open(cache_file, 'r', newline='') as file:
                reader = csv.DictReader(file)
                cached_data = [row for row in reader if row['ticker'].upper() != symbol.upper()]
        except FileNotFoundError:
            pass
        
        # Add new entry
        cached_data.append({
            'ticker': symbol.upper(),
            'current_price': price,
            'timestamp': current_time,
            'api_source': api_source
        })
        
        # Write back to cache
        with open(cache_file, 'w', newline='') as file:
            fieldnames = ['ticker', 'current_price', 'timestamp', 'api_source']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cached_data)
    
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

# Import and initialize AI predictor service
from ai_predictor_service import AIStockPredictorService
try:
    ai_predictor_service = AIStockPredictorService()
except ValueError as e:
    print(f"Warning: AI Predictor service not available: {e}")
    ai_predictor_service = None

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
        manual_price = data.get('price')  # Manual price from frontend
        
        if not ticker or quantity <= 0:
            return jsonify({'error': 'Invalid ticker or quantity'}), 400
        
        # Use manual price if provided, otherwise get current market price
        if manual_price is not None:
            current_price = float(manual_price)
            if current_price <= 0:
                return jsonify({'error': 'Invalid price'}), 400
        else:
            # Get current stock price from API
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

@app.route('/api/portfolio/performance')
def get_portfolio_performance():
    """API endpoint to get portfolio performance data"""
    try:
        from portfolio_service import PortfolioService
        portfolio_service = PortfolioService()
        
        # Get transactions to build performance timeline
        transactions = portfolio_service.get_transactions()
        if not transactions:
            return jsonify({'performance_data': [], 'total_gain_loss': 0, 'total_gain_loss_percent': 0})
        
        # Get unique dates from transactions
        dates = sorted(list(set([t['date'] for t in transactions])))
        performance_data = []
        
        for date in dates:
            # Calculate portfolio value on this date
            daily_value = calculate_portfolio_value_on_date(date, transactions)
            performance_data.append({
                'date': date,
                'portfolio_value': daily_value['total_value'],
                'cash_balance': daily_value['cash'],
                'holdings_value': daily_value['holdings_value'],
                'total_invested': daily_value['total_invested'],
                'gain_loss': daily_value['gain_loss'],
                'gain_loss_percent': daily_value['gain_loss_percent']
            })
        
        # Get current totals
        current_data = performance_data[-1] if performance_data else {
            'gain_loss': 0, 'gain_loss_percent': 0
        }
        
        return jsonify({
            'performance_data': performance_data,
            'total_gain_loss': current_data['gain_loss'],
            'total_gain_loss_percent': current_data['gain_loss_percent']
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get portfolio performance: {str(e)}'}), 500

@app.route('/api/portfolio/refresh-quotes', methods=['POST'])
def refresh_portfolio_quotes():
    """API endpoint to refresh portfolio quotes (override cache)"""
    try:
        from portfolio_service import PortfolioService
        portfolio_service = PortfolioService()
        
        # Get current holdings
        holdings = portfolio_service.get_holdings()
        refreshed_quotes = []
        
        for holding in holdings:
            ticker = holding['ticker']
            # Force refresh (override cache)
            quote = stock_service.get_cached_quote(ticker, force_refresh=True)
            if quote:
                refreshed_quotes.append({
                    'ticker': ticker,
                    'current_price': quote['current_price'],
                    'api_source': quote['api_source'],
                    'timestamp': quote.get('timestamp', datetime.now().isoformat())
                })
        
        return jsonify({
            'success': True,
            'refreshed_quotes': refreshed_quotes,
            'message': f'Refreshed quotes for {len(refreshed_quotes)} holdings'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to refresh quotes: {str(e)}'}), 500

def calculate_portfolio_value_on_date(target_date, transactions):
    """Calculate portfolio value on a specific date"""
    # Filter transactions up to target date
    relevant_transactions = [t for t in transactions if t['date'] <= target_date]
    
    # Calculate holdings and cash on this date
    holdings = {}
    total_invested = 0
    
    for transaction in relevant_transactions:
        ticker = transaction['ticker']
        
        # Skip transactions with empty values (like sell-only transactions)
        if not transaction['quantity'] or not transaction['buy_price'] or not transaction['total']:
            continue
            
        quantity = float(transaction['quantity'])
        price = float(transaction['buy_price'])
        total_cost = float(transaction['total'])
        
        if ticker not in holdings:
            holdings[ticker] = {'quantity': 0, 'total_cost': 0}
        
        holdings[ticker]['quantity'] += quantity
        holdings[ticker]['total_cost'] += total_cost
        total_invested += total_cost
    
    # Get current market values using cached quotes
    holdings_value = 0
    for ticker, holding in holdings.items():
        if holding['quantity'] > 0:
            quote = stock_service.get_cached_quote(ticker)
            if quote:
                market_value = quote['current_price'] * holding['quantity']
                holdings_value += market_value
    
    # Calculate cash (starting cash - total invested)
    starting_cash = 10000  # Initial cash amount
    current_cash = starting_cash - total_invested
    
    total_value = holdings_value + current_cash
    gain_loss = total_value - starting_cash
    gain_loss_percent = (gain_loss / starting_cash) * 100 if starting_cash > 0 else 0
    
    return {
        'total_value': total_value,
        'cash': current_cash,
        'holdings_value': holdings_value,
        'total_invested': total_invested,
        'gain_loss': gain_loss,
        'gain_loss_percent': gain_loss_percent
    }

@app.route('/api/ai/recommendations', methods=['POST'])
def get_ai_recommendations():
    """Get AI-powered stock recommendations"""
    try:
        from ai_predictor_service import AIStockPredictorService
        from portfolio_service import PortfolioService
        
        # Get request data
        request_data = request.get_json() or {}
        use_openai_price = request_data.get('use_openai_price', False)
        
        print(f"=== AI RECOMMENDATIONS REQUEST ===")
        print(f"Use OpenAI Price: {use_openai_price}")
        
        # Initialize services
        ai_service = AIStockPredictorService()
        portfolio_service = PortfolioService()
        stock_service = MultiAPIStockService() if not use_openai_price else None
        
        # Get recommendations
        result = ai_service.get_stock_recommendations(portfolio_service, stock_service, use_openai_price)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get AI recommendations: {str(e)}'
        }), 500

@app.route('/api/ai/execute-trades', methods=['POST'])
def execute_ai_trades():
    """API endpoint to execute selected AI trade recommendations"""
    try:
        data = request.get_json()
        selected_buys = data.get('selected_buys', [])
        selected_sells = data.get('selected_sells', [])
        
        results = {
            'buy_results': [],
            'sell_results': [],
            'errors': []
        }
        
        # Execute sell orders first
        for sell_data in selected_sells:
            try:
                ticker = sell_data['ticker']
                action = sell_data['action']
                
                if action == 'SELL':
                    # Get current holding to determine quantity
                    holdings = portfolio_service.get_holdings()
                    holding = next((h for h in holdings if h['ticker'] == ticker), None)
                    
                    if holding:
                        quote = stock_service.get_stock_quote(ticker)
                        if quote:
                            result = portfolio_service.sell_stock(
                                ticker=ticker,
                                quantity=int(holding['quantity']),
                                price=quote['current_price'],
                                reason=f"AI Recommendation: {sell_data.get('reason', 'AI suggested sell')}"
                            )
                            results['sell_results'].append(result)
                        else:
                            results['errors'].append(f"Could not get quote for {ticker}")
                    else:
                        results['errors'].append(f"No holding found for {ticker}")
                        
                elif action == 'TRIM':
                    # Sell half of the position
                    holdings = portfolio_service.get_holdings()
                    holding = next((h for h in holdings if h['ticker'] == ticker), None)
                    
                    if holding:
                        quote = stock_service.get_stock_quote(ticker)
                        if quote:
                            trim_quantity = max(1, int(holding['quantity'] // 2))
                            result = portfolio_service.sell_stock(
                                ticker=ticker,
                                quantity=trim_quantity,
                                price=quote['current_price'],
                                reason=f"AI Recommendation: {sell_data.get('reason', 'AI suggested trim')}"
                            )
                            results['sell_results'].append(result)
                        else:
                            results['errors'].append(f"Could not get quote for {ticker}")
                    else:
                        results['errors'].append(f"No holding found for {ticker}")
                        
            except Exception as e:
                results['errors'].append(f"Error selling {sell_data.get('ticker', 'unknown')}: {str(e)}")
        
        # Execute buy orders
        for buy_data in selected_buys:
            try:
                ticker = buy_data['ticker']
                quantity = int(buy_data['quantity'])
                stop_price = buy_data.get('stop_loss_price')
                
                print(f"=== EXECUTING BUY ORDER ===")
                print(f"Ticker: {ticker}")
                print(f"AI Quantity: {quantity}")
                print(f"AI Stop Price: {stop_price}")
                print(f"Buy Data: {buy_data}")
                
                quote = stock_service.get_stock_quote(ticker)
                if quote:
                    current_price = quote['current_price']
                    total_cost = current_price * quantity
                    
                    print(f"Current Market Price: ${current_price}")
                    print(f"Total Cost Calculation: ${current_price} x {quantity} = ${total_cost}")
                    
                    result = portfolio_service.buy_stock(
                        ticker=ticker,
                        quantity=quantity,
                        price=current_price,
                        reason=f"AI Recommendation: {buy_data.get('reason', 'AI suggested buy')}",
                        stop_price=stop_price
                    )
                    results['buy_results'].append(result)
                else:
                    results['errors'].append(f"Could not get quote for {ticker}")
                    
            except Exception as e:
                print(f"=== BUY ORDER ERROR ===")
                print(f"Error for {ticker}: {str(e)}")
                results['errors'].append(f"Error buying {buy_data.get('ticker', 'unknown')}: {str(e)}")
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': f'Failed to execute trades: {str(e)}'}), 500

@app.route('/api/ai/auto-execute-trades', methods=['POST'])
def auto_execute_ai_trades():
    """API endpoint to automatically execute AI trade recommendations with cash validation"""
    try:
        print(f"=== AUTO EXECUTE AI TRADES ===")
        
        # Get AI recommendations first
        from ai_predictor_service import AIStockPredictorService
        from portfolio_service import PortfolioService
        
        # Initialize services
        ai_service = AIStockPredictorService()
        portfolio_service_local = PortfolioService()
        
        # Get request data
        request_data = request.get_json() or {}
        use_openai_price = request_data.get('use_openai_price', False)
        
        print(f"Use OpenAI Price: {use_openai_price}")
        
        # Get AI recommendations with share reduction logic applied
        result = ai_service.get_stock_recommendations(
            portfolio_service_local, 
            stock_service if not use_openai_price else None, 
            use_openai_price
        )
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': f"Failed to get AI recommendations: {result.get('error', 'Unknown error')}"
            }), 500
        
        recommendations = result['recommendations']
        buy_recommendations = recommendations.get('buy_recommendations', [])
        sell_decisions = recommendations.get('sell_decisions', [])
        
        print(f"Got {len(buy_recommendations)} buy recommendations and {len(sell_decisions)} sell decisions")
        
        # Validate cash requirements one more time before execution
        current_cash = portfolio_service_local.get_cash_balance()
        total_buy_cost = sum(
            rec.get('current_price', rec.get('buy_price', 0)) * rec.get('quantity', 0) 
            for rec in buy_recommendations
        )
        
        print(f"Current Cash: ${current_cash:,.2f}")
        print(f"Total Buy Cost: ${total_buy_cost:,.2f}")
        print(f"Remaining after trades: ${current_cash - total_buy_cost:,.2f}")
        
        if total_buy_cost > current_cash - 500:
            return jsonify({
                'success': False,
                'error': f'Insufficient funds for auto-execution. Need ${total_buy_cost:,.2f}, have ${current_cash:,.2f} (keeping $500 buffer)',
                'current_cash': current_cash,
                'total_buy_cost': total_buy_cost,
                'recommendations': recommendations
            }), 400
        
        # Execute trades automatically
        execution_results = {
            'buy_results': [],
            'sell_results': [],
            'errors': [],
            'recommendations_used': recommendations,
            'auto_executed': True
        }
        
        # Execute sell orders first
        for sell_data in sell_decisions:
            try:
                ticker = sell_data['ticker']
                action = sell_data['action']
                
                if action == 'SELL':
                    holdings = portfolio_service_local.get_holdings()
                    holding = next((h for h in holdings if h['ticker'] == ticker), None)
                    
                    if holding:
                        if use_openai_price:
                            # Use a reasonable price for selling (we don't have current price)
                            current_price = 50.0  # Default price for test
                        else:
                            quote = stock_service.get_stock_quote(ticker)
                            if not quote:
                                execution_results['errors'].append(f"Could not get quote for {ticker}")
                                continue
                            current_price = quote['current_price']
                        
                        result = portfolio_service_local.sell_stock(
                            ticker=ticker,
                            quantity=int(holding['quantity']),
                            price=current_price,
                            reason=f"Auto AI Recommendation: {sell_data.get('reason', 'AI suggested sell')}"
                        )
                        execution_results['sell_results'].append(result)
                        print(f"✅ Auto-sold {holding['quantity']} shares of {ticker} at ${current_price}")
                    else:
                        execution_results['errors'].append(f"No holding found for {ticker}")
                        
                elif action == 'TRIM':
                    holdings = portfolio_service_local.get_holdings()
                    holding = next((h for h in holdings if h['ticker'] == ticker), None)
                    
                    if holding:
                        if use_openai_price:
                            current_price = 50.0  # Default price for test
                        else:
                            quote = stock_service.get_stock_quote(ticker)
                            if not quote:
                                execution_results['errors'].append(f"Could not get quote for {ticker}")
                                continue
                            current_price = quote['current_price']
                        
                        trim_quantity = max(1, int(holding['quantity'] // 2))
                        result = portfolio_service_local.sell_stock(
                            ticker=ticker,
                            quantity=trim_quantity,
                            price=current_price,
                            reason=f"Auto AI Recommendation: {sell_data.get('reason', 'AI suggested trim')}"
                        )
                        execution_results['sell_results'].append(result)
                        print(f"✅ Auto-trimmed {trim_quantity} shares of {ticker} at ${current_price}")
                    else:
                        execution_results['errors'].append(f"No holding found for {ticker}")
                        
            except Exception as e:
                error_msg = f"Error auto-selling {sell_data.get('ticker', 'unknown')}: {str(e)}"
                execution_results['errors'].append(error_msg)
                print(f"❌ {error_msg}")
        
        # Execute buy orders
        for buy_data in buy_recommendations:
            try:
                ticker = buy_data['ticker']
                quantity = int(buy_data['quantity'])
                stop_price = buy_data.get('stop_loss_price')
                
                print(f"=== AUTO EXECUTING BUY ORDER ===")
                print(f"Ticker: {ticker}")
                print(f"Quantity: {quantity}")
                print(f"Stop Price: {stop_price}")
                
                if use_openai_price:
                    # Use the AI-provided price
                    current_price = buy_data.get('current_price', buy_data.get('buy_price', 50.0))
                    print(f"Using OpenAI Price: ${current_price}")
                else:
                    # Get current market price
                    quote = stock_service.get_stock_quote(ticker)
                    if not quote:
                        execution_results['errors'].append(f"Could not get quote for {ticker}")
                        continue
                    current_price = quote['current_price']
                    print(f"Using Market Price: ${current_price}")
                
                total_cost = current_price * quantity
                print(f"Total Cost: ${current_price} x {quantity} = ${total_cost}")
                
                result = portfolio_service_local.buy_stock(
                    ticker=ticker,
                    quantity=quantity,
                    price=current_price,
                    reason=f"Auto AI Recommendation: {buy_data.get('reason', 'AI suggested buy')}",
                    stop_price=stop_price
                )
                execution_results['buy_results'].append(result)
                print(f"✅ Auto-bought {quantity} shares of {ticker} at ${current_price}")
                
            except Exception as e:
                error_msg = f"Error auto-buying {buy_data.get('ticker', 'unknown')}: {str(e)}"
                execution_results['errors'].append(error_msg)
                print(f"❌ {error_msg}")
        
        # Final summary
        print(f"=== AUTO EXECUTION COMPLETE ===")
        print(f"Successful buys: {len(execution_results['buy_results'])}")
        print(f"Successful sells: {len(execution_results['sell_results'])}")
        print(f"Errors: {len(execution_results['errors'])}")
        
        return jsonify(execution_results)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to auto-execute trades: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5007)
