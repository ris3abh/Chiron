#!/bin/bash
# Installs Chiron: builds Chiron.app, starts it at login, and (re)starts it now. Run it again after any change.
# ./build.sh --package <dir>: CI's dev DMG. Same build, written to <dir>/Chiron.app and signed ad hoc; nothing on this Mac
# (keychain, LaunchServices, LaunchAgents, ~/.config) is touched and nothing is started.
set -e
PACKAGE=""
if [ "$1" = "--package" ]; then
  [ -n "$2" ] || { echo "Use: ./build.sh --package <dir>"; exit 1; }
  mkdir -p "$2"; PACKAGE=$(cd "$2" && pwd)
fi
cd "$(dirname "$0")"
VERSION=$(tr -d '\n' < VERSION)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid VERSION: $VERSION"; exit 1; }
IFS=. read -r VERSION_MAJOR VERSION_MINOR VERSION_PATCH <<< "$VERSION"
(( VERSION_MINOR < 1000 && VERSION_PATCH < 1000 )) || { echo "VERSION components must be below 1000"; exit 1; }
BUILD=$((VERSION_MAJOR * 1000000 + VERSION_MINOR * 1000 + VERSION_PATCH))
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo unknown)
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 26 ] || { echo "Chiron needs macOS 26 or later (it uses Apple's new on-device speech)."; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo "Needs Apple's command line tools. Run: xcode-select --install   then run ./build.sh again."; exit 1; }
command -v python3 >/dev/null || { echo "Chiron needs Python 3. Install it, then run ./build.sh again."; exit 1; }
[ -n "$PACKAGE" ] || command -v claude >/dev/null || [ -x ~/.local/bin/claude ] || echo "Note: Claude Code is not installed yet. Chiron's setup window can install it, or you can use a custom server."
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
# A compiler error must leave the installed app and its resources alone.
# With several files only main.swift may hold top-level code, so the core goes in as main.swift; the module stays Chiron
# so `Chiron.settings` still names the global.
cp Chiron.swift "$STAGE/main.swift"
swiftc -O -target "$(uname -m)-apple-macos26.0" -module-name Chiron "$STAGE/main.swift" app/*.swift -o "$STAGE/Chiron"
APP=~/Applications/Chiron.app   # in Applications so System Settings can list it for permissions
[ -n "$PACKAGE" ] && APP="$STAGE/Chiron.app"   # assembled in the stage and moved whole, so a failure leaves nothing half-written in <dir>
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/ui"
cp chiron.py "$APP/Contents/Resources/"
rm -rf "$APP/Contents/Resources/chiron"; mkdir -p "$APP/Contents/Resources/chiron"
cp chiron/*.py "$APP/Contents/Resources/chiron/"   # the package, without __pycache__
for f in chiron/*.json; do [ -e "$f" ] && cp "$f" "$APP/Contents/Resources/chiron/"; done
cp ui/*.html ui/*.js "$APP/Contents/Resources/ui/"
for d in strings fonts; do
  if [ -d "ui/$d" ]; then rm -rf "$APP/Contents/Resources/ui/$d"; cp -R "ui/$d" "$APP/Contents/Resources/ui/$d"; fi
done
cp ui/AppIcon.icns "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.chiron.app</string>
<key>CFBundleName</key><string>Chiron</string>
<key>CFBundleExecutable</key><string>Chiron</string>
<key>CFBundleVersion</key><string>$BUILD</string>
<key>CFBundleShortVersionString</key><string>$VERSION</string>
<key>ChironCommit</key><string>$COMMIT</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>ChironSource</key><string>$(pwd)</string>
<key>LSUIElement</key><true/>
<key>NSMicrophoneUsageDescription</key><string>Chiron listens when you use its shortcut or microphone button.</string>
<key>NSAppleEventsUsageDescription</key><string>Chiron controls apps like Finder, Chrome and Music when you ask it to.</string>
<key>NSCalendarsFullAccessUsageDescription</key><string>Chiron reads your calendar, adds events you request, and asks before moving or deleting existing events. Calendar details are sent to your chosen AI model.</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Chiron turns your words into text on this Mac.</string>
</dict></plist>
P
mv "$STAGE/Chiron" "$APP/Contents/MacOS/Chiron"
if [ -n "$PACKAGE" ]; then
  codesign -s - --force --deep "$APP"
  rm -rf "$PACKAGE/Chiron.app"; mv "$APP" "$PACKAGE/Chiron.app"
  echo "Packaged $PACKAGE/Chiron.app"
  exit 0
fi
# With a code-signing identity named "Chiron Local Signing" in the keychain, macOS keeps permissions across
# rebuilds; ad hoc signing would ask for every permission again after each one. So make it once.
ID=$(security find-identity -p codesigning | awk '/Chiron Local Signing/{print $2; exit}')
if [ -z "$ID" ]; then
  K=$(mktemp -d)
  /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -subj "/CN=Chiron Local Signing" -addext "extendedKeyUsage=critical,codeSigning" \
    -addext "keyUsage=critical,digitalSignature" -keyout "$K/k.pem" -out "$K/c.pem" 2>/dev/null &&
  /usr/bin/openssl pkcs12 -export -inkey "$K/k.pem" -in "$K/c.pem" -out "$K/a.p12" -passout pass:chiron 2>/dev/null &&
  security import "$K/a.p12" -P chiron -T /usr/bin/codesign >/dev/null 2>&1 || true   # fails quietly: ad hoc still works
  rm -rf "$K"
  ID=$(security find-identity -p codesigning | awk '/Chiron Local Signing/{print $2; exit}')
fi
codesign -s "${ID:--}" --force "$APP"
# register with macOS, or System Settings can't list it for permissions
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
AGENT=~/Library/LaunchAgents/com.chiron.app.plist   # starts at login, restarts if it crashes (Quit stays quit)
mkdir -p ~/Library/LaunchAgents ~/.config/chiron
cat > "$AGENT" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.chiron.app</string>
<key>ProgramArguments</key><array><string>$APP/Contents/MacOS/Chiron</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>StandardErrorPath</key><string>$HOME/.config/chiron/app.err</string>
</dict></plist>
P
[ -n "$CHIRON_NO_RESTART" ] && exit 0   # build only; the running copy keeps going
# Reload the job so launchd refreshes its executable signing requirement after a rebuild.
launchctl bootout gui/$(id -u)/com.chiron.app 2>/dev/null || true
pkill -f "$APP/Contents/MacOS/Chiron$" 2>/dev/null && sleep 1   # stop a copy opened by hand too
# bootout can return before the job has finished unloading.
launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || { sleep 1; launchctl bootstrap gui/$(id -u) "$AGENT" 2>/dev/null || {
  echo "Could not add Chiron to Login Items; opening it directly instead."
  open "$APP"
}; }
echo "Chiron is running. Hold fn and talk."
