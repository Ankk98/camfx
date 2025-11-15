#!/usr/bin/env python3
"""Comprehensive verification of Chromium PipeWire camera setup."""

import json
import subprocess
import sys
import os


def check_chromium_flag():
    """Check if Chromium flag is enabled via user data directory."""
    print("\n🔍 Checking Chromium WebRTCPipeWireCapturer flag...")
    
    # Try to find Chromium user data directory
    home = os.path.expanduser("~")
    possible_paths = [
        f"{home}/.var/app/org.chromium.Chromium/config/chromium/Default/Preferences",
        f"{home}/.config/chromium/Default/Preferences",
        f"{home}/.config/google-chrome/Default/Preferences",
    ]
    
    for prefs_path in possible_paths:
        if os.path.exists(prefs_path):
            try:
                with open(prefs_path, 'r') as f:
                    prefs = json.load(f)
                
                # Check if flag is enabled
                flags = prefs.get('browser', {}).get('enabled_labs_experiments', [])
                if 'WebRTCPipeWireCapturer' in flags:
                    print(f"   ✅ Flag found in: {prefs_path}")
                    print(f"   ✅ WebRTCPipeWireCapturer is enabled")
                    return True
                else:
                    print(f"   ⚠️  Preferences found at: {prefs_path}")
                    print(f"   ❌ WebRTCPipeWireCapturer flag NOT found in enabled experiments")
                    print(f"   📝 Current flags: {flags if flags else 'none'}")
                    return False
            except Exception as e:
                print(f"   ⚠️  Could not read preferences: {e}")
    
    print("   ⚠️  Could not find Chromium preferences file")
    print("   💡 This might mean:")
    print("      - Chromium hasn't been run yet")
    print("      - Flag needs to be set manually in chrome://flags")
    return None


def check_flatpak_permissions():
    """Check Flatpak permissions for Chromium."""
    print("\n🔍 Checking Flatpak permissions...")
    
    try:
        result = subprocess.run(
            ['flatpak', 'override', '--show', 'org.chromium.Chromium'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            output = result.stdout
            # Check for PipeWire permission (can be in different formats)
            # Format: "org.freedesktop.portal.PipeWire=talk" in Session Bus Policy section
            has_pipewire = (
                'org.freedesktop.portal.PipeWire=talk' in output or
                'org.freedesktop.portal.PipeWire' in output
            )
            has_session_bus = 'session-bus' in output or 'sockets=session-bus' in output
            
            if has_pipewire and has_session_bus:
                print("   ✅ PipeWire permissions granted")
                print("   ✅ Session bus access granted")
                return True
            else:
                print("   ❌ Missing permissions:")
                if not has_pipewire:
                    print("      - PipeWire portal access")
                if not has_session_bus:
                    print("      - Session bus access")
                print("\n   💡 Fix with: ./scripts/fix_chromium_permissions.sh")
                return False
        else:
            print("   ⚠️  Could not check Flatpak permissions")
            return None
    except FileNotFoundError:
        print("   ℹ️  Not a Flatpak installation")
        return None
    except Exception as e:
        print(f"   ⚠️  Error checking permissions: {e}")
        return None


def check_pipewire_services():
    """Check if PipeWire services are running."""
    print("\n🔍 Checking PipeWire services...")
    
    services = ['pipewire', 'wireplumber', 'xdg-desktop-portal']
    all_running = True
    
    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'is-active', service],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                print(f"   ✅ {service} is running")
            else:
                print(f"   ❌ {service} is NOT running")
                print(f"      Start with: systemctl --user start {service}")
                all_running = False
        except Exception as e:
            print(f"   ⚠️  Could not check {service}: {e}")
            all_running = False
    
    return all_running


def check_camfx_node():
    """Check if camfx node exists in PipeWire."""
    print("\n🔍 Checking camfx PipeWire node...")
    
    try:
        result = subprocess.run(
            ['pw-dump'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print(f"   ❌ pw-dump failed: {result.stderr}")
            return False
        
        data = json.loads(result.stdout)
        nodes = [obj for obj in data if obj.get('type') == 'PipeWire:Interface:Node']
        camfx_nodes = [
            n for n in nodes
            if n.get('info', {}).get('props', {}).get('media.name') == 'camfx'
        ]
        
        if camfx_nodes:
            node = camfx_nodes[0]
            props = node.get('info', {}).get('props', {})
            state = node.get('info', {}).get('state', 'unknown')
            
            print(f"   ✅ camfx node found (ID: {node.get('id')})")
            print(f"   ✅ media.class: {props.get('media.class')}")
            print(f"   ✅ media.name: {props.get('media.name')}")
            print(f"   ✅ node.description: {props.get('node.description')}")
            print(f"   ℹ️  State: {state} (normal when no client connected)")
            return True
        else:
            print("   ❌ camfx node NOT found in PipeWire")
            print("   💡 Make sure camfx is running: camfx blur --name 'camfx'")
            return False
            
    except Exception as e:
        print(f"   ❌ Error checking PipeWire: {e}")
        return False


def main():
    print("=" * 60)
    print("Chromium PipeWire Camera Setup Verification")
    print("=" * 60)
    
    results = {
        'services': check_pipewire_services(),
        'permissions': check_flatpak_permissions(),
        'camfx_node': check_camfx_node(),
        'chromium_flag': check_chromium_flag(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_good = True
    for check, result in results.items():
        if result is False:
            all_good = False
            print(f"❌ {check}: FAILED")
        elif result is True:
            print(f"✅ {check}: OK")
        else:
            print(f"⚠️  {check}: UNKNOWN")
    
    print("\n" + "=" * 60)
    
    if all_good and all(r is not False for r in results.values()):
        print("✅ All checks passed!")
        print("\nIf Chromium still can't see the camera:")
        print("  1. Make sure Chromium flag is enabled: chrome://flags/#enable-webrtc-pipewire-capturer")
        print("  2. Restart Chromium COMPLETELY (close all windows)")
        print("  3. Check: chrome://settings/content/camera")
    else:
        print("⚠️  Some checks failed. Fix the issues above and try again.")
        print("\nQuick fixes:")
        if results.get('permissions') is False:
            print("  - Run: ./scripts/fix_chromium_permissions.sh")
        if results.get('camfx_node') is False:
            print("  - Start camfx: camfx blur --name 'camfx'")
        if results.get('chromium_flag') is False:
            print("  - Enable flag: chrome://flags/#enable-webrtc-pipewire-capturer")
    
    print("=" * 60)


if __name__ == '__main__':
    main()

