#!/usr/bin/env python3
"""
Simple test runner for the market maker system.
Run this script to execute comprehensive tests before production deployment.
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Run the comprehensive test suite."""
    print("🚀 Hyperliquid Market Maker - Test Runner")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("src") or not os.path.exists("tests"):
        print("❌ Error: Please run this script from the project root directory")
        print("   (where src/ and tests/ folders are located)")
        return False
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment not detected")
        print("   Consider activating your virtual environment first")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Install required dependencies
    print("\n📦 Checking dependencies...")
    try:
        import psutil
        print("✅ psutil is available")
    except ImportError:
        print("📥 Installing psutil...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil==6.1.0"])
        print("✅ psutil installed")
    
    # Run the comprehensive test suite
    print("\n🧪 Running comprehensive test suite...")
    test_script = os.path.join("tests", "run_all_tests.py")
    
    if not os.path.exists(test_script):
        print(f"❌ Test script not found: {test_script}")
        return False
    
    try:
        result = subprocess.run([sys.executable, test_script], check=True)
        print("\n🎉 All tests completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code: {e.returncode}")
        return False
    except KeyboardInterrupt:
        print("\n⏹️  Test execution interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1) 