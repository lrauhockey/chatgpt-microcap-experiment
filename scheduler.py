#!/usr/bin/env python3
"""
Automated Trading Scheduler
Runs scheduled tasks for portfolio management:
- 9:30 AM weekdays: AI predictor with automatic buy/sell execution
- 10:00 AM, 12:00 PM, 2:00 PM, 3:30 PM: Stop-loss monitoring

"""

import schedule
import time
import logging
from datetime import datetime, timedelta
from portfolio_service import PortfolioService
from ai_predictor_service import AIStockPredictorService
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TradingScheduler:
    def __init__(self):
        self.portfolio_service = PortfolioService()
        self.ai_service = AIStockPredictorService()
        
        # Import stock service from app.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app import stock_service
        self.stock_service = stock_service
        
        logger.info("Trading Scheduler initialized")
    
    def run_ai_predictor_with_execution(self):
        """Run AI predictor at 9:30 AM and execute trades automatically"""
        try:
            logger.info("=== RUNNING 9:30 AM AI PREDICTOR WITH AUTO-EXECUTION ===")
            
            # Get current portfolio data
            holdings = self.portfolio_service.get_holdings()
            cash_balance = self.portfolio_service.get_cash_balance()
            
            logger.info(f"Current cash balance: ${cash_balance:.2f}")
            logger.info(f"Current holdings: {len(holdings)} positions")
            
            # Get AI recommendations
            recommendations = self.ai_service.get_stock_recommendations(
                portfolio_service=self.portfolio_service,
                stock_service=self.stock_service,
                use_openai_price=False  # Use real market prices
            )
            
            if not recommendations:
                logger.warning("No AI recommendations received")
                return
            
            # Execute SELL orders first to free up cash
            sell_results = []
            if 'sell_decisions' in recommendations and recommendations['sell_decisions']:
                logger.info(f"Processing {len(recommendations['sell_decisions'])} SELL recommendations...")
                
                for sell_rec in recommendations['sell_decisions']:
                    try:
                        ticker = sell_rec['ticker']
                        quantity = sell_rec['quantity']
                        
                        # Get current market price
                        quote = self.stock_service.get_cached_quote(ticker, force_refresh=True)
                        if not quote:
                            logger.error(f"Failed to get current price for {ticker}")
                            continue
                        
                        current_price = quote['current_price']
                        
                        # Execute sell
                        result = self.portfolio_service.sell_stock(
                            ticker=ticker,
                            quantity=quantity,
                            price=current_price,
                            reason=f"AI Auto-Sell: {sell_rec.get('reason', 'AI recommendation')}"
                        )
                        
                        sell_results.append({
                            'ticker': ticker,
                            'quantity': quantity,
                            'price': current_price,
                            'result': result,
                            'success': True
                        })
                        
                        logger.info(f"✅ SOLD {quantity} shares of {ticker} at ${current_price:.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to sell {sell_rec['ticker']}: {str(e)}")
                        sell_results.append({
                            'ticker': sell_rec['ticker'],
                            'error': str(e),
                            'success': False
                        })
            
            # Execute BUY orders after sells are complete
            buy_results = []
            if 'buy_decisions' in recommendations and recommendations['buy_decisions']:
                # Refresh cash balance after sells
                cash_balance = self.portfolio_service.get_cash_balance()
                logger.info(f"Cash available for buys: ${cash_balance:.2f}")
                logger.info(f"Processing {len(recommendations['buy_decisions'])} BUY recommendations...")
                
                for buy_rec in recommendations['buy_decisions']:
                    try:
                        ticker = buy_rec['ticker']
                        quantity = buy_rec['quantity']
                        stop_loss_price = buy_rec.get('stop_loss_price')
                        
                        # Get current market price
                        quote = self.stock_service.get_cached_quote(ticker, force_refresh=True)
                        if not quote:
                            logger.error(f"Failed to get current price for {ticker}")
                            continue
                        
                        current_price = quote['current_price']
                        total_cost = quantity * current_price
                        
                        # Check if we have enough cash
                        current_cash = self.portfolio_service.get_cash_balance()
                        if total_cost > current_cash:
                            logger.warning(f"Insufficient funds for {ticker}: Need ${total_cost:.2f}, have ${current_cash:.2f}")
                            continue
                        
                        # Execute buy
                        result = self.portfolio_service.buy_stock(
                            ticker=ticker,
                            quantity=quantity,
                            price=current_price,
                            reason=f"AI Auto-Buy: {buy_rec.get('reason', 'AI recommendation')}",
                            stop_price=stop_loss_price
                        )
                        
                        buy_results.append({
                            'ticker': ticker,
                            'quantity': quantity,
                            'price': current_price,
                            'stop_loss': stop_loss_price,
                            'result': result,
                            'success': True
                        })
                        
                        logger.info(f"✅ BOUGHT {quantity} shares of {ticker} at ${current_price:.2f} (Stop: ${stop_loss_price:.2f})")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to buy {buy_rec['ticker']}: {str(e)}")
                        buy_results.append({
                            'ticker': buy_rec['ticker'],
                            'error': str(e),
                            'success': False
                        })
            
            # Summary
            successful_sells = len([r for r in sell_results if r.get('success')])
            successful_buys = len([r for r in buy_results if r.get('success')])
            
            logger.info(f"=== AI EXECUTION COMPLETE ===")
            logger.info(f"Successful sells: {successful_sells}")
            logger.info(f"Successful buys: {successful_buys}")
            
            # Update cached quotes for all holdings
            self.update_all_cached_quotes()
            
        except Exception as e:
            logger.error(f"Error in AI predictor execution: {str(e)}")
    
    def check_stop_losses(self):
        """Check stop losses for all holdings and execute sells if triggered"""
        try:
            logger.info("=== CHECKING STOP LOSSES ===")
            
            # Get all transactions with stop prices
            transactions = self.portfolio_service.get_transactions()
            holdings = self.portfolio_service.get_holdings()
            
            # Build map of current holdings with their stop prices
            stop_loss_map = {}
            for transaction in transactions:
                ticker = transaction['ticker']
                stop_price = transaction.get('stop_price', '')
                
                if stop_price and stop_price != '':
                    try:
                        stop_loss_map[ticker] = float(stop_price)
                    except (ValueError, TypeError):
                        continue
            
            if not stop_loss_map:
                logger.info("No stop losses set for current holdings")
                return
            
            logger.info(f"Monitoring {len(stop_loss_map)} positions with stop losses")
            
            stop_loss_triggered = []
            
            for holding in holdings:
                ticker = holding['ticker']
                quantity = holding['quantity']
                
                if ticker not in stop_loss_map:
                    continue
                
                stop_price = stop_loss_map[ticker]
                
                # Get current market price
                quote = self.stock_service.get_cached_quote(ticker, force_refresh=True)
                if not quote:
                    logger.warning(f"Failed to get current price for {ticker}")
                    continue
                
                current_price = quote['current_price']
                
                logger.info(f"{ticker}: Current ${current_price:.2f} vs Stop ${stop_price:.2f}")
                
                # Check if stop loss is triggered
                if current_price <= stop_price:
                    logger.warning(f"🚨 STOP LOSS TRIGGERED for {ticker}: ${current_price:.2f} <= ${stop_price:.2f}")
                    
                    try:
                        # Execute stop loss sell
                        result = self.portfolio_service.sell_stock(
                            ticker=ticker,
                            quantity=int(quantity),
                            price=stop_price,  # Sell at stop loss price
                            reason=f"Stop Loss Triggered: Current ${current_price:.2f} <= Stop ${stop_price:.2f}"
                        )
                        
                        stop_loss_triggered.append({
                            'ticker': ticker,
                            'quantity': quantity,
                            'stop_price': stop_price,
                            'current_price': current_price,
                            'result': result,
                            'success': True
                        })
                        
                        logger.info(f"✅ STOP LOSS EXECUTED: Sold {quantity} shares of {ticker} at ${stop_price:.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to execute stop loss for {ticker}: {str(e)}")
                        stop_loss_triggered.append({
                            'ticker': ticker,
                            'error': str(e),
                            'success': False
                        })
            
            if stop_loss_triggered:
                successful_stops = len([r for r in stop_loss_triggered if r.get('success')])
                logger.info(f"=== STOP LOSS CHECK COMPLETE: {successful_stops} positions sold ===")
            else:
                logger.info("=== STOP LOSS CHECK COMPLETE: No triggers ===")
            
            # Update cached quotes for all holdings
            self.update_all_cached_quotes()
            
        except Exception as e:
            logger.error(f"Error in stop loss check: {str(e)}")
    
    def update_all_cached_quotes(self):
        """Update cached quotes for all current holdings"""
        try:
            holdings = self.portfolio_service.get_holdings()
            logger.info(f"Updating cached quotes for {len(holdings)} holdings...")
            
            for holding in holdings:
                ticker = holding['ticker']
                quote = self.stock_service.get_cached_quote(ticker, force_refresh=True)
                if quote:
                    logger.info(f"Updated {ticker}: ${quote['current_price']:.2f} from {quote['api_source']}")
                else:
                    logger.warning(f"Failed to update quote for {ticker}")
                    
        except Exception as e:
            logger.error(f"Error updating cached quotes: {str(e)}")

