import openai
import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class AIStockPredictorService:
    """Service class to get AI-powered stock recommendations using OpenAI"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        openai.api_key = self.openai_api_key
    
    def get_stock_recommendations(self, portfolio_service, stock_service, use_openai_price=False) -> Dict:
        """Get AI recommendations for buying/selling stocks based on current portfolio"""
        try:
            # Get current portfolio data
            portfolio_summary = portfolio_service.get_portfolio_summary(stock_service)
            holdings = portfolio_summary['holdings']
            cash_balance = portfolio_summary['cash_balance']
            total_capital = portfolio_summary['total_portfolio_value']
            
            # Build the prompt with current portfolio data
            prompt = self._build_prompt(holdings, cash_balance, total_capital)
            
            print(f"=== OpenAI REQUEST ===")
            print(f"Portfolio Summary: Cash=${cash_balance:,.2f}, Total=${total_capital:,.2f}")
            print(f"Holdings: {len(holdings)} positions")
            print(f"Prompt: {prompt[:500]}..." if len(prompt) > 500 else f"Prompt: {prompt}")
            
            # Call OpenAI API with function calling for structured output
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # Define the function schema for structured output
            function_schema = {
                "name": "provide_stock_recommendations",
                "description": "Provide stock buy/sell recommendations based on portfolio analysis",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sell_decisions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "ticker": {"type": "string"},
                                    "action": {"type": "string", "enum": ["SELL", "HOLD", "TRIM"]},
                                    "reason": {"type": "string"}
                                },
                                "required": ["ticker", "action", "reason"]
                            }
                        },
                        "buy_recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "ticker": {"type": "string"},
                                    "buy_price": {"type": "number"},
                                    "quantity": {"type": "integer"},
                                    "stop_loss_price": {"type": "number"},
                                    "reason": {"type": "string"}
                                },
                                "required": ["ticker", "buy_price", "quantity", "stop_loss_price", "reason"]
                            }
                        },
                        "remaining_cash": {"type": "number"}
                    },
                    "required": ["sell_decisions", "buy_recommendations", "remaining_cash"]
                }
            }
            
            messages = [
                {
                    "role": "system", 
                    "content": "You are a professional stock analyst. Analyze the portfolio and provide structured recommendations."
                },
                {"role": "user", "content": prompt}
            ]
            
            print(f"=== OpenAI MESSAGES ===")
            for i, msg in enumerate(messages):
                print(f"Message {i+1} ({msg['role']}): {msg['content'][:200]}..." if len(msg['content']) > 200 else f"Message {i+1} ({msg['role']}): {msg['content']}")
            
            print(f"=== OpenAI FUNCTION SCHEMA ===")
            print(json.dumps(function_schema, indent=2))
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                functions=[function_schema],
                function_call={"name": "provide_stock_recommendations"},
                temperature=0.3,
                max_tokens=2000
            )
            
            print(f"=== OpenAI RESPONSE ===")
            print(f"Response object: {response}")
            print(f"Choice 0: {response.choices[0]}")
            print(f"Message: {response.choices[0].message}")
            
            # Parse the function call response
            function_call = response.choices[0].message.function_call
            if function_call and function_call.name == "provide_stock_recommendations":
                recommendations = json.loads(function_call.arguments)
                print(f"=== AI FUNCTION RESPONSE ===")
                print(f"Function name: {function_call.name}")
                print(f"Arguments: {function_call.arguments}")
                print(f"Parsed recommendations: {json.dumps(recommendations, indent=2)}")
            else:
                # Fallback to regular response parsing
                ai_response = response.choices[0].message.content.strip()
                print(f"AI Regular Response: {ai_response}")  # Debug logging
                
                # Clean up the response - remove any non-JSON content
                if not ai_response.startswith('{'):
                    start_idx = ai_response.find('{')
                    end_idx = ai_response.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        ai_response = ai_response[start_idx:end_idx+1]
                    else:
                        # Return empty recommendations if no valid JSON
                        return {
                            'success': True,
                            'recommendations': {
                                'sell_decisions': [],
                                'buy_recommendations': [],
                                'remaining_cash': cash_balance
                            },
                            'raw_response': ai_response,
                            'note': 'No valid recommendations found, returning empty set'
                        }
                
                recommendations = json.loads(ai_response)
            
            # Validate and enrich recommendations with current prices
            if use_openai_price:
                print("=== USING OPENAI PRICES (SKIPPING API VALIDATION) ===")
                validated_recommendations = self._use_openai_prices(recommendations)
            else:
                print("=== VALIDATING WITH STOCK APIs ===")
                validated_recommendations = self._validate_recommendations(recommendations, stock_service)
            
            return {
                'success': True,
                'recommendations': validated_recommendations,
                'raw_response': function_call.arguments if 'function_call' in locals() and function_call else ai_response,
                'used_openai_price': use_openai_price
            }
            
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse AI response as JSON: {str(e)}',
                'raw_response': ai_response if 'ai_response' in locals() else None,
                'debug_info': f'Response length: {len(ai_response) if "ai_response" in locals() else 0}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get AI recommendations: {str(e)}',
                'debug_info': f'Error type: {type(e).__name__}'
            }
    
    def _build_prompt(self, holdings: List[Dict], cash_balance: float, total_capital: float) -> str:
        """Build the prompt for OpenAI based on current portfolio"""
        
        # Format current holdings
        holdings_text = ""
        if holdings:
            for holding in holdings:
                # Calculate average purchase price from holdings data
                avg_cost = holding['average_cost']
                holdings_text += f"  - Ticker: {holding['ticker']} | Shares: {int(holding['quantity'])} | Purchase Price: ${avg_cost:.2f}\n"
        else:
            holdings_text = "  - No current holdings\n"
        
        # Determine investment strategy based on portfolio state
        if len(holdings) == 0:
            strategy_context = f"""
