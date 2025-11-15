#!/usr/bin/env python3
"""Check if Chromium can detect the camfx virtual camera."""

import json
import subprocess
import sys


def check_pipewire_source(name="camfx"):
    """Check if the PipeWire source exists."""
    try:
        result = subprocess.run(
            ['pw-dump'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"❌ pw-dump failed: {result.stderr}")
            return False
        
        data = json.loads(result.stdout)
        nodes = [obj for obj in data if obj.get('type') == 'PipeWire:Interface:Node']
        video_sources = [
            n for n in nodes 
            if n.get('info', {}).get('props', {}).get('media.class') == 'Video/Source'
        ]
        
        camfx_sources = [
            n for n in video_sources
            if n.get('info', {}).get('props', {}).get('media.name') == name
        ]
        
        if not camfx_sources:
            print(f"❌ Virtual camera '{name}' not found in PipeWire")
            if video_sources:
                print(f"   Found {len(video_sources)} other Video/Source nodes:")
                for n in video_sources:
                    props = n.get('info', {}).get('props', {})
                    print(f"     - {props.get('media.name', 'unnamed')} (id: {n.get('id')})")
            return False
        
        source = camfx_sources[0]
        props = source.get('info', {}).get('props', {})
        state = source.get('info', {}).get('state', 'unknown')
        
        print(f"✅ Virtual camera '{name}' found in PipeWire")
        print(f"   Node ID: {source.get('id')}")
        print(f"   State: {state}")
        print(f"   Description: {props.get('node.description', 'not set')}")
        print(f"   Media name: {props.get('media.name', 'not set')}")
        
        if state == 'suspended':
            print("   ⚠️  Node is suspended (normal when no client connected)")
        
        return True
        
    except FileNotFoundError:
        print("❌ pw-dump not found. Install PipeWire tools:")
        print("   sudo dnf install pipewire-utils")
        return False
    except json.JSONDecodeError:
        print("❌ Failed to parse pw-dump output")
        return False
    except Exception as e:
        print(f"❌ Error checking PipeWire: {e}")
        return False


def check_chromium_flags():
    """Check Chromium installation and suggest flags."""
    chromium_paths = [
        'chromium',
        'chromium-browser',
        'google-chrome',
        'google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome-stable',
    ]
    
    # Check Flatpak
    try:
        result = subprocess.run(
            ['flatpak', 'list', '--app', '--columns=application'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            flatpak_apps = result.stdout.lower()
            if 'chromium' in flatpak_apps or 'chrome' in flatpak_apps:
                print("\n📦 Chromium/Chrome detected as Flatpak")
                print("   Flatpak apps may need additional permissions for PipeWire")
                print("   Check: flatpak info <app-id>")
    except:
        pass
    
    found = False
    for path in chromium_paths:
        try:
            result = subprocess.run(
                ['which', path],
                capture_output=True,
                timeout=1
            )
            if result.returncode == 0:
                print(f"\n✅ Found Chromium/Chrome: {path}")
                found = True
                break
        except:
            continue
    
    if not found:
        print("\n⚠️  Chromium/Chrome not found in standard locations")
        print("   If installed via Flatpak or custom location, check manually")
    
    print("\n🔧 To enable PipeWire support in Chromium:")
    print("   1. Open: chrome://flags/#enable-webrtc-pipewire-capturer")
    print("   2. Set to 'Enabled'")
    print("   3. Restart Chromium")
    print("\n   OR launch with flag:")
    print("   chromium --enable-features=WebRTCPipeWireCapturer")


def main():
    print("=" * 60)
    print("Chromium Camera Compatibility Check")
    print("=" * 60)
    
    source_name = sys.argv[1] if len(sys.argv) > 1 else "camfx"
    
    print(f"\nChecking for virtual camera: '{source_name}'")
    source_exists = check_pipewire_source(source_name)
    
    check_chromium_flags()
    
    print("\n" + "=" * 60)
    if source_exists:
        print("✅ Virtual camera is created in PipeWire")
        print("⚠️  If Chromium still can't see it:")
        print("   1. Ensure WebRTCPipeWireCapturer flag is enabled")
        print("   2. Check Chromium permissions: chrome://settings/content/camera")
        print("   3. Try restarting Chromium after enabling the flag")
    else:
        print("❌ Virtual camera not found")
        print("   Make sure camfx is running: camfx blur")
    
    print("=" * 60)


if __name__ == '__main__':
    main()

