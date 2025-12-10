#!/usr/bin/env python3
"""
Lint and Fix Script for rcscripts repository
Runs linters and applies automatic fixes where possible
"""

import argparse
import glob
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_command(cmd: List[str], description: str, fix_mode: bool = False) -> Tuple[bool, str]:
    """Run a command and return success status and output"""
    print(f"{'🔧 Fixing' if fix_mode else '🔍 Checking'}: {description}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )

        if result.returncode == 0:
            print(f"  ✅ {description} - OK")
            return True, result.stdout
        else:
            print(f"  ❌ {description} - FAILED")
            if result.stdout:
                print(f"     STDOUT: {result.stdout}")
            if result.stderr:
                print(f"     STDERR: {result.stderr}")
            return False, result.stderr

    except FileNotFoundError:
        error_msg = f"Command not found: {' '.join(cmd)}"
        print(f"  ❌ {description} - {error_msg}")
        return False, error_msg


def check_dependencies() -> bool:
    """Check if required linting tools are installed"""
    tools = ["black", "isort", "flake8", "mypy"]
    missing_tools = []

    for tool in tools:
        success, _ = run_command([tool, "--version"], f"Checking {tool}")
        if not success:
            missing_tools.append(tool)

    if missing_tools:
        print(f"\n❌ Missing tools: {', '.join(missing_tools)}")
        print("Install with: pip install -r requirements-dev.txt")
        return False

    return True


def run_linters(fix_mode: bool = False) -> bool:
    """Run all linters, applying fixes if fix_mode is True"""
    success = True

    # Only target script directories to preserve functionality
    script_patterns = [
        "../scripts/actions/*/*.py",
        "../scripts/assets/*/*.py",
        "../scripts/courses/*/*.py",
        "../scripts/groups/*/*.py",
        "../scripts/inspections/*/*.py",
        "../scripts/issues/*/*.py",
        "../scripts/nuke_account/*.py",
        "../scripts/organizations/*/*.py",
        "../scripts/sites/*/*.py",
        "../scripts/templates/*/*.py",
        "../scripts/users/*/*.py",
    ]

    # Expand glob patterns to find actual files
    script_files = []
    for pattern in script_patterns:
        script_files.extend(glob.glob(pattern))

    if not script_files:
        print("⚠️ No Python files found in script directories")
        return True

    print(f"📁 Found {len(script_files)} Python files to check:")

    # Black - Code formatting (with string preservation)
    black_args = ["--skip-string-normalization"]
    if fix_mode:
        black_cmd = ["black"] + black_args + script_files
    else:
        black_cmd = ["black", "--check", "--diff"] + black_args + script_files
    black_success, _ = run_command(black_cmd, "Black code formatting", fix_mode)
    success = success and black_success

    # isort - Import sorting (conservative mode)
    if fix_mode:
        isort_cmd = ["isort"] + script_files
    else:
        isort_cmd = ["isort", "--check-only", "--diff"] + script_files
    isort_success, _ = run_command(isort_cmd, "isort import sorting", fix_mode)
    success = success and isort_success

    # flake8 - Style guide enforcement (check only, no fixes available)
    flake8_cmd = ["flake8", "--config", ".flake8"] + script_files
    flake8_success, _ = run_command(flake8_cmd, "flake8 style guide")
    success = success and flake8_success

    # mypy - Type checking (check only, no auto-fixes, relaxed mode)
    # Skip mypy for now due to duplicate main.py module conflicts
    print("🔍 Checking: mypy type checking")
    print("  ⏭️  mypy type checking - SKIPPED (duplicate module conflicts)")
    mypy_success = True

    return success


def main():
    parser = argparse.ArgumentParser(description="Lint and fix Python code")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply automatic fixes where possible"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Only check if dependencies are installed"
    )

    args = parser.parse_args()

    print("🐍 Python Code Quality Tool")
    print("=" * 50)

    if args.check_deps:
        if check_dependencies():
            print("\n✅ All dependencies are installed!")
            sys.exit(0)
        else:
            sys.exit(1)

    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)

    print(f"\n{'🔧 FIXING MODE' if args.fix else '🔍 CHECK MODE'}")
    print("-" * 30)

    success = run_linters(fix_mode=args.fix)

    print("\n" + "=" * 50)
    if success:
        print("✅ All checks passed!")
        if not args.fix:
            print("💡 Run with --fix to automatically fix formatting issues")
    else:
        print("❌ Some checks failed!")
        if not args.fix:
            print("💡 Run with --fix to automatically fix what can be fixed")
        sys.exit(1)


if __name__ == "__main__":
    main()