IMPORTANT: You have ${cash_balance:,.2f} in cash with NO current holdings. This is a fresh portfolio start.
You MUST recommend 2-3 high-quality small/mid-cap stocks to begin building the portfolio.
Focus on diversified sectors (tech, healthcare, industrials, consumer) with strong fundamentals.
Target stocks in the $15-50 price range for good position sizing.
"""
        else:
            strategy_context = f"""
Current portfolio has {len(holdings)} positions. Analyze each for SELL/HOLD/TRIM decisions.
Only recommend new buys if you have strong conviction and sufficient cash remains.
"""

        prompt = f"""You are an aggressive growth-focused stock analyst managing a ${total_capital:,.2f} small/mid-cap portfolio.

{strategy_context}

MANDATORY REQUIREMENTS:
- If cash > $2000: MUST recommend at least 2 BUY positions
- If cash > $5000: MUST recommend 3 BUY positions  
- Focus on US small/mid-cap stocks ($500M - $10B market cap)
- Target undervalued growth stocks with strong fundamentals
- Use current market prices (assume September 2024 data)
- CRITICAL: No single stock position should exceed 20% of total portfolio value
- With ${total_capital:,.0f} portfolio: Maximum position size is ${total_capital * 0.20:,.0f} per stock

### Current Portfolio Status
- Total Capital: ${total_capital:,.2f}
- Available Cash: ${cash_balance:,.2f}
- Current Holdings: {len(holdings)} positions
{holdings_text}

### Investment Targets (MUST RECOMMEND IF CASH AVAILABLE):
Focus on these high-growth sectors:
- Technology: AI/Cloud/Cybersecurity companies
- Healthcare: Biotech/Medical devices  
- Clean Energy: Solar/Battery/EV infrastructure
- Industrial: Automation/Robotics

### Stock Selection Criteria:
- Market cap: $500M - $10B
- P/E ratio: 15-30 (reasonable valuation)
- Revenue growth: >15% annually
- Strong balance sheet (low debt/equity)
- Insider buying activity preferred

### POSITION SIZING RULES FOR ${cash_balance:,.0f} CASH:
Since you have ${cash_balance:,.0f} available, you MUST provide these recommendations:

POSITION SIZING CONSTRAINTS:
- Maximum per stock: ${total_capital * 0.20:,.0f} (20% of ${total_capital:,.0f} portfolio)
- Target per position: ${total_capital * 0.15:,.0f} - ${total_capital * 0.18:,.0f} (15-18% of portfolio)
- Leave minimum $2000 cash buffer

Example BUY recommendations (REQUIRED):
- Stock 1: Target ~${total_capital * 0.16:,.0f} position (16% of portfolio)
- Stock 2: Target ~${total_capital * 0.15:,.0f} position (15% of portfolio)  
- Stock 3: Target ~${total_capital * 0.17:,.0f} position (17% of portfolio)

Calculate share quantities based on current stock prices to stay within these dollar limits.