def main():
    """Main scheduler loop"""
    scheduler = TradingScheduler()
    
    # Schedule AI predictor for 9:30 AM on weekdays
    schedule.every().monday.at("09:30").do(scheduler.run_ai_predictor_with_execution)
    schedule.every().tuesday.at("09:30").do(scheduler.run_ai_predictor_with_execution)
    schedule.every().wednesday.at("09:30").do(scheduler.run_ai_predictor_with_execution)
    schedule.every().thursday.at("09:30").do(scheduler.run_ai_predictor_with_execution)
    schedule.every().friday.at("09:30").do(scheduler.run_ai_predictor_with_execution)
    
    # Schedule stop loss checks at 10:00 AM, 12:00 PM, 2:00 PM, 3:30 PM on weekdays
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
        getattr(schedule.every(), day).at("10:00").do(scheduler.check_stop_losses)
        getattr(schedule.every(), day).at("12:00").do(scheduler.check_stop_losses)
        getattr(schedule.every(), day).at("14:00").do(scheduler.check_stop_losses)  # 2:00 PM
        getattr(schedule.every(), day).at("15:30").do(scheduler.check_stop_losses)  # 3:30 PM
    
    logger.info("Trading Scheduler started!")
    logger.info("Scheduled tasks:")
    logger.info("- AI Predictor + Auto-Execute: Weekdays at 9:30 AM")
    logger.info("- Stop Loss Monitoring: Weekdays at 10:00 AM, 12:00 PM, 2:00 PM, 3:30 PM")
    logger.info("Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    main()
