#!/usr/bin/env python3
"""
Quick automated test to check if OBS solution will work.
No user interaction required.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

# Colors for terminal output
class Color:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def check(name):
    """Print test name"""
    print(f"\n{Color.BLUE}[Test]{Color.NC} {name}", flush=True)

def pass_test(msg):
    """Print success message"""
    print(f"  {Color.GREEN}✓{Color.NC} {msg}", flush=True)

def fail_test(msg):
    """Print failure message"""
    print(f"  {Color.RED}✗{Color.NC} {msg}", flush=True)

def warn_test(msg):
    """Print warning message"""
    print(f"  {Color.YELLOW}⚠{Color.NC} {msg}", flush=True)

def info_test(msg):
    """Print info message"""
    print(f"    {msg}", flush=True)

def run_command(cmd, timeout=5):
    """Run a command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def main():
    print(f"{Color.BLUE}{'='*60}{Color.NC}")
    print(f"{Color.BLUE}OBS Studio Solution - Readiness Check{Color.NC}")
    print(f"{Color.BLUE}{'='*60}{Color.NC}")
    
    results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # Test 1: OBS installed
    check("OBS Studio installation")
    if shutil.which('obs'):
        pass_test("OBS Studio is installed")
        results['passed'] += 1
        
        # Get version
        success, stdout, _ = run_command("obs --version 2>&1")
        if success and stdout:
            info_test(f"Version: {stdout.strip().split()[0]}")
    else:
        fail_test("OBS Studio NOT installed")
        info_test("Install: sudo dnf install obs-studio")
        results['failed'] += 1
    
    # Test 2: PipeWire running
    check("PipeWire service")
    success, _, _ = run_command("pgrep -x pipewire")
    if success:
        pass_test("PipeWire is running")
        results['passed'] += 1
    else:
        fail_test("PipeWire is NOT running")
        info_test("Start: systemctl --user start pipewire")
        results['failed'] += 1
    
    # Test 3: WirePlumber running
    check("WirePlumber service")
    success, _, _ = run_command("pgrep -x wireplumber")
    if success:
        pass_test("WirePlumber is running")
        results['passed'] += 1
    else:
        fail_test("WirePlumber is NOT running")
        info_test("Start: systemctl --user start wireplumber")
        results['failed'] += 1
    
    # Test 4: Python environment
    check("Python environment")
    venv_path = Path(__file__).parent / ".venv"
    if venv_path.exists():
        pass_test("Virtual environment found")
        results['passed'] += 1
    else:
        warn_test("No virtual environment (may be okay)")
        results['warnings'] += 1
    
    # Test 5: camfx command
    check("camfx installation")
    # Try in venv first
    if venv_path.exists():
        camfx_path = venv_path / "bin" / "camfx"
        if camfx_path.exists():
            pass_test("camfx installed in venv")
            results['passed'] += 1
        else:
            fail_test("camfx not in venv")
            info_test("Install: pip install -e .")
            results['failed'] += 1
    elif shutil.which('camfx'):
        pass_test("camfx installed system-wide")
        results['passed'] += 1
    else:
        fail_test("camfx not found")
        results['failed'] += 1
    
    # Test 6: GStreamer
    check("GStreamer")
    if shutil.which('gst-launch-1.0'):
        pass_test("GStreamer is installed")
        results['passed'] += 1
    else:
        fail_test("GStreamer not found")
        results['failed'] += 1
    
    # Test 7: Check for v4l2loopback conflicts
    check("v4l2loopback conflicts")
    success, _, _ = run_command("lsmod | grep v4l2loopback")
    if success:
        warn_test("v4l2loopback module is loaded (not needed for OBS)")
        info_test("Consider removing: sudo modprobe -r v4l2loopback")
        results['warnings'] += 1
    else:
        pass_test("No v4l2loopback conflicts")
        results['passed'] += 1
    
    # Test 8: Browser support
    check("Browser installations")
    browsers = []
    if shutil.which('chromium') or shutil.which('chromium-browser'):
        browsers.append("Chromium (native PipeWire)")
        pass_test("Chromium found - native PipeWire support")
        results['passed'] += 1
    if shutil.which('google-chrome'):
        browsers.append("Chrome (native PipeWire)")
        pass_test("Chrome found - native PipeWire support")
        results['passed'] += 1
    if shutil.which('firefox'):
        browsers.append("Firefox (needs OBS)")
        info_test("Firefox found - will need OBS bridge")
    
    if not browsers:
        warn_test("No browsers found")
        results['warnings'] += 1
    
    # Test 9: pw-cli availability
    check("PipeWire tools")
    if shutil.which('pw-cli'):
        pass_test("pw-cli available")
        results['passed'] += 1
        
        # Count nodes
        success, stdout, _ = run_command("pw-cli ls Node 2>/dev/null | grep -c 'id'")
        if success and stdout.strip().isdigit():
            count = int(stdout.strip())
            info_test(f"Found {count} PipeWire nodes")
    else:
        warn_test("pw-cli not found (optional)")
        results['warnings'] += 1
    
    # Summary
    print(f"\n{Color.BLUE}{'='*60}{Color.NC}")
    print(f"{Color.BLUE}Summary{Color.NC}")
    print(f"{Color.BLUE}{'='*60}{Color.NC}\n")
    
    print(f"{Color.GREEN}Passed:{Color.NC}   {results['passed']}")
    print(f"{Color.RED}Failed:{Color.NC}   {results['failed']}")
    print(f"{Color.YELLOW}Warnings:{Color.NC} {results['warnings']}\n")
    
    # Final verdict
    if results['failed'] == 0:
        print(f"{Color.GREEN}✓ OBS solution should work!{Color.NC}\n")
        print("Usage:")
        print("  1. Start camfx:")
        print("     $ camfx blur")
        print("")
        print("  2. Open OBS Studio:")
        print("     $ obs")
        print("")
        print("  3. In OBS:")
        print("     - Add Source → PipeWire Capture")
        print("     - Select 'camfx' camera")
        print("     - Click 'Start Virtual Camera'")
        print("")
        print("  4. In Firefox:")
        print("     - Select 'OBS Virtual Camera'")
        print("")
        print(f"{Color.BLUE}For full interactive test, run:{Color.NC}")
        print("  ./test_obs_solution.sh")
        print("")
        return 0
    else:
        print(f"{Color.RED}✗ Some requirements missing{Color.NC}\n")
        print("Fix the failed tests above before proceeding.")
        print("")
        if not shutil.which('obs'):
            print("Most important: Install OBS Studio")
            print("  sudo dnf install obs-studio obs-studio-plugins")
        print("")
        return 1

if __name__ == "__main__":
    sys.exit(main())

