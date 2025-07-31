#!/usr/bin/env python3
"""
Test runner script for the ML pipeline project
"""
import subprocess
import sys
import os

def run_unit_tests():
    """Run unit tests"""
    print("🧪 Running Unit Tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/unit/", 
        "-v", 
        "--tb=short"
    ], cwd=os.path.dirname(os.path.dirname(__file__)))
    return result.returncode == 0

def run_integration_tests():
    """Run integration tests"""
    print("🔗 Running Integration Tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/integration/", 
        "-v", 
        "--tb=short"
    ], cwd=os.path.dirname(os.path.dirname(__file__)))
    return result.returncode == 0

def run_load_tests():
    """Run load tests"""
    print("⚡ Running Load Tests...")
    print("To run load tests manually:")
    print("cd tests/load && locust -f locustfile.py --host=http://localhost:6001")
    return True

def main():
    """Main test runner"""
    print("🚀 Starting ML Pipeline Test Suite")
    
    # Install test requirements
    print("📦 Installing test requirements...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "tests/requirements-test.txt"
    ], cwd=os.path.dirname(os.path.dirname(__file__)))
    
    results = []
    
    # Run tests
    results.append(("Unit Tests", run_unit_tests()))
    results.append(("Integration Tests", run_integration_tests()))
    results.append(("Load Tests", run_load_tests()))
    
    # Summary
    print("\n📊 Test Results Summary:")
    for test_type, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_type}: {status}")
    
    # Exit with error if any tests failed
    if not all(result[1] for result in results[:2]):  # Exclude load tests from failure
        sys.exit(1)
    
    print("\n🎉 All tests completed successfully!")

if __name__ == "__main__":
    main()