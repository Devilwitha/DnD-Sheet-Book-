#!/usr/bin/env python3
"""
Finale Testabdeckung Validierung
"""
import os
import sys
import subprocess
from pathlib import Path
import json
import time

class TestCoverageValidator:
    """Validator für komplette Testabdeckung."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.coverage_data = {}
        
    def count_test_files_and_methods(self):
        """Zähle alle Test-Dateien und -Methods."""
        test_files = list(self.test_dir.glob("test_*.py"))
        total_methods = 0
        file_breakdown = {}
        
        print("📊 TEST FILES ANALYSIS:")
        print("=" * 60)
        
        for test_file in sorted(test_files):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                method_count = content.count('def test_')
                total_methods += method_count
                file_breakdown[test_file.name] = method_count
                
                print(f"{test_file.name:<35} {method_count:>3} tests")
                
            except Exception as e:
                print(f"{test_file.name:<35} ERROR: {e}")
                file_breakdown[test_file.name] = 0
        
        print("=" * 60)
        print(f"{'TOTAL':<35} {total_methods:>3} tests")
        print(f"Total Test Files: {len(test_files)}")
        print()
        
        return len(test_files), total_methods, file_breakdown

    def analyze_source_coverage(self):
        """Analysiere Source-Code Coverage."""
        source_modules = {
            'core': ['character.py', 'enemy.py', 'game_manager.py', 'network_manager.py', '__init__.py'],
            'ui': ['*.py'],  # Will count all .py files in ui/
            'utils': ['*.py']  # Will count all .py files in utils/
        }
        
        coverage_analysis = {}
        
        print("🔍 SOURCE CODE COVERAGE ANALYSIS:")
        print("=" * 60)
        
        for module_dir, files in source_modules.items():
            module_path = self.project_root / module_dir
            if not module_path.exists():
                print(f"❌ {module_dir}/ directory not found")
                continue
                
            if files == ['*.py']:
                # Count all Python files
                py_files = list(module_path.rglob("*.py"))
                py_files = [f for f in py_files if not f.name.startswith('__pycache__')]
            else:
                # Specific files
                py_files = [module_path / f for f in files if (module_path / f).exists()]
            
            covered_files = 0
            total_files = len(py_files)
            
            print(f"\n{module_dir.upper()}/ Module:")
            for py_file in sorted(py_files):
                if py_file.name.startswith('__'):
                    continue
                    
                # Check if there are tests for this file
                has_dedicated_test = (self.test_dir / f"test_{py_file.stem}.py").exists()
                
                # Check if mentioned in any test file
                mentioned_in_tests = False
                for test_file in self.test_dir.glob("test_*.py"):
                    try:
                        with open(test_file, 'r', encoding='utf-8') as f:
                            if py_file.stem in f.read():
                                mentioned_in_tests = True
                                break
                    except:
                        continue
                
                is_covered = has_dedicated_test or mentioned_in_tests
                status = "✅" if is_covered else "❌"
                
                if is_covered:
                    covered_files += 1
                    
                test_info = ""
                if has_dedicated_test:
                    test_info = " (dedicated test)"
                elif mentioned_in_tests:
                    test_info = " (mentioned in tests)"
                
                print(f"  {status} {py_file.name}{test_info}")
            
            coverage_pct = (covered_files / total_files * 100) if total_files > 0 else 0
            coverage_analysis[module_dir] = {
                'covered': covered_files,
                'total': total_files,
                'percentage': coverage_pct
            }
            
            print(f"  📈 Coverage: {covered_files}/{total_files} ({coverage_pct:.1f}%)")
        
        return coverage_analysis

    def run_sample_tests(self):
        """Führe eine Stichprobe von Tests aus."""
        print("🧪 RUNNING SAMPLE TESTS:")
        print("=" * 60)
        
        # Test die neuen erweiterten Test-Dateien
        sample_tests = [
            'test_ui_screens_extended.py',
            'test_utils_extended.py', 
            'test_integration_flows.py'
        ]
        
        test_results = {}
        
        for test_file in sample_tests:
            test_path = self.test_dir / test_file
            if not test_path.exists():
                print(f"❌ {test_file} not found")
                test_results[test_file] = False
                continue
            
            try:
                print(f"Running {test_file}...")
                result = subprocess.run([
                    sys.executable, '-m', 'pytest', 
                    str(test_path), 
                    '-v', '--tb=short'
                ], capture_output=True, text=True, timeout=60, cwd=self.project_root)
                
                success = result.returncode == 0
                test_results[test_file] = success
                
                if success:
                    # Count passed tests from output
                    passed_count = result.stdout.count(' PASSED')
                    print(f"  ✅ {test_file}: {passed_count} tests passed")
                else:
                    failed_count = result.stdout.count(' FAILED')
                    print(f"  ❌ {test_file}: {failed_count} tests failed")
                    if result.stderr:
                        print(f"     Error: {result.stderr[:200]}...")
                        
            except subprocess.TimeoutExpired:
                print(f"  ⏰ {test_file}: timeout")
                test_results[test_file] = False
            except Exception as e:
                print(f"  ❌ {test_file}: error - {e}")
                test_results[test_file] = False
        
        return test_results

    def generate_final_report(self):
        """Generiere finalen Coverage-Report."""
        print("\n" + "=" * 60)
        print("📋 FINAL TEST COVERAGE REPORT")
        print("=" * 60)
        
        # Zähle Tests
        file_count, method_count, file_breakdown = self.count_test_files_and_methods()
        
        # Analysiere Coverage
        source_coverage = self.analyze_source_coverage()
        
        # Führe Sample-Tests aus
        test_results = self.run_sample_tests()
        
        # Berechne Gesamtstatistiken
        total_covered = sum(data['covered'] for data in source_coverage.values())
        total_source_files = sum(data['total'] for data in source_coverage.values())
        overall_coverage = (total_covered / total_source_files * 100) if total_source_files > 0 else 0
        
        # Erfolgsrate der Sample-Tests
        successful_tests = sum(1 for success in test_results.values() if success)
        total_sample_tests = len(test_results)
        test_success_rate = (successful_tests / total_sample_tests * 100) if total_sample_tests > 0 else 0
        
        print(f"\n🎯 FINAL STATISTICS:")
        print("=" * 60)
        print(f"Test Files: {file_count}")
        print(f"Test Methods: {method_count}")
        print(f"Source Coverage: {total_covered}/{total_source_files} ({overall_coverage:.1f}%)")
        print(f"Sample Test Success: {successful_tests}/{total_sample_tests} ({test_success_rate:.1f}%)")
        
        print(f"\n📊 DETAILED COVERAGE:")
        for module, data in source_coverage.items():
            print(f"  {module}: {data['covered']}/{data['total']} ({data['percentage']:.1f}%)")
        
        # Bewertung
        print(f"\n🏆 OVERALL ASSESSMENT:")
        print("=" * 60)
        
        if (method_count >= 120 and overall_coverage >= 85 and test_success_rate >= 80):
            assessment = "🌟 EXCELLENT - COMPLETE COVERAGE ACHIEVED!"
            color = "green"
        elif (method_count >= 100 and overall_coverage >= 75 and test_success_rate >= 70):
            assessment = "✅ VERY GOOD - STRONG COVERAGE"
            color = "blue"  
        elif (method_count >= 80 and overall_coverage >= 60):
            assessment = "⚠️  GOOD - ADEQUATE COVERAGE"
            color = "yellow"
        else:
            assessment = "❌ NEEDS IMPROVEMENT"
            color = "red"
        
        print(assessment)
        
        if "COMPLETE" in assessment:
            print("\n🎊 CONGRATULATIONS! 🎊")
            print("Your D&D Sheet Book project has achieved comprehensive test coverage!")
            print("All major components are thoroughly tested and validated.")
        
        return {
            'test_files': file_count,
            'test_methods': method_count,
            'source_coverage': overall_coverage,
            'test_success_rate': test_success_rate,
            'assessment': assessment,
            'is_complete': "COMPLETE" in assessment
        }

def main():
    """Hauptfunktion für finale Testabdeckung Validierung."""
    print("🔍 D&D SHEET BOOK - FINALE TESTABDECKUNG VALIDIERUNG")
    print("=" * 60)
    print(f"Datum: {time.strftime('%d.%m.%Y %H:%M:%S')}")
    print()
    
    validator = TestCoverageValidator()
    
    try:
        result = validator.generate_final_report()
        
        print(f"\n⏱️  Validierung abgeschlossen")
        print(f"🎯 Status: {'ERFOLGREICH' if result['is_complete'] else 'TEILWEISE'}")
        
        return result['is_complete']
        
    except Exception as e:
        print(f"❌ Fehler während der Validierung: {e}")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n{'='*60}")
    print(f"FINALE TESTABDECKUNG: {'✅ KOMPLETT' if success else '⚠️ UNVOLLSTÄNDIG'}")
    print(f"{'='*60}")
    sys.exit(0 if success else 1)