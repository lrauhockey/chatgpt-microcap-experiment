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
        self.iex_key = os.getenv('IEX_CLOUD_API_KEY')
        
        # Define available APIs with their methods in a specific order of preference
        self.apis = [
            {'name': 'finnhub', 'method': self._get_finnhub_quote},
            {'name': 'alpha_vantage', 'method': self._get_alpha_vantage_quote},
            {'name': 'yfinance', 'method': self._get_yfinance_quote},
            {'name': 'pyfinviz', 'method': self._get_pyfinviz_quote},
            {'name': 'free_api', 'method': self._get_free_api_quote}
        ]
    
    def get_stock_quote(self, symbol):
        """Get stock quote using multiple APIs with fallback in a predefined order"""
        # Use the predefined order of APIs
        apis_to_try = self.apis.copy()
        
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
        
        if not os.path.exists(cache_file):
            with open(cache_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ticker', 'current_price', 'timestamp', 'api_source'])
        
        cached_quotes = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['ticker']:
                            cached_quotes[row['ticker']] = {
                                'current_price': float(row['current_price']),
                                'timestamp': row['timestamp'],
                                'api_source': row['api_source']
                            }
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        if not force_refresh and symbol in cached_quotes:
            try:
                cached_time = datetime.fromisoformat(cached_quotes[symbol]['timestamp'])
                if datetime.now() - cached_time < timedelta(hours=1):
                    print(f"📋 Using cached quote for {symbol}: ${cached_quotes[symbol]['current_price']}")
                    return cached_quotes[symbol]
            except Exception as e:
                print(f"Error parsing cached timestamp for {symbol}: {e}")
        
        print(f"🔄 Fetching fresh quote for {symbol}...")
        quote = self.get_stock_quote(symbol)
        if quote:
            cached_quotes[symbol] = {
                'current_price': quote['current_price'],
                'timestamp': datetime.now().isoformat(),
                'api_source': quote['api_source']
            }
            
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
        previous_close = current_price
        change = 0
        change_percent = 0
        
        volume = 0
        market_cap = 0
        company_name = symbol.upper()
        
        try:
            if hasattr(quote, 'volume') and quote.volume:
                volume = int(float(quote.volume.replace(',', '').replace('M', '000000').replace('K', '000')))
            if hasattr(quote, 'market_cap') and quote.market_cap:
                market_cap_str = quote.market_cap.replace('B', '000000000').replace('M', '000000').replace('K', '000')
                market_cap = int(float(market_cap_str))
            if hasattr(quote, 'company') and quote.company:
                company_name = quote.company
        except:
            pass
        
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
        
        if 'Global Quote' not in data or not data['Global Quote']:
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
        finnhub_key = os.getenv('FINHUB_API_KEY')

        if not finnhub_key:
            raise Exception("Finnhub API key not provided")

        url = f"https://finnhub.io/api/v1/quote"
        params = {'symbol': symbol.upper(), 'token': finnhub_key}
        
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
        
        hist_url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries=2"
        hist_response = requests.get(hist_url, timeout=10)
        hist_data = hist_response.json()
        
        previous_close = current_price
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
        try:
            stock = yf.Ticker(symbol.upper())
            hist = stock.history(period=period)
            
            if not hist.empty:
                data = [{'date': date.strftime('%Y-%m-%d'), 'open': round(row['Open'], 2), 'high': round(row['High'], 2), 'low': round(row['Low'], 2), 'close': round(row['Close'], 2), 'volume': int(row['Volume'])} for date, row in hist.iterrows()]
                return data
        except Exception as e:
            print(f"yfinance historical data failed: {str(e)}")
        
        try:
            days = {'1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365}.get(period, 30)
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol.upper()}?timeseries={days}"
            
            response = requests.get(url, timeout=15)
            data = response.json()
            
            if 'historical' in data:
                return [{'date': item['date'], 'open': round(item['open'], 2), 'high': round(item['high'], 2), 'low': round(item['low'], 2), 'close': round(item['close'], 2), 'volume': int(item['volume'])} for item in reversed(data['historical'])]
        except Exception as e:
            print(f"Free API historical data failed: {str(e)}")
        
        return None

# Initialize services
stock_service = MultiAPIStockService()
from portfolio_service import PortfolioService
portfolio_service = PortfolioService()
from ai_predictor_service import AIStockPredictorService
try:
    ai_predictor_service = AIStockPredictorService()
except ValueError as e:
    print(f"Warning: AI Predictor service not available: {e}")
    ai_predictor_service = None

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/quote/<symbol>')
def get_quote(symbol):
    quote = stock_service.get_stock_quote(symbol)
    if quote:
        return jsonify(quote)
    else:
        return jsonify({'error': f'Could not fetch data for symbol {symbol}'}), 404

@app.route('/api/historical/<symbol>')
def get_historical(symbol):
    period = request.args.get('period', '1mo')
    data = stock_service.get_historical_data(symbol, period)
    if data:
        return jsonify({'symbol': symbol.upper(), 'data': data})
    else:
        return jsonify({'error': f'Could not fetch historical data for symbol {symbol}'}), 404

@app.route('/api/portfolio/buy', methods=['POST'])
def buy_stock():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        quantity = int(data.get('quantity', 0))
        
        if not ticker or quantity <= 0:
            return jsonify({'error': 'Invalid ticker or quantity'}), 400
        
        price = data.get('price')
        if price is None:
            quote = stock_service.get_stock_quote(ticker)
            if not quote:
                return jsonify({'error': f'Could not get quote for {ticker}'}), 404
            price = quote['current_price']

        result = portfolio_service.buy_stock(
            ticker=ticker,
            quantity=quantity,
            price=float(price),
            reason=data.get('reason', '').strip(),
            stop_price=float(data.get('stop_price')) if data.get('stop_price') else None
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Transaction failed: {str(e)}'}), 500

@app.route('/api/portfolio/sell', methods=['POST'])
def sell_stock():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        quantity = int(data.get('quantity', 0))

        if not ticker or quantity <= 0:
            return jsonify({'error': 'Invalid ticker or quantity'}), 400
        
        quote = stock_service.get_stock_quote(ticker)
        if not quote:
            return jsonify({'error': f'Could not get quote for {ticker}'}), 404
        
        result = portfolio_service.sell_stock(
            ticker=ticker,
            quantity=quantity,
            price=quote['current_price'],
            reason=data.get('reason', '').strip()
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Transaction failed: {str(e)}'}), 500

@app.route('/api/portfolio/summary')
def get_portfolio_summary():
    try:
        summary = portfolio_service.get_portfolio_summary(stock_service)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': f'Failed to get portfolio summary: {str(e)}'}), 500

@app.route('/api/portfolio/transactions')
def get_transactions():
    try:
        transactions = portfolio_service.get_transactions()
        return jsonify({'transactions': transactions})
    except Exception as e:
        return jsonify({'error': f'Failed to get transactions: {str(e)}'}), 500

@app.route('/api/ai/recommendations', methods=['POST'])
def get_ai_recommendations():
    try:
        request_data = request.get_json() or {}
        use_openai_price = request_data.get('use_openai_price', False)
        
        print(f"=== AI RECOMMENDATIONS REQUEST (OpenAI Price: {use_openai_price}) ===")
        
        result = ai_predictor_service.get_stock_recommendations(
            portfolio_service, 
            stock_service if not use_openai_price else None, 
            use_openai_price
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get AI recommendations: {str(e)}'}), 500

@app.route('/api/ai/execute-trades', methods=['POST'])
def execute_ai_trades():
    """Executes trades selected manually from the UI."""
    try:
        data = request.get_json()
        selected_buys = data.get('selected_buys', [])
        selected_sells = data.get('selected_sells', [])
        
        results = {'buy_results': [], 'sell_results': [], 'errors': []}
        
        for sell_data in selected_sells:
            try:
                ticker = sell_data['ticker']
                holdings = portfolio_service.get_holdings()
                holding = next((h for h in holdings if h['ticker'] == ticker), None)
                if not holding:
                    raise ValueError(f"No holding found for {ticker}")

                quantity_to_sell = int(holding['quantity'])
                if sell_data.get('action') == 'TRIM':
                    quantity_to_sell = max(1, quantity_to_sell // 2)

                quote = stock_service.get_stock_quote(ticker)
                if not quote:
                    raise ConnectionError(f"Could not get quote for {ticker}")

                result = portfolio_service.sell_stock(
                    ticker=ticker,
                    quantity=quantity_to_sell,
                    price=quote['current_price'],
                    reason=f"AI Recommendation: {sell_data.get('reason', 'AI suggested sell/trim')}"
                )
                results['sell_results'].append(result)
            except Exception as e:
                results['errors'].append(f"Error processing sell for {sell_data.get('ticker', 'unknown')}: {str(e)}")

        for buy_data in selected_buys:
            try:
                ticker = buy_data['ticker']
                quantity = int(buy_data['quantity'])
                quote = stock_service.get_stock_quote(ticker)
                if not quote:
                    raise ConnectionError(f"Could not get quote for {ticker}")

                result = portfolio_service.buy_stock(
                    ticker=ticker,
                    quantity=quantity,
                    price=quote['current_price'],
                    reason=f"AI Recommendation: {buy_data.get('reason', 'AI suggested buy')}",
                    stop_price=buy_data.get('stop_loss_price')
                )
                results['buy_results'].append(result)
            except Exception as e:
                results['errors'].append(f"Error processing buy for {buy_data.get('ticker', 'unknown')}: {str(e)}")
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': f'Failed to execute trades: {str(e)}'}), 500

@app.route('/api/ai/auto-execute-trades', methods=['POST'])
def auto_execute_ai_trades():
    """API endpoint to automatically execute AI trade recommendations."""
    try:
        data = request.get_json()
        recommendations = data.get('recommendations')

        if not recommendations:
            print("ERROR: No recommendations provided to auto-execute.")
            return jsonify({'error': 'No recommendations provided'}), 400

        buy_results, sell_results, errors = [], [], []

        # Execute Sells First
        if 'sells' in recommendations and recommendations['sells']:
            for sell_trade in recommendations['sells']:
                try:
                    ticker = sell_trade.get('ticker')
                    quantity = sell_trade.get('quantity')
                    price = sell_trade.get('price')
                    print(f"Attempting to SELL {quantity} shares of {ticker}")
                    if not all([ticker, quantity, price]):
                        raise ValueError("Sell trade data is incomplete.")
                    
                    sell_result = portfolio_service.sell_stock(
                        ticker=ticker,
                        quantity=quantity,
                        price=price,
                        reason=sell_trade.get('reason', 'Auto-AI Sell')
                    )
                    sell_results.append(sell_result)
                    print(f"SUCCESS: Sold {ticker}")
                except Exception as e:
                    error_msg = f"Failed to execute sell for {sell_trade.get('ticker', 'UNKNOWN')}: {str(e)}"
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)

        # Execute Buys
        if 'buys' in recommendations and recommendations['buys']:
            for buy_trade in recommendations['buys']:
                try:
                    ticker = buy_trade.get('ticker')
                    quantity = buy_trade.get('quantity')
                    price = buy_trade.get('price')
                    print(f"Attempting to BUY {quantity} shares of {ticker}")
                    if not all([ticker, quantity, price]):
                        raise ValueError("Buy trade data is incomplete.")

                    buy_result = portfolio_service.buy_stock(
                        ticker=ticker,
                        quantity=quantity,
                        price=price,
                        reason=buy_trade.get('reason', 'Auto-AI Buy'),
                        stop_price=buy_trade.get('stop_loss_price')
                    )
                    buy_results.append(buy_result)
                    print(f"SUCCESS: Bought {ticker}")
                except Exception as e:
                    error_msg = f"Failed to execute buy for {buy_trade.get('ticker', 'UNKNOWN')}: {str(e)}"
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)

        # Update cache after trades
        try:
            holdings = portfolio_service.get_holdings()
            if holdings:
                print(f"Updating cached quotes for {len(holdings)} holdings...")
                for holding in holdings:
                    stock_service.get_cached_quote(holding['ticker'], force_refresh=True)
                print("Cache update complete.")
        except Exception as e:
            print(f"Error updating cache after trades: {e}")

        return jsonify({
            'success': not errors,
            'buy_results': buy_results,
            'sell_results': sell_results,
            'errors': errors,
            'message': 'Auto-execution attempt completed.'
        })

    except Exception as e:
        print(f"CRITICAL ERROR in auto_execute_ai_trades: {str(e)}")
        return jsonify({'error': f'A critical error occurred: {str(e)}'}), 500


def calculate_portfolio_value_on_date(target_date, transactions):
    """Calculate portfolio value on a specific date using actual portfolio data"""
    print(f"=== PORTFOLIO CALCULATION DEBUG for {target_date} ===")
    
    # For current date, use actual portfolio data instead of reconstructing from transactions
    today = datetime.now().strftime('%Y-%m-%d')
    if target_date == today:
        print("Using actual portfolio data for current date")
        try:
            # Get actual portfolio summary
            portfolio_summary = portfolio_service.get_portfolio_summary(stock_service)
            
            starting_cash = 10000.0
            total_value = portfolio_summary['total_portfolio_value']
            cash_balance = portfolio_summary['cash_balance']
            holdings_value = portfolio_summary['total_market_value']
            
            gain_loss = total_value - starting_cash
            gain_loss_percent = (gain_loss / starting_cash) * 100 if starting_cash > 0 else 0
            
            print(f"Actual portfolio data:")
            print(f"Cash balance: ${cash_balance:.2f}")
            print(f"Holdings value: ${holdings_value:.2f}")
            print(f"Total value: ${total_value:.2f}")
            print(f"Gain/Loss: ${gain_loss:.2f} ({gain_loss_percent:.2f}%)")
            print(f"=== END PORTFOLIO CALCULATION DEBUG ===")
            
            return {
                'total_value': total_value,
                'cash': cash_balance,
                'holdings_value': holdings_value,
                'total_invested': starting_cash - cash_balance + holdings_value,
                'gain_loss': gain_loss,
                'gain_loss_percent': gain_loss_percent
            }
        except Exception as e:
            print(f"Failed to get actual portfolio data: {e}")
            # Fall back to transaction reconstruction
    
    # For historical dates, reconstruct from transactions
    print("Reconstructing from transaction history")
    relevant_transactions = [t for t in transactions if t['date'][:10] <= target_date]
    
    print(f"Total transactions: {len(transactions)}")
    print(f"Relevant transactions: {len(relevant_transactions)}")
    
    holdings = {}
    total_invested = 0
    total_proceeds = 0
    
    for t in relevant_transactions:
        ticker = t['ticker']
        
        # Check if this is a buy transaction (has quantity and buy_price)
        if t.get('quantity') and t.get('buy_price') and t.get('total'):
            quantity = float(t['quantity'])
            total_cost = float(t['total'])
            total_invested += total_cost
            
            if ticker not in holdings:
                holdings[ticker] = 0
            holdings[ticker] += quantity
            
            print(f"BUY: {ticker} - {quantity} shares @ ${float(t['buy_price']):.2f} = ${total_cost:.2f}")
            
        # Check if this is a sell transaction (has sell_quantity and sell_price)
        elif t.get('sell_quantity') and t.get('sell_price'):
            sell_quantity = float(t['sell_quantity'])
            sell_price = float(t['sell_price'])
            sell_total = sell_quantity * sell_price
            total_proceeds += sell_total
            
            if ticker in holdings:
                holdings[ticker] -= sell_quantity
                # Remove ticker if quantity becomes 0 or negative
                if holdings[ticker] <= 0:
                    del holdings[ticker]
            
            print(f"SELL: {ticker} - {sell_quantity} shares @ ${sell_price:.2f} = ${sell_total:.2f}")

    print(f"Total invested: ${total_invested:.2f}")
    print(f"Total proceeds: ${total_proceeds:.2f}")
    print(f"Holdings: {holdings}")

    # Calculate current market value of holdings
    holdings_value = 0
    for ticker, quantity in holdings.items():
        if quantity > 0:
            quote = stock_service.get_cached_quote(ticker)
            if quote:
                market_value = quote['current_price'] * quantity
                holdings_value += market_value
                print(f"HOLDING: {ticker} - {quantity} shares @ ${quote['current_price']:.2f} = ${market_value:.2f}")

    # Calculate cash position
    starting_cash = 10000  # As defined in portfolio_service
    current_cash = starting_cash - total_invested + total_proceeds
    
    # Calculate total portfolio value and gains/losses
    total_value = current_cash + holdings_value
    gain_loss = total_value - starting_cash
    gain_loss_percent = (gain_loss / starting_cash) * 100 if starting_cash > 0 else 0
    
    print(f"Starting cash: ${starting_cash:.2f}")
    print(f"Current cash: ${current_cash:.2f}")
    print(f"Holdings value: ${holdings_value:.2f}")
    print(f"Total value: ${total_value:.2f}")
    print(f"Gain/Loss: ${gain_loss:.2f} ({gain_loss_percent:.2f}%)")
    print(f"=== END PORTFOLIO CALCULATION DEBUG ===")
    
    return {
        'total_value': total_value,
        'cash': current_cash,
        'holdings_value': holdings_value,
        'total_invested': total_invested,
        'gain_loss': gain_loss,
        'gain_loss_percent': gain_loss_percent
    }

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
    """API endpoint to get portfolio performance data using daily performance tracking"""
    try:
        print("=== PERFORMANCE API CALLED ===")
        
        # Update today's performance first
        today = datetime.now().strftime('%Y-%m-%d')
        update_daily_performance(today)
        
        # Get performance data from file
        performance_records = portfolio_service.get_daily_performance()
        
        if not performance_records:
            print("No performance records found")
            return jsonify({'performance_data': [], 'total_gain_loss': 0, 'total_gain_loss_percent': 0})
        
        # Convert to chart format
        performance_data = []
        for record in performance_records:
            performance_data.append({
                'date': record['date'],
                'portfolio_pct_change': round(record['portfolio_gain_loss_pct'], 3),
                'sp500_pct_change': round(record['spy_gain_loss_pct'], 3),
                'portfolio_value': record['portfolio_value'],
                'sp500_value': record['spy_price']
            })
        
        # Get current totals
        latest_record = performance_records[-1]
        
        result = {
            'performance_data': performance_data,
            'total_gain_loss': latest_record['portfolio_gain_loss'],
            'total_gain_loss_percent': latest_record['portfolio_gain_loss_pct'],
            'start_date': performance_records[0]['date'],
            'end_date': latest_record['date']
        }
        
        print(f"Returned {len(performance_data)} performance data points")
        print("=== PERFORMANCE API SUCCESS ===")
        return jsonify(result)
        
    except Exception as e:
        print(f"=== PERFORMANCE API ERROR: {str(e)} ===")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to get portfolio performance: {str(e)}'}), 500

def update_daily_performance(date: str):
    """Update daily performance record for a specific date"""
    try:
        print(f"=== UPDATING DAILY PERFORMANCE for {date} ===")
        
        # Get portfolio data
        portfolio_summary = portfolio_service.get_portfolio_summary(stock_service)
        portfolio_value = portfolio_summary['total_portfolio_value']
        
        # Calculate portfolio gain/loss from $10,000 baseline
        baseline = 10000.0
        portfolio_gain_loss = portfolio_value - baseline
        portfolio_gain_loss_pct = (portfolio_gain_loss / baseline) * 100
        
        # Get SPY data
        spy_quote = stock_service.get_cached_quote("SPY")
        spy_price = spy_quote['current_price'] if spy_quote else 659.30
        
        # Calculate SPY gain/loss from baseline (use first cached SPY price as baseline)
        spy_baseline = 659.30  # Your cached baseline price
        spy_gain_loss = spy_price - spy_baseline
        spy_gain_loss_pct = (spy_gain_loss / spy_baseline) * 100
        
        print(f"Portfolio: ${portfolio_value:.2f} (${portfolio_gain_loss:+.2f}, {portfolio_gain_loss_pct:+.3f}%)")
        print(f"SPY: ${spy_price:.2f} (${spy_gain_loss:+.2f}, {spy_gain_loss_pct:+.3f}%)")
        
        # Record the data
        portfolio_service.record_daily_performance(
            date=date,
            portfolio_value=portfolio_value,
            portfolio_gain_loss=portfolio_gain_loss,
            portfolio_gain_loss_pct=portfolio_gain_loss_pct,
            spy_price=spy_price,
            spy_gain_loss=spy_gain_loss,
            spy_gain_loss_pct=spy_gain_loss_pct
        )
        
        print(f"=== DAILY PERFORMANCE UPDATED ===")
        
    except Exception as e:
        print(f"Error updating daily performance: {e}")
        import traceback
        traceback.print_exc()

@app.route('/api/portfolio/refresh-quotes', methods=['POST'])
def refresh_portfolio_quotes():
    """API endpoint to refresh portfolio quotes (override cache)"""
    try:
        holdings = portfolio_service.get_holdings()
        refreshed_quotes = []
        
        for holding in holdings:
            ticker = holding['ticker']
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
