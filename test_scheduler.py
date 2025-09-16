#!/usr/bin/env python3
"""
Test script for the trading scheduler - allows manual testing of scheduled functions

"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scheduler import TradingScheduler

def test_ai_predictor():
    """Test the AI predictor with auto-execution"""
    print("=== TESTING AI PREDICTOR WITH AUTO-EXECUTION ===")
    scheduler = TradingScheduler()
    scheduler.run_ai_predictor_with_execution()

def test_stop_loss_check():
    """Test the stop loss monitoring"""
    print("=== TESTING STOP LOSS MONITORING ===")
    scheduler = TradingScheduler()
    scheduler.check_stop_losses()

def test_quote_updates():
    """Test quote cache updates"""
    print("=== TESTING QUOTE CACHE UPDATES ===")
    scheduler = TradingScheduler()
    scheduler.update_all_cached_quotes()

if __name__ == "__main__":
    print("Trading Scheduler Test Menu")
    print("1. Test AI Predictor + Auto-Execute")
    print("2. Test Stop Loss Monitoring")
    print("3. Test Quote Cache Updates")
    print("4. Exit")
    
    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            test_ai_predictor()
        elif choice == "2":
            test_stop_loss_check()
        elif choice == "3":
            test_quote_updates()
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter 1-4.")
