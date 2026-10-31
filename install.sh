#!/bin/bash
# Chiron installer. Paste in Terminal:
#   curl -fsSL https://raw.githubusercontent.com/ris3abh/Chiron/main/install.sh | bash
# Downloads the source to ~/.chiron (paste the line again to update), builds the app, opens it.
set -e
DIR="${CHIRON_SOURCE:-$HOME/.chiron}"   # not CHIRON_DIR: that one is the data folder
echo "Installing Chiron…"
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 26 ] || { echo "Chiron needs macOS 26 or later."; exit 1; }
if ! xcode-select -p >/dev/null 2>&1; then
  echo "First, Apple's command line tools. A macOS window will open: click Install."
  echo "When it finishes, paste the install line again."
  xcode-select --install 2>/dev/null || true
  exit 1
fi
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull -q --ff-only || { echo "Could not update $DIR. Delete that folder, then paste the install line again."; exit 1; }
else
  git clone -q --depth 1 https://github.com/ris3abh/Chiron.git "$DIR"
fi
"$DIR/build.sh"
open "$HOME/Applications/Chiron.app"
echo "Done. The Chiron setup window walks you through the rest."
