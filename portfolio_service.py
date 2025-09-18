import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd 

class PortfolioService:
    """Service class to handle portfolio transactions and file management"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.transactions_file = os.path.join(data_dir, "transactions.csv")
        self.holdings_file = os.path.join(data_dir, "holdings.csv")
        self.cash_file = os.path.join(data_dir, "cash.csv")
        self.performance_file = os.path.join(data_dir, "daily_performance.csv")
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
    
    def get_cash_balance(self) -> float:
        """Get current cash balance"""
        try:
            with open(self.cash_file, 'r') as f:
                reader = csv.DictReader(f)
                row = next(reader)
                return float(row['cash_amount'])
        except (FileNotFoundError, StopIteration, KeyError):
            # Initialize with default cash if file doesn't exist
            self._update_cash_balance(10000.00)
            return 10000.00
    
    def _update_cash_balance(self, new_balance: float):
        """Update cash balance in file"""
        with open(self.cash_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['cash_amount'])
            writer.writerow([f"{new_balance:.2f}"])
    
    def get_holdings(self) -> List[Dict]:
        """Get current holdings"""
        holdings = []
        try:
            with open(self.holdings_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    holdings.append({
                        'ticker': row['ticker'],
                        'quantity': float(row['quantity']),
                        'average_cost': float(row['average_cost']),
                        'total_market_value': float(row['total_market_value'])
                    })
        except FileNotFoundError:
            pass
        return holdings
    
    def _update_holdings(self, holdings: List[Dict]):
        """Update holdings file"""
        with open(self.holdings_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ticker', 'quantity', 'average_cost', 'total_market_value'])
            writer.writeheader()
            for holding in holdings:
                writer.writerow(holding)
    
    def _add_transaction(self, transaction: Dict):
        """Add transaction to transactions file"""
        file_exists = os.path.exists(self.transactions_file)
        with open(self.transactions_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'date', 'ticker', 'quantity', 'buy_price', 'total', 'reason', 
                'stop_price', 'sell_date', 'sell_quantity', 'sell_price', 'gain_loss'
            ])
            if not file_exists:
                writer.writeheader()
            writer.writerow(transaction)
    
    def buy_stock(self, ticker: str, quantity: int, price: float, reason: str, stop_price: Optional[float] = None) -> Dict:
        """Execute a buy transaction"""
        total_cost = quantity * price
        current_cash = self.get_cash_balance()
        
        if total_cost > current_cash:
            raise ValueError(f"Insufficient funds. Need ${total_cost:.2f}, have ${current_cash:.2f}")
        
        # Update cash balance
        new_cash_balance = current_cash - total_cost
        self._update_cash_balance(new_cash_balance)
        
        # Add transaction record
        transaction = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ticker': ticker.upper(),
            'quantity': quantity,
            'buy_price': price,
            'total': total_cost,
            'reason': reason,
            'stop_price': stop_price if stop_price else '',
            'sell_date': '',
            'sell_quantity': '',
            'sell_price': '',
            'gain_loss': ''
        }
        self._add_transaction(transaction)
        
        # Update holdings
        self._update_holdings_after_buy(ticker.upper(), quantity, price)
        
        return {
            'success': True,
            'message': f"Bought {quantity} shares of {ticker.upper()} at ${price:.2f} each",
            'total_cost': total_cost,
            'remaining_cash': new_cash_balance,
            'transaction': transaction
        }
    
    def sell_stock(self, ticker: str, quantity: int, price: float, reason: str) -> Dict:
        """Execute a sell transaction"""
        holdings = self.get_holdings()
        ticker_upper = ticker.upper()
        
        # Find the holding
        holding = None
        for h in holdings:
            if h['ticker'] == ticker_upper:
                holding = h
                break
        
        if not holding:
            raise ValueError(f"No holdings found for {ticker_upper}")
        
        if quantity > holding['quantity']:
            raise ValueError(f"Cannot sell {quantity} shares. Only have {holding['quantity']} shares of {ticker_upper}")
        
        # Calculate gain/loss
        total_proceeds = quantity * price
        cost_basis = quantity * holding['average_cost']
        gain_loss = total_proceeds - cost_basis
        
        # Update cash balance
        current_cash = self.get_cash_balance()
        new_cash_balance = current_cash + total_proceeds
        self._update_cash_balance(new_cash_balance)
        
        # Add transaction record
        transaction = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ticker': ticker_upper,
            'quantity': '',
            'buy_price': '',
            'total': '',
            'reason': reason,
            'stop_price': '',
            'sell_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sell_quantity': quantity,
            'sell_price': price,
            'gain_loss': gain_loss
        }
        self._add_transaction(transaction)
        
        # Update holdings
        self._update_holdings_after_sell(ticker_upper, quantity)
        
        return {
            'success': True,
            'message': f"Sold {quantity} shares of {ticker_upper} at ${price:.2f} each",
            'total_proceeds': total_proceeds,
            'gain_loss': gain_loss,
            'remaining_cash': new_cash_balance,
            'transaction': transaction
        }
    
    def _update_holdings_after_buy(self, ticker: str, quantity: int, price: float):
        """Update holdings after a buy transaction"""
        holdings = self.get_holdings()
        
        # Find existing holding
        existing_holding = None
        for i, holding in enumerate(holdings):
            if holding['ticker'] == ticker:
                existing_holding = i
                break
        
        if existing_holding is not None:
            # Update existing holding with weighted average cost
            old_holding = holdings[existing_holding]
            old_total_cost = old_holding['quantity'] * old_holding['average_cost']
            new_total_cost = quantity * price
            total_quantity = old_holding['quantity'] + quantity
            new_average_cost = (old_total_cost + new_total_cost) / total_quantity
            
            holdings[existing_holding] = {
                'ticker': ticker,
                'quantity': total_quantity,
                'average_cost': new_average_cost,
                'total_market_value': total_quantity * price  # Will be updated with real-time price later
            }
        else:
            # Add new holding
            holdings.append({
                'ticker': ticker,
                'quantity': quantity,
                'average_cost': price,
                'total_market_value': quantity * price
            })
        
        self._update_holdings(holdings)
    
    def _update_holdings_after_sell(self, ticker: str, quantity: int):
        """Update holdings after a sell transaction"""
        holdings = self.get_holdings()
        
        for i, holding in enumerate(holdings):
            if holding['ticker'] == ticker:
                new_quantity = holding['quantity'] - quantity
                if new_quantity <= 0:
                    # Remove holding if quantity is 0 or less
                    holdings.pop(i)
                else:
                    # Update quantity
                    holdings[i]['quantity'] = new_quantity
                    # Keep same average cost, update market value (will be updated with real-time price later)
                    holdings[i]['total_market_value'] = new_quantity * holding['average_cost']
                break
        
        self._update_holdings(holdings)
    
    def update_market_values(self, stock_service):
        """Update market values for all holdings using current stock prices"""
        holdings = self.get_holdings()
        updated_holdings = []
        
        for holding in holdings:
            quote = stock_service.get_stock_quote(holding['ticker'])
            if quote:
                current_price = quote['current_price']
                holding['total_market_value'] = holding['quantity'] * current_price
            updated_holdings.append(holding)
        
        self._update_holdings(updated_holdings)
        return updated_holdings
    
    def get_portfolio_summary(self, stock_service) -> Dict:
        """Get complete portfolio summary with stop loss information"""
        cash_balance = self.get_cash_balance()
        holdings = self.update_market_values(stock_service)
        
        # Add stop loss information to holdings
        holdings_with_stop_loss = self._add_stop_loss_to_holdings(holdings)
        
        total_market_value = sum(h['total_market_value'] for h in holdings_with_stop_loss)
        total_portfolio_value = cash_balance + total_market_value
        
        return {
            'cash_balance': cash_balance,
            'holdings': holdings_with_stop_loss,
            'total_market_value': total_market_value,
            'total_portfolio_value': total_portfolio_value,
            'holdings_count': len(holdings_with_stop_loss)
        }
    
    def _add_stop_loss_to_holdings(self, holdings: List[Dict]) -> List[Dict]:
        """Add stop loss information to holdings from transaction history"""
        transactions = self.get_transactions()
        
        # Create a map of ticker to stop loss prices from buy transactions
        stop_loss_map = {}
        for tx in transactions:
            ticker = tx.get('ticker', '').upper()
            stop_price = tx.get('stop_price', '')
            
            # Only consider buy transactions with stop prices
            if tx.get('quantity') and tx.get('buy_price') and stop_price:
                try:
                    stop_loss_price = float(stop_price)
                    if stop_loss_price > 0:
                        # Use the most recent stop loss price for each ticker
                        stop_loss_map[ticker] = stop_loss_price
                except (ValueError, TypeError):
                    continue
        
        # Add stop loss information to holdings
        enriched_holdings = []
        for holding in holdings:
            ticker = holding['ticker']
            enriched_holding = holding.copy()
            
            if ticker in stop_loss_map:
                stop_loss_price = stop_loss_map[ticker]
                current_price = holding['total_market_value'] / holding['quantity'] if holding['quantity'] > 0 else 0
                
                enriched_holding['stop_loss_price'] = stop_loss_price
                enriched_holding['has_stop_loss'] = True
                
                # Calculate stop loss risk percentage
                if current_price > 0:
                    risk_percentage = ((current_price - stop_loss_price) / current_price) * 100
                    enriched_holding['stop_loss_risk_pct'] = max(0, risk_percentage)  # Ensure non-negative
                else:
                    enriched_holding['stop_loss_risk_pct'] = 0
            else:
                enriched_holding['stop_loss_price'] = None
                enriched_holding['has_stop_loss'] = False
                enriched_holding['stop_loss_risk_pct'] = 0
            
            enriched_holdings.append(enriched_holding)
        
        return enriched_holdings
    
    def get_transactions(self) -> List[Dict]:
        """Get all transactions"""
        transactions = []
        try:
            with open(self.transactions_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    transactions.append(row)
        except FileNotFoundError:
            pass
        return transactions
    
    def record_daily_performance(self, date: str, portfolio_value: float, portfolio_gain_loss: float, 
                                portfolio_gain_loss_pct: float, spy_price: float, spy_gain_loss: float, 
                                spy_gain_loss_pct: float):
        """Record daily performance data"""
        file_exists = os.path.exists(self.performance_file)
        
        # Check if entry for this date already exists
        existing_data = []
        if file_exists:
            try:
                with open(self.performance_file, 'r') as f:
                    reader = csv.DictReader(f)
                    existing_data = [row for row in reader if row['date'] != date]
            except:
                existing_data = []
        
        # Add new entry
        new_entry = {
            'date': date,
            'portfolio_value': portfolio_value,
            'portfolio_gain_loss': portfolio_gain_loss,
            'portfolio_gain_loss_pct': portfolio_gain_loss_pct,
            'spy_price': spy_price,
            'spy_gain_loss': spy_gain_loss,
            'spy_gain_loss_pct': spy_gain_loss_pct
        }
        existing_data.append(new_entry)
        
        # Write back to file
        with open(self.performance_file, 'w', newline='') as f:
            fieldnames = ['date', 'portfolio_value', 'portfolio_gain_loss', 'portfolio_gain_loss_pct', 
                         'spy_price', 'spy_gain_loss', 'spy_gain_loss_pct']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in existing_data:
                writer.writerow(row)
    
    def get_daily_performance(self) -> List[Dict]:
        """Get all daily performance records"""
        performance_data = []
        try:
            with open(self.performance_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    row['portfolio_value'] = float(row['portfolio_value'])
                    row['portfolio_gain_loss'] = float(row['portfolio_gain_loss'])
                    row['portfolio_gain_loss_pct'] = float(row['portfolio_gain_loss_pct'])
                    row['spy_price'] = float(row['spy_price'])
                    row['spy_gain_loss'] = float(row['spy_gain_loss'])
                    row['spy_gain_loss_pct'] = float(row['spy_gain_loss_pct'])
                    performance_data.append(row)
        except FileNotFoundError:
            pass
        return performance_data
