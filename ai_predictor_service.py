import openai
import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
# 
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
                                    "quantity": {"type": "integer"},
                                    "current_price": {"type": "number"},
                                    "reason": {"type": "string"}
                                },
                                "required": ["ticker", "action", "quantity", "current_price", "reason"]
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
            
            # Apply share reduction logic to ensure we don't exceed available cash
            final_recommendations = self._apply_share_reduction_logic(validated_recommendations, cash_balance)
            
            return {
                'success': True,
                'recommendations': final_recommendations,
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
        
        # Format current holdings with detailed analysis requirements
        holdings_text = ""
        if holdings:
            for holding in holdings:
                # Calculate average purchase price from holdings data
                avg_cost = holding['average_cost']
                quantity = int(holding['quantity'])
                market_value = holding['total_market_value']
                current_price = market_value / quantity if quantity > 0 else 0
                gain_loss = market_value - (quantity * avg_cost)
                gain_loss_pct = (gain_loss / (quantity * avg_cost)) * 100 if quantity * avg_cost > 0 else 0
                
                holdings_text += f"  - {holding['ticker']}: {quantity} shares @ ${avg_cost:.2f} avg cost | Current: ${current_price:.2f} | P&L: ${gain_loss:+.2f} ({gain_loss_pct:+.1f}%)\n"
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
CRITICAL: Current portfolio has {len(holdings)} positions. You MUST analyze EACH holding for sell decisions:

SELL DECISION REQUIREMENTS:
- For EACH current holding, you MUST provide a sell_decision with:
  * ticker: The stock symbol
  * action: "SELL" (sell all shares), "TRIM" (sell partial), or "HOLD" (keep all)
  * quantity: Number of shares to sell (0 for HOLD, partial for TRIM, all shares for SELL)
  * current_price: Use current market price (assume September 2024 data)
  * reason: Specific reason for the decision

SELL CRITERIA:
- SELL if: Stock is overvalued, fundamentals deteriorated, better opportunities exist
- TRIM if: Position is too large (>20% of portfolio), take some profits, rebalance
- HOLD if: Stock still has strong fundamentals and growth potential

You must provide sell decisions for ALL current holdings, even if the decision is HOLD.
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
        
        # Validate sell decisions with current prices
        for sell_decision in recommendations.get('sell_decisions', []):
            ticker = sell_decision.get('ticker', '').upper()
            if ticker:
                try:
                    # Get current price to validate symbol exists and update price
                    current_price = stock_service.get_current_price(ticker)
                    if current_price and current_price > 0:
                        validated_sell = sell_decision.copy()
                        validated_sell['current_price'] = current_price  # Use real current price
                        validated_sell['ticker'] = ticker
                        
                        # Ensure quantity is valid
                        quantity = sell_decision.get('quantity', 0)
                        if quantity < 0:
                            validated_sell['quantity'] = 0
                        
                        validated['sell_decisions'].append(validated_sell)
                        print(f"Validated sell decision for {ticker}: {sell_decision.get('action')} {quantity} shares @ ${current_price:.2f}")
                    else:
                        print(f"Warning: Could not get current price for sell ticker {ticker}")
                except Exception as e:
                    print(f"Failed to validate sell decision for {ticker}: {e}")
                    # Fallback: Use AI-provided price
                    validated_sell = sell_decision.copy()
                    validated_sell['ticker'] = ticker
                    validated_sell['api_validation_failed'] = True
                    validated['sell_decisions'].append(validated_sell)
                    print(f"Using AI-provided price for sell decision {ticker}")
        
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
        
        # Process sell decisions using OpenAI prices
        for sell_decision in recommendations.get('sell_decisions', []):
            ticker = sell_decision.get('ticker', '').upper()
            if ticker:
                validated_sell = sell_decision.copy()
                validated_sell['ticker'] = ticker
                # Use AI-provided current price for sell decisions
                ai_price = sell_decision.get('current_price', 0)
                validated_sell['current_price'] = ai_price
                validated_sell['using_openai_price'] = True
                
                # Ensure quantity is valid
                quantity = sell_decision.get('quantity', 0)
                if quantity < 0:
                    validated_sell['quantity'] = 0
                
                validated['sell_decisions'].append(validated_sell)
                print(f"Using OpenAI price for sell decision {ticker}: {sell_decision.get('action')} {quantity} shares @ ${ai_price:.2f}")
        
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
    
    def _apply_share_reduction_logic(self, recommendations: Dict, available_cash: float) -> Dict:
        """Apply share reduction logic to ensure total buy value doesn't exceed available cash minus $500 buffer"""
        
        # Keep $500 minimum cash buffer
        CASH_BUFFER = 500.0
        max_investment = available_cash - CASH_BUFFER
        
        print(f"=== SHARE REDUCTION LOGIC ===")
        print(f"Available Cash: ${available_cash:,.2f}")
        print(f"Cash Buffer: ${CASH_BUFFER:,.2f}")
        print(f"Max Investment: ${max_investment:,.2f}")
        
        buy_recommendations = recommendations.get('buy_recommendations', [])
        
        if not buy_recommendations:
            print("No buy recommendations to process")
            return recommendations
        
        # Calculate total cost of all buy recommendations
        total_original_cost = 0
        for buy_rec in buy_recommendations:
            price = buy_rec.get('current_price', buy_rec.get('buy_price', 0))
            quantity = buy_rec.get('quantity', 0)
            cost = price * quantity
            total_original_cost += cost
            buy_rec['original_quantity'] = quantity
            buy_rec['original_cost'] = cost
            print(f"Original: {buy_rec['ticker']} - {quantity} shares @ ${price:.2f} = ${cost:,.2f}")
        
        print(f"Total Original Cost: ${total_original_cost:,.2f}")
        
        # If total cost is within budget, no reduction needed
        if total_original_cost <= max_investment:
            print("✅ Total cost is within budget - no reduction needed")
            for buy_rec in buy_recommendations:
                buy_rec['shares_reduced'] = False
                buy_rec['reduction_reason'] = "No reduction needed - within budget"
            return recommendations
        
        # Need to reduce shares - reduce each stock by 1 share iteratively until within budget
        print(f"❌ Total cost ${total_original_cost:,.2f} exceeds max investment ${max_investment:,.2f}")
        print("🔄 Starting share reduction process...")
        
        reduction_rounds = 0
        while True:
            # Calculate current total cost
            current_total_cost = 0
            for buy_rec in buy_recommendations:
                price = buy_rec.get('current_price', buy_rec.get('buy_price', 0))
                quantity = buy_rec.get('quantity', 0)
                current_total_cost += price * quantity
            
            print(f"Round {reduction_rounds + 1}: Current total cost = ${current_total_cost:,.2f}")
            
            # If we're within budget, we're done
            if current_total_cost <= max_investment:
                print(f"✅ Achieved target! Final cost: ${current_total_cost:,.2f} (under ${max_investment:,.2f})")
                break
            
            # Reduce each stock by 1 share (if they have shares left)
            reductions_made = False
            for buy_rec in buy_recommendations:
                if buy_rec.get('quantity', 0) > 0:
                    buy_rec['quantity'] -= 1
                    reductions_made = True
                    price = buy_rec.get('current_price', buy_rec.get('buy_price', 0))
                    print(f"  Reduced {buy_rec['ticker']} by 1 share (now {buy_rec['quantity']} shares)")
            
            # If no reductions were made (all stocks at 0 shares), break to avoid infinite loop
            if not reductions_made:
                print("⚠️ All stocks reduced to 0 shares - stopping reduction")
                break
            
            reduction_rounds += 1
            
            # Safety check to prevent infinite loops
            if reduction_rounds > 1000:
                print("⚠️ Too many reduction rounds - stopping for safety")
                break
        
        # Calculate final costs and mark reductions
        final_total_cost = 0
        for buy_rec in buy_recommendations:
            price = buy_rec.get('current_price', buy_rec.get('buy_price', 0))
            final_quantity = buy_rec.get('quantity', 0)
            original_quantity = buy_rec.get('original_quantity', 0)
            final_cost = price * final_quantity
            final_total_cost += final_cost
            
            shares_reduced = original_quantity - final_quantity
            buy_rec['shares_reduced'] = shares_reduced > 0
            buy_rec['shares_reduced_count'] = shares_reduced
            buy_rec['final_cost'] = final_cost
            
            if shares_reduced > 0:
                buy_rec['reduction_reason'] = f"Reduced by {shares_reduced} shares to stay within budget"
                print(f"📉 {buy_rec['ticker']}: {original_quantity} → {final_quantity} shares (reduced by {shares_reduced})")
                print(f"   Cost: ${buy_rec['original_cost']:,.2f} → ${final_cost:,.2f} (saved ${buy_rec['original_cost'] - final_cost:,.2f})")
            else:
                buy_rec['reduction_reason'] = "No reduction needed"
        
        # Remove any stocks that ended up with 0 shares
        buy_recommendations = [rec for rec in buy_recommendations if rec.get('quantity', 0) > 0]
        
        print(f"=== FINAL RESULTS ===")
        print(f"Original total cost: ${total_original_cost:,.2f}")
        print(f"Final total cost: ${final_total_cost:,.2f}")
        print(f"Total savings: ${total_original_cost - final_total_cost:,.2f}")
        print(f"Remaining cash after trades: ${available_cash - final_total_cost:,.2f}")
        print(f"Final recommendations: {len(buy_recommendations)} stocks")
        
        # Update the recommendations
        recommendations['buy_recommendations'] = buy_recommendations
        recommendations['share_reduction_applied'] = True
        recommendations['original_total_cost'] = total_original_cost
        recommendations['final_total_cost'] = final_total_cost
        recommendations['total_savings'] = total_original_cost - final_total_cost
        recommendations['reduction_rounds'] = reduction_rounds
        
        return recommendations
