#!/usr/bin/env python3
"""
Configure Things MCP token interactively.
This script helps users set up their Things authentication token.
"""
import sys
import os
import subprocess
import logging
from pathlib import Path

# Add parent directory to path to import things_mcp
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from src.things_mcp.config import set_things_auth_token, get_things_auth_token
except ImportError:
    print("ERROR: Unable to import things_mcp package. Make sure you're running this from the things-mcp directory.")
    sys.exit(1)

def get_token_from_things():
    """Attempt to get the token from Things app via AppleScript."""
    try:
        # AppleScript to get token from Things app preferences
        script = '''
        tell application "System Events"
            tell process "Things3"
                click menu item "Preferences…" of menu "Things" of menu bar 1
                delay 0.5
                click button "General" of toolbar 1 of window "Preferences"
                delay 0.5
                
                # Check if the URL setting is enabled
                set urlEnabled to get value of checkbox "Enable Things URLs" of window "Preferences"
                
                if not urlEnabled then
                    # Enable URL scheme if it's not already enabled
                    click checkbox "Enable Things URLs" of window "Preferences"
                    delay 0.5
                end if
                
                # Get the token value if available
                set tokenValue to ""
                try
                    set tokenField to text field "Token:" of window "Preferences"
                    set tokenValue to value of tokenField
                end try
                
                # Close preferences
                click button 1 of window "Preferences"
                
                return tokenValue
            end tell
        end tell
        '''
        
        result = subprocess.run(['osascript', '-e', script], 
                            capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ERROR running AppleScript: {result.stderr}")
            return None
        
        token = result.stdout.strip()
        if token:
            return token
            
        return None
    except Exception as e:
        print(f"ERROR getting token from Things app: {str(e)}")
        return None

def main():
    """Main function to configure Things token."""
    print("\n===== Things MCP Configuration =====\n")
    
    current_token = get_things_auth_token()
    if current_token:
        print(f"Current Things authentication token: {current_token}")
        change = input("\nDo you want to change this token? (y/n): ").lower()
        if change != 'y':
            print("\nKeeping existing token. Configuration complete!")
            return
    
    print("\nLooking for token in Things app...")
    auto_token = get_token_from_things()
    
    if auto_token:
        print(f"Found token in Things app: {auto_token}")
        use_auto = input("Use this token? (y/n): ").lower()
        if use_auto == 'y':
            set_things_auth_token(auto_token)
            print("\nToken saved successfully!")
            return
    else:
        print("Could not automatically find token in Things app.")
    
    print("\nTo find your Things authentication token:")
    print("1. Open Things app")
    print("2. Go to Things → Preferences")
    print("3. Select the 'General' tab")
    print("4. Check 'Enable Things URLs'")
    print("5. Copy the token value shown")
    
    manual_token = input("\nEnter your Things authentication token: ").strip()
    
    if not manual_token:
        print("\nNo token provided. Configuration cancelled.")
        return
    
    set_things_auth_token(manual_token)
    print("\nToken saved successfully!")

if __name__ == "__main__":
    main()
