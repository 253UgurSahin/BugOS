#!/usr/bin/env bash
# The photo studio: make every app screenshot for the website again, in English, light and dark.
#
#   bash tools/screenshots/studio.sh [image] [live-image]
#
# Needs podman and a BugOS image (default: localhost/bugos:lokaal, built with tools/iso-local.sh,
# or ghcr.io/253ugursahin/bugos:latest). The apps run from THIS checkout (mounted over the image),
# so the photos show the code as it is now, even with an older image. No screen is needed.
# Output: website/assets/<name>-<light|dark>.webp (and live.webp). Needs Python with Pillow.
set -euo pipefail

IMAGE="${1:-localhost/bugos:lokaal}"
LIVE_IMAGE="${2:-localhost/bugos-live:lokaal}"
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT="$(cd "$HERE" && (pwd -W 2>/dev/null || pwd))"   # pwd -W: Windows path for podman on Git Bash
WORK="$(mktemp -d)"
WORK_HOST="$(cd "$WORK" && (pwd -W 2>/dev/null || pwd))"
trap 'rm -rf "$WORK"' EXIT
export MSYS_NO_PATHCONV=1

run() {  # image, then the command inside it
    local image="$1"; shift
    podman run --rm \
        -v "$ROOT:/repo:ro" \
        -v "$ROOT/system_files/usr/lib/bugos/python:/usr/lib/bugos/python:ro" \
        -v "$ROOT/system_files/usr/share/bugos:/usr/share/bugos:ro" \
        -v "$WORK_HOST:/out" \
        -e QT_QPA_PLATFORM=offscreen -e QT_SCALE_FACTOR=2 -e LANG=en_US.UTF-8 -e LC_ALL=en_US.UTF-8 \
        -e BUGOS_BRON=/repo/system_files -e BUGOS_APPICONEN=/out/icons \
        --entrypoint /usr/bin/bash "$image" -c "$*"
}

echo "== App icons for the Store (from Flathub, like BugOS itself shows them)"
run "$IMAGE" 'python3 - <<"EOF"
import json, pathlib, urllib.request
out = pathlib.Path("/out/icons"); out.mkdir(exist_ok=True)
apps = [a["id"] for a in json.load(open("/usr/share/bugos/store.json", encoding="utf-8"))["apps"]]
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bugos-studio"}), timeout=20).read()
for i in apps:
    try:
        icon = json.loads(get(f"https://flathub.org/api/v2/appstream/{i}")).get("icon") or ""
        if icon.startswith("https://dl.flathub.org/"):
            (out / f"{i}.png").write_bytes(get(icon))
    except Exception as e:
        print("no icon for", i, e)
print(len(list(out.glob("*.png"))), "icons")
EOF'

echo "== The apps"
run "$IMAGE" 'for s in welcome help help-crop settings power-crop store backup switch; do
    for th in licht donker; do
        name=$s-$([ $th = licht ] && echo light || echo dark)
        case $s in *-crop) name=${s%-crop}-$([ $th = licht ] && echo light || echo dark)-crop;; esac
        BUGOS_THEMA=$th timeout 90 python3 /repo/tools/screenshots/studio.py $s /out/$name.png 2>&1 | grep -E "^(ERROR|[a-z-]+: [0-9]+x)" || true
    done
done'

echo "== Files (the file manager), in a home folder with example files (see explorer.sh)"
for th in licht donker; do
    name=explorer-$([ $th = licht ] && echo light || echo dark)
    # explorer.sh starts "the program" as user bugie; here that program is the studio.
    # tr: a checkout on Windows can have CRLF line endings, which bash does not accept.
    run "$IMAGE" 'chmod 777 /out
        tr -d "\r" < /repo/tools/screenshots/explorer.sh | sed "s#^REPO=.*#REPO=/repo#" > /tmp/explorer.sh
        cat > /tmp/studio-files <<"EOF"
#!/usr/bin/bash
exec python3 /repo/tools/screenshots/studio.py files "$BUGOS_STUDIO_UIT" "$@"
EOF
        chmod 755 /tmp/studio-files
        BUGOS_LSBLK=/repo/tools/screenshots/no-drives.json BUGOS_THEMA='"$th"' BUGOS_STUDIO_UIT=/out/'"$name"'.png timeout 120 bash /tmp/explorer.sh '"$th"' Pictures /tmp/studio-files 2>&1 | grep -E "^(ERROR|files:|Traceback)" || true'
done

echo "== The live stick"
run "$LIVE_IMAGE" 'BUGOS_THEMA=donker timeout 90 python3 /repo/tools/screenshots/studio.py live /out/live.png 2>&1 | grep -E "^(ERROR|live:)" || true'

echo "== To webp"
PY="$(command -v python3 || command -v python)"
"$PY" - "$WORK_HOST" "$ROOT/website/assets" <<'EOF'
import sys
from pathlib import Path
from PIL import Image
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
n = 0
for png in sorted(src.glob("*.png")):
    Image.open(png).convert("RGB").save(dst / f"{png.stem}.webp", "WEBP", quality=88, method=6)
    n += 1
print(n, "photos in", dst)
EOF
