#!/bin/bash
clear
echo "========================================="
echo "   Flow Studio Manager - macOS Enabler   "
echo "========================================="
echo ""
echo "Removing macOS Gatekeeper quarantine..."

APP_PATH="/Applications/Flow Studio Manager.app"
USER_APP_PATH="$HOME/Applications/Flow Studio Manager.app"

if [ -d "$APP_PATH" ]; then
    xattr -cr "$APP_PATH" 2>/dev/null
    echo "✓ Fixed: $APP_PATH"
    echo "Launching Flow Studio Manager..."
    open "$APP_PATH"
elif [ -d "$USER_APP_PATH" ]; then
    xattr -cr "$USER_APP_PATH" 2>/dev/null
    echo "✓ Fixed: $USER_APP_PATH"
    echo "Launching Flow Studio Manager..."
    open "$USER_APP_PATH"
else
    echo "App not found in /Applications. Searching current directory..."
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    LOCAL_APP="$DIR/Flow Studio Manager.app"
    if [ -d "$LOCAL_APP" ]; then
        xattr -cr "$LOCAL_APP" 2>/dev/null
        echo "✓ Fixed: $LOCAL_APP"
        echo "Launching..."
        open "$LOCAL_APP"
    else
        echo "Please drag Flow Studio Manager into Applications folder first, then run this file."
    fi
fi

echo ""
echo "Done! You can close this window."
