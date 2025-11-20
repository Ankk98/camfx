#!/usr/bin/env python3
"""
Script to download source code of PipeWire-related dependencies for review.
"""

import os
import subprocess
import sys
from pathlib import Path

# Configuration
TARGET_DIR = Path(__file__).parent.parent / "dependency_sources"
REPOS = [
    {
        "name": "pipewire",
        "url": "https://gitlab.freedesktop.org/pipewire/pipewire.git",
        "desc": "PipeWire multimedia server (Core C code)"
    },
    {
        "name": "wireplumber",
        "url": "https://gitlab.freedesktop.org/pipewire/wireplumber.git",
        "desc": "PipeWire session manager"
    },
    {
        "name": "gstreamer",
        "url": "https://gitlab.freedesktop.org/gstreamer/gstreamer.git",
        "desc": "GStreamer multimedia framework (Monorepo, includes plugins)"
    },
    {
        "name": "pygobject",
        "url": "https://gitlab.gnome.org/GNOME/pygobject.git",
        "desc": "Python bindings for GObject/GStreamer"
    },
    {
        "name": "dbus-python",
        "url": "https://gitlab.freedesktop.org/dbus/dbus-python.git",
        "desc": "Python bindings for D-Bus"
    }
]

def main():
    """Main entry point."""
    print(f"Creating target directory: {TARGET_DIR}")
    TARGET_DIR.mkdir(exist_ok=True)
    
    # Create a README in the target directory
    readme_path = TARGET_DIR / "README.md"
    if not readme_path.exists():
        with open(readme_path, "w") as f:
            f.write("# Dependency Source Codes\n\n")
            f.write("This directory contains source code clones of dependencies for review purposes.\n")
            f.write("These are ignored by git.\n\n")
            f.write("## Repositories\n")
            for repo in REPOS:
                f.write(f"- **{repo['name']}**: {repo['desc']} ({repo['url']})\n")
    
    print(f"Processing {len(REPOS)} repositories...")
    
    for repo in REPOS:
        name = repo["name"]
        url = repo["url"]
        repo_dir = TARGET_DIR / name
        
        print(f"\n--- {name} ---")
        if repo_dir.exists():
            print(f"Directory {repo_dir} already exists.")
            if (repo_dir / ".git").exists():
                print("Git repository detected. Updating...")
                try:
                    subprocess.run(
                        ["git", "pull"], 
                        cwd=repo_dir, 
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    print("Successfully updated.")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to update: {e.stderr}")
            else:
                print("Directory exists but is not a git repository. Skipping.")
        else:
            print(f"Cloning {url}...")
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(repo_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print("Successfully cloned.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone: {e.stderr}")

    print("\nDone. Source codes are available in:", TARGET_DIR)

if __name__ == "__main__":
    main()
