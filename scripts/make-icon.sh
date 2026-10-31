#!/bin/bash
# Renders docs/icon.svg into ui/AppIcon.icns and docs/icon.png. Needs Google Chrome (headless) for the SVG; run after editing the mark.
set -e
cd "$(dirname "$0")/.."
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
printf '<html><body style="margin:0;background:transparent">%s</body></html>' "$(cat docs/icon.svg)" > "$W/i.html"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000 --window-size=1024,1024 \
  --screenshot="$W/1024.png" "file://$W/i.html" 2>/dev/null
mkdir "$W/AppIcon.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$W/1024.png" --out "$W/AppIcon.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$W/1024.png" --out "$W/AppIcon.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$W/AppIcon.iconset" -o ui/AppIcon.icns
sips -z 512 512 "$W/1024.png" --out docs/icon.png >/dev/null
echo "Wrote ui/AppIcon.icns and docs/icon.png"
