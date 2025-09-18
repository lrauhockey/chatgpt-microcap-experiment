#!/usr/bin/env python3
"""
Test script for AI Predictor Share Reduction Logic

This test validates that the AI predictor correctly reduces share quantities
when the total buy value exceeds available cash minus a $500 buffer.

Test scenario:
- Available cash: $10,000
- Cash buffer: $500
- Max investment: $9,500
- Mock stocks: ABC (100 shares @ $50), DEF (90 shares @ $50), HIJ (80 shares @ $50)
- Original total: $13,500 (exceeds budget)
- Expected: Shares reduced until total ≤ $9,500

"""

import sys
import os
import json
from datetime import datetime

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_predictor_service import AIStockPredictorService
from portfolio_service import PortfolioService

class MockStockService:
    """Mock stock service that doesn't call OpenAI or external APIs"""
    
    def get_current_price(self, symbol):
        """Return fixed price of $50 for all test stocks"""
        if symbol.upper() in ['ABC', 'DEF', 'HIJ']:
            return 50.0
        return None
    
    def get_stock_quote(self, symbol):
        """Return mock quote data"""
        if symbol.upper() in ['ABC', 'DEF', 'HIJ']:
            return {
                'symbol': symbol.upper(),
                'current_price': 50.0,
                'name': f'Mock Company {symbol.upper()}',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None

class TestShareReduction:
    """Test class for share reduction logic"""
    
    def __init__(self):
        self.ai_service = AIStockPredictorService()
        self.mock_stock_service = MockStockService()
        
    def create_mock_recommendations(self):
        """Create mock AI recommendations that exceed the budget"""
        return {
            'sell_decisions': [],
            'buy_recommendations': [
                {
                    'ticker': 'ABC',
                    'buy_price': 50.0,
                    'current_price': 50.0,
                    'quantity': 100,
                    'stop_loss_price': 42.50,
                    'reason': 'Strong growth potential in tech sector'
                },
                {
                    'ticker': 'DEF',
                    'buy_price': 50.0,
                    'current_price': 50.0,
                    'quantity': 90,
                    'stop_loss_price': 42.50,
                    'reason': 'Undervalued healthcare stock'
                },
                {
                    'ticker': 'HIJ',
                    'buy_price': 50.0,
                    'current_price': 50.0,
                    'quantity': 80,
                    'stop_loss_price': 42.50,
                    'reason': 'Clean energy growth opportunity'
                }
            ],
            'remaining_cash': 0
        }
    
    def test_share_reduction_logic(self):
        """Test the share reduction logic with mock data"""
        print("=" * 60)
        print("TESTING AI PREDICTOR SHARE REDUCTION LOGIC")
        print("=" * 60)
        
        # Test parameters
        available_cash = 10000.0
        cash_buffer = 500.0
        max_investment = available_cash - cash_buffer
        
        print(f"Test Setup:")
        print(f"  Available Cash: ${available_cash:,.2f}")
        print(f"  Cash Buffer: ${cash_buffer:,.2f}")
        print(f"  Max Investment: ${max_investment:,.2f}")
        print()
        
        # Create mock recommendations
        mock_recommendations = self.create_mock_recommendations()
        
        print("Original Mock Recommendations:")
        original_total = 0
        for i, rec in enumerate(mock_recommendations['buy_recommendations'], 1):
            cost = rec['quantity'] * rec['current_price']
            original_total += cost
            print(f"  {i}. {rec['ticker']}: {rec['quantity']} shares @ ${rec['current_price']:.2f} = ${cost:,.2f}")
        
        print(f"\nOriginal Total Cost: ${original_total:,.2f}")
        print(f"Exceeds Budget By: ${original_total - max_investment:,.2f}")
        print()
        
        # Apply share reduction logic
        print("Applying Share Reduction Logic...")
        print("-" * 40)
        
        final_recommendations = self.ai_service._apply_share_reduction_logic(
            mock_recommendations, 
            available_cash
        )
        
        print()
        print("=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        
        # Display final results
        final_buy_recs = final_recommendations.get('buy_recommendations', [])
        final_total = 0
        
        print("Final Recommendations:")
        for i, rec in enumerate(final_buy_recs, 1):
            original_qty = rec.get('original_quantity', 0)
            final_qty = rec.get('quantity', 0)
            shares_reduced = rec.get('shares_reduced_count', 0)
            final_cost = rec.get('final_cost', 0)
            final_total += final_cost
            
            print(f"  {i}. {rec['ticker']}:")
            print(f"     Original: {original_qty} shares")
            print(f"     Final: {final_qty} shares")
            print(f"     Reduced by: {shares_reduced} shares")
            print(f"     Final cost: ${final_cost:,.2f}")
            print(f"     Reason: {rec.get('reduction_reason', 'N/A')}")
            print()
        
        # Summary
        original_total_from_results = final_recommendations.get('original_total_cost', 0)
        final_total_from_results = final_recommendations.get('final_total_cost', 0)
        total_savings = final_recommendations.get('total_savings', 0)
        reduction_rounds = final_recommendations.get('reduction_rounds', 0)
        
        print("Summary:")
        print(f"  Original Total Cost: ${original_total_from_results:,.2f}")
        print(f"  Final Total Cost: ${final_total_from_results:,.2f}")
        print(f"  Total Savings: ${total_savings:,.2f}")
        print(f"  Reduction Rounds: {reduction_rounds}")
        print(f"  Remaining Cash After Trades: ${available_cash - final_total_from_results:,.2f}")
        print(f"  Cash Buffer Maintained: ${available_cash - final_total_from_results >= cash_buffer}")
        print()
        
        # Validation
        print("Validation:")
        success = True
        
        # Check if final total is within budget
        if final_total_from_results <= max_investment:
            print("  ✅ Final cost is within budget")
        else:
            print(f"  ❌ Final cost ${final_total_from_results:,.2f} exceeds budget ${max_investment:,.2f}")
            success = False
        
        # Check if cash buffer is maintained
        remaining_cash = available_cash - final_total_from_results
        if remaining_cash >= cash_buffer:
            print(f"  ✅ Cash buffer maintained (${remaining_cash:,.2f} >= ${cash_buffer:,.2f})")
        else:
            print(f"  ❌ Cash buffer not maintained (${remaining_cash:,.2f} < ${cash_buffer:,.2f})")
            success = False
        
        # Check if shares were actually reduced
        total_shares_reduced = sum(rec.get('shares_reduced_count', 0) for rec in final_buy_recs)
        if total_shares_reduced > 0:
            print(f"  ✅ Shares were reduced (total reduction: {total_shares_reduced} shares)")
        else:
            print("  ❌ No shares were reduced")
            success = False
        
        # Check if all stocks are still present (none reduced to 0)
        if len(final_buy_recs) == 3:
            print("  ✅ All 3 stocks maintained in portfolio")
        else:
            print(f"  ⚠️  Only {len(final_buy_recs)} stocks remaining (some reduced to 0 shares)")
        
        print()
        if success:
            print("🎉 TEST PASSED: Share reduction logic working correctly!")
        else:
            print("❌ TEST FAILED: Share reduction logic has issues!")
        
        return success
    
    def test_no_reduction_needed(self):
        """Test case where no reduction is needed"""
        print("\n" + "=" * 60)
        print("TESTING CASE: NO REDUCTION NEEDED")
        print("=" * 60)
        
        available_cash = 10000.0
        
        # Create recommendations that are within budget
        small_recommendations = {
            'sell_decisions': [],
            'buy_recommendations': [
                {
                    'ticker': 'ABC',
                    'buy_price': 50.0,
                    'current_price': 50.0,
                    'quantity': 50,  # $2,500
                    'stop_loss_price': 42.50,
                    'reason': 'Small position test'
                },
                {
                    'ticker': 'DEF',
                    'buy_price': 50.0,
                    'current_price': 50.0,
                    'quantity': 40,  # $2,000
                    'stop_loss_price': 42.50,
                    'reason': 'Small position test'
                }
            ],
            'remaining_cash': 0
        }
        
        original_total = sum(rec['quantity'] * rec['current_price'] for rec in small_recommendations['buy_recommendations'])
        print(f"Original Total: ${original_total:,.2f} (well within ${available_cash - 500:,.2f} budget)")
        
        result = self.ai_service._apply_share_reduction_logic(small_recommendations, available_cash)
        
        # Check that no reduction occurred
        shares_reduced = any(rec.get('shares_reduced', False) for rec in result.get('buy_recommendations', []))
        
        if not shares_reduced:
            print("✅ TEST PASSED: No reduction applied when within budget")
            return True
        else:
            print("❌ TEST FAILED: Reduction applied when not needed")
            return False

def main():
    """Run all tests"""
    print("Starting AI Predictor Share Reduction Tests...")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = TestShareReduction()
    
    # Run tests
    test1_passed = tester.test_share_reduction_logic()
    test2_passed = tester.test_no_reduction_needed()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Test 1 (Share Reduction): {'PASSED' if test1_passed else 'FAILED'}")
    print(f"Test 2 (No Reduction Needed): {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! Share reduction logic is working correctly.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED! Please review the share reduction logic.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