### MANDATORY OUTPUT REQUIREMENTS:
- With ${cash_balance:,.0f} cash: MUST recommend exactly 3 BUY positions
- Use real ticker symbols from major exchanges (NYSE/NASDAQ)
- Calculate realistic quantities based on assumed current prices
- Set stop-loss 15-20% below buy price
- Provide specific, actionable recommendations"""

        return prompt
    
    def _validate_recommendations(self, recommendations: Dict, stock_service) -> Dict:
        """Validate stock symbols exist and get current prices"""
        validated = {
            'sell_decisions': [],
            'buy_recommendations': [],
            'remaining_cash': recommendations.get('remaining_cash', 0)
        }
        
        # Validate sell decisions
        for sell_decision in recommendations.get('sell_decisions', []):
            ticker = sell_decision.get('ticker', '').upper()
            if ticker:
                # Get current price to validate symbol exists
                quote = stock_service.get_stock_quote(ticker)
                if quote:
                    sell_decision['current_price'] = quote['current_price']
                    sell_decision['ticker'] = ticker
                    validated['sell_decisions'].append(sell_decision)
                else:
                    print(f"Warning: Could not validate sell ticker {ticker}")
        
        # Validate buy recommendations
        for buy_rec in recommendations.get('buy_recommendations', []):
            ticker = buy_rec.get('ticker', '').upper()
            if ticker:
                try:
                    # Get current price to validate symbol exists
                    current_price = stock_service.get_current_price(ticker)
                    if current_price and current_price > 0:
                        validated_buy = buy_rec.copy()
                        validated_buy['current_price'] = current_price
                        validated_buy['ticker'] = ticker
                        
                        # Fix stop loss if it's greater than current price
                        suggested_stop_loss = buy_rec.get('stop_loss_price', 0)
                        if suggested_stop_loss >= current_price:
                            # Set stop loss to 15% below current price
                            corrected_stop_loss = current_price * 0.85
                            validated_buy['stop_loss_price'] = round(corrected_stop_loss, 2)
                            validated_buy['stop_loss_corrected'] = True
                            print(f"Corrected stop loss for {ticker}: {suggested_stop_loss} -> {corrected_stop_loss:.2f} (15% below current ${current_price})")
                        else:
                            validated_buy['stop_loss_corrected'] = False
                        
                        validated['buy_recommendations'].append(validated_buy)
                except Exception as e:
                    print(f"Failed to validate buy recommendation for {ticker}: {e}")
                    # Fallback: Use AI-provided price if API validation fails
                    print(f"Using AI-provided price for {ticker} as fallback")
                    validated_buy = buy_rec.copy()
                    validated_buy['current_price'] = buy_rec.get('buy_price', 0)  # Use AI suggested price
                    validated_buy['ticker'] = ticker
                    validated_buy['api_validation_failed'] = True
                    
                    # Fix stop loss using AI price
                    ai_price = buy_rec.get('buy_price', 0)
                    suggested_stop_loss = buy_rec.get('stop_loss_price', 0)
                    if suggested_stop_loss >= ai_price and ai_price > 0:
                        corrected_stop_loss = ai_price * 0.85
                        validated_buy['stop_loss_price'] = round(corrected_stop_loss, 2)
                        validated_buy['stop_loss_corrected'] = True
                        print(f"Corrected stop loss for {ticker} using AI price: {suggested_stop_loss} -> {corrected_stop_loss:.2f} (15% below AI price ${ai_price})")
                    else:
                        validated_buy['stop_loss_corrected'] = False
                    
                    validated['buy_recommendations'].append(validated_buy)
                    continue
                    print(f"Warning: Could not validate buy ticker {ticker}")
        
        return validated
    
    def _use_openai_prices(self, recommendations: Dict) -> Dict:
        """Use OpenAI-provided prices without API validation"""
        validated = {
            'sell_decisions': [],
            'buy_recommendations': [],
            'remaining_cash': recommendations.get('remaining_cash', 0)
        }
        
        # Process sell decisions (no price validation needed)
        for sell_decision in recommendations.get('sell_decisions', []):
            ticker = sell_decision.get('ticker', '').upper()
            if ticker:
                validated_sell = sell_decision.copy()
                validated_sell['ticker'] = ticker
                validated_sell['current_price'] = 'OpenAI Price'  # Placeholder since sells don't need current price
                validated['sell_decisions'].append(validated_sell)
        
        # Process buy recommendations using OpenAI prices
        for buy_rec in recommendations.get('buy_recommendations', []):
            ticker = buy_rec.get('ticker', '').upper()
            if ticker:
                validated_buy = buy_rec.copy()
                validated_buy['ticker'] = ticker
                validated_buy['current_price'] = buy_rec.get('buy_price', 0)  # Use AI's suggested buy price as current price
                
                # Fix stop loss if it's greater than or equal to AI price
                ai_price = buy_rec.get('buy_price', 0)
                suggested_stop_loss = buy_rec.get('stop_loss_price', 0)
                if suggested_stop_loss >= ai_price and ai_price > 0:
                    corrected_stop_loss = ai_price * 0.85
                    validated_buy['stop_loss_price'] = round(corrected_stop_loss, 2)
                    validated_buy['stop_loss_corrected'] = True
                    print(f"Corrected stop loss for {ticker} using OpenAI price: {suggested_stop_loss} -> {corrected_stop_loss:.2f} (15% below OpenAI price ${ai_price})")
                else:
                    validated_buy['stop_loss_corrected'] = False
                
                validated_buy['using_openai_price'] = True
                validated['buy_recommendations'].append(validated_buy)
                print(f"Using OpenAI price for {ticker}: ${ai_price}")
        
        return validated
