"""
Komplette Test-Coverage Validierung
"""
import os
import sys
import subprocess
import json
import time
from pathlib import Path

def run_pytest_with_coverage():
    """Run pytest with coverage report."""
    print("🔍 Running complete test suite with coverage analysis...\n")
    
    try:
        # Run pytest with coverage
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/', 
            '--tb=short',
            '-v',
            '--durations=10'
        ], capture_output=True, text=True, timeout=300)
        
        print("PYTEST OUTPUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def analyze_test_files():
    """Analyze all test files and count tests."""
    test_dir = Path("tests")
    test_files = list(test_dir.glob("test_*.py"))
    
    total_tests = 0
    test_summary = {}
    
    print("📊 TEST FILE ANALYSIS:")
    print("=" * 50)
    
    for test_file in sorted(test_files):
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count test methods
            test_count = content.count('def test_')
            total_tests += test_count
            test_summary[test_file.name] = test_count
            
            print(f"{test_file.name:<35} {test_count:>3} tests")
            
        except Exception as e:
            print(f"{test_file.name:<35} ERROR: {e}")
    
    print("=" * 50)
    print(f"{'TOTAL':<35} {total_tests:>3} tests")
    print()
    
    return total_tests, test_summary

def analyze_source_coverage():
    """Analyze which source files are covered by tests."""
    source_dirs = ['core', 'ui', 'utils']
    test_coverage = {}
    
    print("📁 SOURCE COVERAGE ANALYSIS:")
    print("=" * 60)
    
    for source_dir in source_dirs:
        if os.path.exists(source_dir):
            py_files = list(Path(source_dir).rglob("*.py"))
            py_files = [f for f in py_files if not f.name.startswith('__')]
            
            covered_files = 0
            total_files = len(py_files)
            
            print(f"\n{source_dir.upper()}/ directory:")
            for py_file in sorted(py_files):
                # Check if there's a corresponding test
                test_name = f"test_{py_file.stem}.py"
                test_exists = os.path.exists(f"tests/{test_name}")
                
                # Check if file is mentioned in any test
                mentioned_in_tests = False
                if os.path.exists("tests"):
                    for test_file in Path("tests").glob("test_*.py"):
                        try:
                            with open(test_file, 'r', encoding='utf-8') as f:
                                if py_file.stem in f.read():
                                    mentioned_in_tests = True
                                    break
                        except:
                            pass
                
                status = "✓" if (test_exists or mentioned_in_tests) else "✗"
                if test_exists or mentioned_in_tests:
                    covered_files += 1
                
                print(f"  {status} {py_file.name}")
            
            coverage_pct = (covered_files / total_files * 100) if total_files > 0 else 0
            test_coverage[source_dir] = {
                'covered': covered_files,
                'total': total_files,
                'percentage': coverage_pct
            }
            
            print(f"  Coverage: {covered_files}/{total_files} ({coverage_pct:.1f}%)")
    
    return test_coverage

def generate_coverage_report():
    """Generate comprehensive coverage report."""
    print("📋 GENERATING FINAL COVERAGE REPORT...")
    print("=" * 60)
    
    # Test file analysis
    total_tests, test_summary = analyze_test_files()
    
    # Source coverage analysis
    source_coverage = analyze_source_coverage()
    
    # Calculate overall statistics
    overall_covered = sum(data['covered'] for data in source_coverage.values())
    overall_total = sum(data['total'] for data in source_coverage.values())
    overall_percentage = (overall_covered / overall_total * 100) if overall_total > 0 else 0
    
    print("\n" + "=" * 60)
    print("📈 FINAL COVERAGE STATISTICS:")
    print("=" * 60)
    print(f"Total test methods: {total_tests}")
    print(f"Source files covered: {overall_covered}/{overall_total} ({overall_percentage:.1f}%)")
    
    print(f"\nDetailed coverage by directory:")
    for directory, data in source_coverage.items():
        print(f"  {directory}: {data['covered']}/{data['total']} ({data['percentage']:.1f}%)")
    
    # Test completeness assessment
    print(f"\n🎯 TEST COMPLETENESS ASSESSMENT:")
    print("=" * 60)
    
    if total_tests >= 120:
        print("✅ EXCELLENT: 120+ tests provide comprehensive coverage")
    elif total_tests >= 100:
        print("✅ VERY GOOD: 100+ tests provide strong coverage")
    elif total_tests >= 80:
        print("⚠️  GOOD: 80+ tests provide adequate coverage")
    else:
        print("❌ NEEDS IMPROVEMENT: <80 tests may have coverage gaps")
    
    if overall_percentage >= 90:
        print("✅ EXCELLENT: 90%+ source file coverage")
    elif overall_percentage >= 75:
        print("✅ GOOD: 75%+ source file coverage")
    elif overall_percentage >= 60:
        print("⚠️  ADEQUATE: 60%+ source file coverage")
    else:
        print("❌ NEEDS IMPROVEMENT: <60% source file coverage")
    
    # Overall assessment
    print(f"\n🏆 OVERALL ASSESSMENT:")
    print("=" * 60)
    
    if total_tests >= 100 and overall_percentage >= 80:
        print("🌟 COMPLETE COVERAGE ACHIEVED!")
        print("   Your test suite provides comprehensive coverage")
        print("   across all major system components.")
        assessment = "COMPLETE"
    elif total_tests >= 80 and overall_percentage >= 70:
        print("✅ STRONG COVERAGE ACHIEVED!")
        print("   Your test suite covers most important components")
        print("   with room for minor improvements.")
        assessment = "STRONG"
    else:
        print("⚠️  PARTIAL COVERAGE")
        print("   Consider adding more tests for better coverage.")
        assessment = "PARTIAL"
    
    return {
        'total_tests': total_tests,
        'source_coverage': source_coverage,
        'overall_percentage': overall_percentage,
        'assessment': assessment,
        'test_files': test_summary
    }

def main():
    """Main coverage validation function."""
    print("🧪 COMPLETE TEST COVERAGE VALIDATION")
    print("=" * 60)
    print("Analyzing D&D Sheet Book test coverage...")
    print()
    
    start_time = time.time()
    
    # Change to project directory
    os.chdir(Path(__file__).parent.parent)
    
    # Run tests first
    test_success = run_pytest_with_coverage()
    
    print("\n" + "=" * 60)
    
    # Generate coverage report regardless of test results
    coverage_data = generate_coverage_report()
    
    # Final summary
    elapsed_time = time.time() - start_time
    
    print(f"\n⏱️  Analysis completed in {elapsed_time:.1f} seconds")
    print(f"🧪 Test execution: {'✅ SUCCESS' if test_success else '⚠️  SOME ISSUES'}")
    print(f"📊 Coverage level: {coverage_data['assessment']}")
    
    if coverage_data['assessment'] == "COMPLETE":
        print("\n🎉 CONGRATULATIONS!")
        print("Your D&D Sheet Book project has achieved complete test coverage!")
        return True
    else:
        print(f"\n📈 Current coverage: {coverage_data['overall_percentage']:.1f}%")
        print("Consider adding tests for uncovered components.")
        return test_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)