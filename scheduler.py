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
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from matplotlib.patches import Rectangle
import smtplib
import ssl
from email.message import EmailMessage
import imaplib

# Load environment variables at startup
load_dotenv()

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
    
    def _send_portfolio_email(self, subject_suffix: str = ""):
        """Compose and send a portfolio summary email.
        Uses IMAPSERVER (as SMTP host), USERID, and PWD from environment.
        """
        try:
            # Gather portfolio data
            summary = self.portfolio_service.get_portfolio_summary(self.stock_service)
            cash_balance = summary['cash_balance']
            total_market_value = summary['total_market_value']
            total_portfolio_value = summary['total_portfolio_value']
            holdings = summary['holdings']

            starting_value = 10000.0
            gain_loss = total_portfolio_value - starting_value
            gain_loss_pct = (gain_loss / starting_value) * 100 if starting_value else 0.0

            # Build HTML table for holdings
            rows_html = []
            for h in holdings:
                qty = float(h.get('quantity', 0)) or 0.0
                avg_cost = float(h.get('average_cost', 0)) or 0.0
                current_price = (float(h.get('total_market_value', 0)) / qty) if qty > 0 else 0.0
                mv = float(h.get('total_market_value', 0))
                gl_dollar = (current_price - avg_cost) * qty
                gl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
                stop_price = h.get('stop_loss_price')
                rows_html.append(
                    f"<tr>"
                    f"<td>{h.get('ticker','')}</td>"
                    f"<td style='text-align:right'>{qty:,.0f}</td>"
                    f"<td style='text-align:right'>$ {avg_cost:,.2f}</td>"
                    f"<td style='text-align:right'>$ {current_price:,.2f}</td>"
                    f"<td style='text-align:right'>$ {mv:,.2f}</td>"
                    f"<td style='text-align:right'>$ {gl_dollar:+,.2f}</td>"
                    f"<td style='text-align:right'>{gl_pct:+.2f}%</td>"
                    f"<td style='text-align:right'>{('' if stop_price is None else f'$ {float(stop_price):,.2f}')}</td>"
                    f"</tr>"
                )

            holdings_table = (
                "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:Arial;font-size:13px'>"
                "<thead><tr style='background:#f2f2f2'>"
                "<th>Symbol</th><th>Quantity</th><th>Avg Cost</th><th>Current Price</th><th>Market Value</th><th>Gain/Loss $</th><th>Gain/Loss %</th><th>Stop Loss</th>"
                "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>"
            ) if holdings else "<p>No current holdings.</p>"

            # Optional stop loss summary
            stop_rows = []
            for h in holdings:
                if h.get('has_stop_loss'):
                    qty = float(h.get('quantity', 0)) or 0.0
                    current_price = (float(h.get('total_market_value', 0)) / qty) if qty > 0 else 0.0
                    stop_price = float(h.get('stop_loss_price')) if h.get('stop_loss_price') is not None else None
                    if stop_price is not None:
                        distance = current_price - stop_price
                        distance_pct = (distance / current_price * 100) if current_price > 0 else 0.0
                        stop_rows.append(
                            f"<tr>"
                            f"<td>{h.get('ticker','')}</td>"
                            f"<td style='text-align:right'>$ {current_price:,.2f}</td>"
                            f"<td style='text-align:right'>$ {stop_price:,.2f}</td>"
                            f"<td style='text-align:right'>$ {distance:,.2f} ({distance_pct:+.2f}%)</td>"
                            f"</tr>"
                        )

            stop_section = ""
            if stop_rows:
                stop_section = (
                    "<h3>Stop Loss Checks</h3>"
                    "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:Arial;font-size:13px'>"
                    "<thead><tr style='background:#f2f2f2'>"
                    "<th>Symbol</th><th>Current</th><th>Stop</th><th>Distance</th>"
                    "</tr></thead><tbody>" + "".join(stop_rows) + "</tbody></table>"
                )

            # Email content
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            subject = f"Portfolio Summary {subject_suffix} - {now_str}".strip()
            html_body = f"""
                <div style='font-family:Arial,sans-serif'>
                    <h2>Portfolio Summary</h2>
                    <p><b>As of:</b> {now_str}</p>
                    <ul>
                        <li><b>Current Cash Position:</b> $ {cash_balance:,.2f}</li>
                        <li><b>Current Total Holdings (Market Value):</b> $ {total_market_value:,.2f}</li>
                        <li><b>Total Portfolio Value:</b> $ {total_portfolio_value:,.2f}</li>
                        <li><b>Gain/Loss:</b> $ {gain_loss:+,.2f} ({gain_loss_pct:+.2f}%)</li>
                    </ul>
                    <h3>Holdings</h3>
                    {holdings_table}
                    {stop_section}
                </div>
            """

            text_body = (
                f"Portfolio Summary\n"
                f"As of: {now_str}\n\n"
                f"Current Cash Position: $ {cash_balance:,.2f}\n"
                f"Current Total Holdings (Market Value): $ {total_market_value:,.2f}\n"
                f"Total Portfolio Value: $ {total_portfolio_value:,.2f}\n"
                f"Gain/Loss: $ {gain_loss:+,.2f} ({gain_loss_pct:+.2f}%)\n\n"
                f"Holdings: {len(holdings)} positions\n"
            )

            # Email setup from env
            # Allow separate SMTP credentials; fallback to USERID and APP_PASSWORD only
            user = os.getenv('SMTP_USER') or os.getenv('USERID')
            # IMPORTANT: Do NOT fall back to shell PWD (current working directory)
            # as a password. Use only SMTP_PWD or APP_PASSWORD.
            pwd = os.getenv('SMTP_PWD') or os.getenv('APP_PASSWORD')
            to_addr = 'larzgold@yahoo.com'

            # Auto-detect Gmail defaults if USERID is Gmail and no explicit SMTP_HOST provided
            is_gmail = bool(user and user.lower().endswith('@gmail.com'))
            default_smtp_host = 'smtp.gmail.com' if is_gmail else (os.getenv('IMAPSERVER') or None)
            default_smtp_port = 465 if is_gmail else 587
            default_use_ssl = True if is_gmail else False

            host = os.getenv('SMTP_HOST') or default_smtp_host
            port = int(os.getenv('SMTP_PORT', str(default_smtp_port)))
            # Respect explicit setting; otherwise use Gmail default
            if 'SMTP_USE_SSL' in os.environ:
                use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
            else:
                use_ssl = default_use_ssl
            trust_all = os.getenv('SMTP_TRUST_ALL', 'false').lower() in ('1', 'true', 'yes')

            if not host or not user or not pwd:
                logger.error("Email not sent: IMAPSERVER/USERID/PWD not configured in environment")
                return

            msg = EmailMessage()
            msg['From'] = user
            msg['To'] = to_addr
            msg['Subject'] = subject
            msg.set_content(text_body)
            msg.add_alternative(html_body, subtype='html')

            # Log chosen configuration
            cred_source = 'SMTP_PWD' if os.getenv('SMTP_PWD') else ('APP_PASSWORD' if os.getenv('APP_PASSWORD') else 'UNKNOWN')
            logger.info(f"Email config: SMTP host={host}, port={port}, use_ssl={use_ssl}, trust_all={trust_all}, gmail={is_gmail}, cred_source={cred_source}")

            # Optional IMAP connectivity check (auth/host verification)
            do_imap_check = os.getenv('IMAP_CHECK', 'true').lower() in ('1', 'true', 'yes')
            inbox_folder = os.getenv('INBOX_FOLDER', 'INBOX')
            default_imap_host = 'imap.gmail.com' if is_gmail else (os.getenv('IMAPSERVER') or host)
            imap_host = os.getenv('IMAP_HOST') or default_imap_host
            if do_imap_check:
                try:
                    logger.info(f"IMAP check: connecting to {imap_host} as {user}")
                    with imaplib.IMAP4_SSL(imap_host, ssl_context=_context()) as imap_conn:
                        imap_conn.login(os.getenv('IMAP_USER') or user, os.getenv('IMAP_PWD') or pwd)
                        status, _ = imap_conn.select(inbox_folder)
                        logger.info(f"IMAP select {inbox_folder} -> {status}")
                        imap_conn.logout()
                except Exception as ie:
                    logger.warning(f"IMAP connectivity/auth check failed: {ie}")

            # Try sequence: STARTTLS -> plain SMTP -> SMTP_SSL
            smtp_debug = os.getenv('SMTP_DEBUG', 'false').lower() in ('1', 'true', 'yes')

            def _context():
                # Create SSL context, prefer certifi CA bundle when available
                try:
                    import certifi  # type: ignore
                    ctx = ssl.create_default_context(cafile=certifi.where())
                except Exception:
                    ctx = ssl.create_default_context()
                if trust_all:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                return ctx

            def try_starttls(h, p):
                context = _context()
                with smtplib.SMTP(h, p, timeout=20) as server:
                    if smtp_debug:
                        server.set_debuglevel(1)
                    code, ehlo_resp = server.ehlo()
                    logger.info(f"SMTP EHLO ({h}:{p}) -> {code}")
                    server.starttls(context=context)
                    code2, ehlo2 = server.ehlo()
                    logger.info(f"SMTP STARTTLS EHLO -> {code2}")
                    server.login(user, pwd)
                    server.send_message(msg)

            def try_plain(h, p):
                with smtplib.SMTP(h, p, timeout=20) as server:
                    if smtp_debug:
                        server.set_debuglevel(1)
                    code, ehlo_resp = server.ehlo()
                    logger.info(f"SMTP EHLO (plain {h}:{p}) -> {code}")
                    server.login(user, pwd)
                    server.send_message(msg)

            def try_ssl(h, p):
                context = _context()
                with smtplib.SMTP_SSL(h, p, context=context, timeout=20) as server:
                    if smtp_debug:
                        server.set_debuglevel(1)
                    code, ehlo_resp = server.ehlo()
                    logger.info(f"SMTP_SSL EHLO ({h}:{p}) -> {code}")
                    server.login(user, pwd)
                    server.send_message(msg)

            sent = False
            last_err = None

            try:
                if use_ssl:
                    try_ssl(host, port)
                else:
                    try_starttls(host, port)
                sent = True
            except Exception as e1:
                last_err = e1
                logger.warning(f"STARTTLS/SSL attempt failed: {e1}")
                # Retry plain SMTP on same port
                try:
                    try_plain(host, port)
                    sent = True
                except Exception as e2:
                    last_err = e2
                    logger.warning(f"Plain SMTP attempt failed: {e2}")
                    # Retry SMTP_SSL on typical SSL port if not already tried
                    try:
                        ssl_port = 465 if port != 465 else port
                        try_ssl(host, ssl_port)
                        sent = True
                    except Exception as e3:
                        last_err = e3
                        logger.error(f"SMTP_SSL fallback failed: {e3}")

            if not sent:
                raise last_err or RuntimeError("Unknown SMTP error")

            logger.info(f"📧 Portfolio email sent to {to_addr}")
        except Exception as e:
            logger.error(f"Failed to send portfolio email: {str(e)}")

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
            ai_result = self.ai_service.get_stock_recommendations(
                portfolio_service=self.portfolio_service,
                stock_service=self.stock_service,
                use_openai_price=False  # Use real market prices
            )
            
            if not ai_result or not ai_result.get('success'):
                logger.warning("No AI recommendations received or AI call unsuccessful")
                return
            
            # The AI service returns a wrapper dict with 'recommendations' key
            recommendations = ai_result.get('recommendations') or {}
            if not recommendations:
                logger.warning("AI result missing 'recommendations' content")
                return
            
            # Execute SELL orders first to free up cash
            sell_results = []
            if 'sell_decisions' in recommendations and recommendations['sell_decisions']:
                logger.info(f"Processing {len(recommendations['sell_decisions'])} SELL recommendations...")
                
                for sell_rec in recommendations['sell_decisions']:
                    try:
                        ticker = sell_rec['ticker']
                        action = sell_rec.get('action', 'HOLD')
                        
                        # Skip if action is HOLD
                        if action == 'HOLD':
                            logger.info(f"HOLDING {ticker} - no sell action needed")
                            continue
                        
                        # Get current holdings for this ticker
                        holdings = self.portfolio_service.get_holdings()
                        holding = next((h for h in holdings if h['ticker'] == ticker), None)
                        
                        if not holding:
                            logger.warning(f"No holding found for {ticker} - skipping sell")
                            continue
                        
                        # Calculate quantity to sell based on action
                        total_shares = int(holding['quantity'])
                        if action == 'SELL':
                            quantity_to_sell = total_shares  # Sell all shares
                        elif action == 'TRIM':
                            quantity_to_sell = max(1, total_shares // 2)  # Sell half, minimum 1
                        else:
                            logger.warning(f"Unknown action '{action}' for {ticker} - skipping")
                            continue
                        
                        # Prefer validated price from AI output if present for consistency with share reduction
                        current_price = sell_rec.get('current_price')
                        if not current_price or current_price <= 0:
                            # Get current market price (use same method as UI)
                            quote = self.stock_service.get_stock_quote(ticker)
                            if not quote:
                                logger.error(f"Failed to get current price for {ticker}")
                                continue
                            current_price = quote['current_price']
                        
                        # Ensure valid price
                        if current_price is None or current_price <= 0:
                            logger.error(f"Invalid price for {ticker}: {current_price}. Skipping sell.")
                            continue

                        # Execute sell
                        result = self.portfolio_service.sell_stock(
                            ticker=ticker,
                            quantity=quantity_to_sell,
                            price=current_price,
                            reason=f"AI Auto-{action}: {sell_rec.get('reason', 'AI recommendation')}"
                        )
                        
                        sell_results.append({
                            'ticker': ticker,
                            'action': action,
                            'quantity': quantity_to_sell,
                            'price': current_price,
                            'result': result,
                            'success': True
                        })
                        
                        logger.info(f"✅ {action} {quantity_to_sell} shares of {ticker} at ${current_price:.2f}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to {sell_rec.get('action', 'sell')} {sell_rec['ticker']}: {str(e)}")
                        sell_results.append({
                            'ticker': sell_rec['ticker'],
                            'action': sell_rec.get('action', 'SELL'),
                            'error': str(e),
                            'success': False
                        })
            
            # Execute BUY orders after sells are complete
            buy_results = []
            if 'buy_recommendations' in recommendations and recommendations['buy_recommendations']:
                # Refresh cash balance after sells
                cash_balance = self.portfolio_service.get_cash_balance()
                logger.info(f"Cash available for buys: ${cash_balance:.2f}")
                logger.info(f"Processing {len(recommendations['buy_recommendations'])} BUY recommendations...")
                
                for buy_rec in recommendations['buy_recommendations']:
                    try:
                        ticker = buy_rec['ticker']
                        quantity = buy_rec['quantity']
                        stop_loss_price = buy_rec.get('stop_loss_price')
                        
                        # Prefer validated price from AI output for consistency with share reduction
                        current_price = buy_rec.get('current_price') or buy_rec.get('buy_price')
                        if not current_price or current_price <= 0:
                            # Get current market price (use same method as UI)
                            quote = self.stock_service.get_stock_quote(ticker)
                            if not quote:
                                logger.error(f"Failed to get current price for {ticker}")
                                continue
                            current_price = quote['current_price']
                        if current_price is None or current_price <= 0:
                            logger.error(f"Invalid price for {ticker}: {current_price}. Skipping buy.")
                            continue
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
                        
                        stop_loss_str = f"${stop_loss_price:.2f}" if stop_loss_price else "None"
                        logger.info(f"✅ BOUGHT {quantity} shares of {ticker} at ${current_price:.2f} (Stop: {stop_loss_str})")
                        
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
            
            # Send portfolio email summary after execution
            self._send_portfolio_email(subject_suffix="- After AI Execution")
            
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
                
                # Get current market price (use same method as UI)
                quote = self.stock_service.get_stock_quote(ticker)
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
            
            # Send portfolio email summary after stop loss check
            self._send_portfolio_email(subject_suffix="- After Stop Loss Check")
            
        except Exception as e:
            logger.error(f"Error in stop loss check: {str(e)}")
    
    def update_all_cached_quotes(self):
        """Update cached quotes for all current holdings"""
        try:
            holdings = self.portfolio_service.get_holdings()
            logger.info(f"Updating cached quotes for {len(holdings)} holdings...")
            
            for holding in holdings:
                ticker = holding['ticker']
                quote = self.stock_service.get_stock_quote(ticker)
                if quote:
                    logger.info(f"Updated {ticker}: ${quote['current_price']:.2f} from {quote['api_source']}")
                else:
                    logger.warning(f"Failed to update quote for {ticker}")
                    
        except Exception as e:
            logger.error(f"Error updating cached quotes: {str(e)}")
    
    def generate_daily_portfolio_image(self):
        """Generate daily portfolio summary image at end of trading day"""
        try:
            logger.info("=== GENERATING DAILY PORTFOLIO IMAGE ===")
            
            # Create images directory if it doesn't exist
            images_dir = "images"
            os.makedirs(images_dir, exist_ok=True)
            
            # Get current date for filename
            today = datetime.now()
            filename = f"lrau_portfolio_{today.strftime('%Y_%m_%d')}.png"
            filepath = os.path.join(images_dir, filename)
            
            # Get portfolio data
            portfolio_summary = self.portfolio_service.get_portfolio_summary(self.stock_service)
            performance_data = self.portfolio_service.get_daily_performance()
            
            # Create figure with subplots
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Portfolio Summary - {today.strftime("%B %d, %Y")}', fontsize=16, fontweight='bold')
            
            # 1. Portfolio Overview (Top Left)
            self._create_portfolio_overview(ax1, portfolio_summary, today)
            
            # 2. Holdings Breakdown (Top Right)
            self._create_holdings_chart(ax2, portfolio_summary)
            
            # 3. Performance Chart (Bottom Left)
            self._create_performance_chart(ax3, performance_data)
            
            # 4. Key Metrics (Bottom Right)
            self._create_metrics_table(ax4, portfolio_summary, performance_data)
            
            # Adjust layout and save
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            logger.info(f"✅ Portfolio image saved: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Failed to generate portfolio image: {str(e)}")
    
    def _create_portfolio_overview(self, ax, portfolio_summary, date):
        """Create portfolio overview section"""
        ax.set_title("Portfolio Overview", fontweight='bold', fontsize=12)
        ax.axis('off')
        
        # Portfolio values
        total_value = portfolio_summary['total_portfolio_value']
        cash_balance = portfolio_summary['cash_balance']
        holdings_value = portfolio_summary['total_market_value']
        starting_value = 10000.0
        
        gain_loss = total_value - starting_value
        gain_loss_pct = (gain_loss / starting_value) * 100
        
        # Create text summary
        overview_text = f"""
Total Portfolio Value: ${total_value:,.2f}
Cash Balance: ${cash_balance:,.2f}
Holdings Value: ${holdings_value:,.2f}
Starting Value: ${starting_value:,.2f}

Total Gain/Loss: ${gain_loss:+,.2f}
Percentage Return: {gain_loss_pct:+.2f}%

Number of Holdings: {portfolio_summary['holdings_count']}
Date: {date.strftime('%Y-%m-%d %H:%M')}
        """
        
        # Color coding for gain/loss
        color = 'green' if gain_loss >= 0 else 'red'
        
        ax.text(0.05, 0.95, overview_text.strip(), transform=ax.transAxes, 
                fontsize=11, verticalalignment='top', fontfamily='monospace')
        
        # Add colored box for gain/loss
        if gain_loss != 0:
            box_text = f"{'PROFIT' if gain_loss > 0 else 'LOSS'}: ${abs(gain_loss):,.2f} ({gain_loss_pct:+.2f}%)"
            ax.text(0.05, 0.15, box_text, transform=ax.transAxes, 
                    fontsize=12, fontweight='bold', color=color,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.2))
    
    def _create_holdings_chart(self, ax, portfolio_summary):
        """Create holdings pie chart"""
        holdings = portfolio_summary['holdings']
        
        if not holdings:
            ax.set_title("No Holdings", fontweight='bold', fontsize=12)
            ax.text(0.5, 0.5, 'No current holdings', ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
            return
        
        # Prepare data for pie chart
        tickers = []
        values = []
        colors = plt.cm.Set3(range(len(holdings)))
        
        for holding in holdings:
            tickers.append(holding['ticker'])
            values.append(holding['total_market_value'])
        
        # Add cash as a slice if significant
        cash_balance = portfolio_summary['cash_balance']
        if cash_balance > 100:  # Only show cash if > $100
            tickers.append('CASH')
            values.append(cash_balance)
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(values, labels=tickers, autopct='%1.1f%%', 
                                         colors=colors, startangle=90)
        
        ax.set_title("Portfolio Allocation", fontweight='bold', fontsize=12)
        
        # Add legend with dollar values
        legend_labels = [f"{ticker}: ${value:,.0f}" for ticker, value in zip(tickers, values)]
        ax.legend(wedges, legend_labels, title="Holdings", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    
    def _create_performance_chart(self, ax, performance_data):
        """Create performance line chart"""
        if not performance_data:
            ax.set_title("No Performance Data", fontweight='bold', fontsize=12)
            ax.text(0.5, 0.5, 'No performance data available', ha='center', va='center', transform=ax.transAxes)
            return
        
        # Convert to DataFrame for easier plotting
        df = pd.DataFrame(performance_data)
        df['date'] = pd.to_datetime(df['date'])
        
        # Plot portfolio performance
        ax.plot(df['date'], df['portfolio_gain_loss_pct'], label='Portfolio', linewidth=2, color='blue')
        ax.plot(df['date'], df['spy_gain_loss_pct'], label='S&P 500 (SPY)', linewidth=2, color='red', alpha=0.7)
        
        # Format chart
        ax.set_title("Performance vs S&P 500", fontweight='bold', fontsize=12)
        ax.set_xlabel("Date")
        ax.set_ylabel("Return (%)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 10)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Add horizontal line at 0%
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    def _create_metrics_table(self, ax, portfolio_summary, performance_data):
        """Create key metrics table"""
        ax.set_title("Key Metrics", fontweight='bold', fontsize=12)
        ax.axis('off')
        
        # Calculate metrics
        total_value = portfolio_summary['total_portfolio_value']
        starting_value = 10000.0
        
        metrics = []
        
        # Basic metrics
        metrics.append(["Starting Capital", f"${starting_value:,.2f}"])
        metrics.append(["Current Value", f"${total_value:,.2f}"])
        metrics.append(["Total Return", f"${total_value - starting_value:+,.2f}"])
        metrics.append(["Total Return %", f"{((total_value - starting_value) / starting_value) * 100:+.2f}%"])
        
        # Performance metrics if available
        if performance_data:
            latest = performance_data[-1]
            metrics.append(["", ""])  # Spacer
            metrics.append(["Portfolio Return", f"{latest['portfolio_gain_loss_pct']:+.2f}%"])
            metrics.append(["S&P 500 Return", f"{latest['spy_gain_loss_pct']:+.2f}%"])
            
            outperformance = latest['portfolio_gain_loss_pct'] - latest['spy_gain_loss_pct']
            metrics.append(["Outperformance", f"{outperformance:+.2f}%"])
        
        # Holdings metrics
        holdings = portfolio_summary['holdings']
        if holdings:
            metrics.append(["", ""])  # Spacer
            metrics.append(["Number of Holdings", str(len(holdings))])
            
            # Largest holding
            largest = max(holdings, key=lambda x: x['total_market_value'])
            largest_pct = (largest['total_market_value'] / total_value) * 100
            metrics.append(["Largest Position", f"{largest['ticker']} ({largest_pct:.1f}%)"])
            
            # Cash percentage
            cash_pct = (portfolio_summary['cash_balance'] / total_value) * 100
            metrics.append(["Cash Allocation", f"{cash_pct:.1f}%"])
        
        # Create table
        table_data = []
        for metric in metrics:
            if len(metric) == 2 and metric[0]:  # Skip empty spacers
                table_data.append(metric)
        
        # Display as text (matplotlib table can be tricky)
        y_pos = 0.95
        for metric, value in table_data:
            ax.text(0.05, y_pos, f"{metric}:", transform=ax.transAxes, 
                   fontsize=10, fontweight='bold', verticalalignment='top')
            ax.text(0.65, y_pos, value, transform=ax.transAxes, 
                   fontsize=10, verticalalignment='top', fontfamily='monospace')
            y_pos -= 0.08

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
        getattr(schedule.every(), day).at("16:30").do(scheduler.generate_daily_portfolio_image)  # 4:30 PM
    
    logger.info("Trading Scheduler started!")
    logger.info("Scheduled tasks:")
    logger.info("- AI Predictor + Auto-Execute: Weekdays at 9:30 AM")
    logger.info("- Stop Loss Monitoring: Weekdays at 10:00 AM, 12:00 PM, 2:00 PM, 3:30 PM")
    logger.info("- Daily Portfolio Image: Weekdays at 4:30 PM")
    logger.info("Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

if __name__ == "__main__":
    main()
