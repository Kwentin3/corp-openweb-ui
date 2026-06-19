#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PACKAGE_VERSION="${STAGE2_FFMPEG_PACKAGE_VERSION:-0.12.6}"
CORE_VERSION="${STAGE2_FFMPEG_CORE_VERSION:-0.12.6}"
UTIL_VERSION="${STAGE2_FFMPEG_UTIL_VERSION:-0.12.1}"
TARGET_DIR="${STAGE2_FFMPEG_ASSET_TARGET:-$ROOT_DIR/deploy/openwebui-static/stage2-assets/ffmpeg/$CORE_VERSION}"
TMP_DIR="$(mktemp -d)"

cleanup() {
	rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

fetch_package() {
	package_name="$1"
	version="$2"
	tarball_name="$3"
	url="https://registry.npmjs.org/@ffmpeg/$package_name/-/$tarball_name-$version.tgz"
	archive="$TMP_DIR/$tarball_name-$version.tgz"
	mkdir -p "$TMP_DIR/$package_name"
	curl -fsSL "$url" -o "$archive"
	tar -xzf "$archive" -C "$TMP_DIR/$package_name"
}

mkdir -p "$TARGET_DIR"

fetch_package "ffmpeg" "$PACKAGE_VERSION" "ffmpeg"
cp "$TMP_DIR/ffmpeg/package/dist/umd/ffmpeg.js" "$TARGET_DIR/ffmpeg.js"
cp "$TMP_DIR/ffmpeg/package/dist/umd/814.ffmpeg.js" "$TARGET_DIR/814.ffmpeg.js"

fetch_package "util" "$UTIL_VERSION" "util"
cp "$TMP_DIR/util/package/dist/umd/index.js" "$TARGET_DIR/ffmpeg-util.js"

fetch_package "core" "$CORE_VERSION" "core"
cp "$TMP_DIR/core/package/dist/umd/ffmpeg-core.js" "$TARGET_DIR/ffmpeg-core.js"
cp "$TMP_DIR/core/package/dist/umd/ffmpeg-core.wasm" "$TARGET_DIR/ffmpeg-core.wasm"

cat > "$TARGET_DIR/manifest.json" <<EOF
{
  "ffmpeg_package_version": "$PACKAGE_VERSION",
  "ffmpeg_core_version": "$CORE_VERSION",
  "ffmpeg_util_version": "$UTIL_VERSION",
  "source": "npm:@ffmpeg",
  "layout": "umd"
}
EOF

echo "ffmpeg.wasm assets installed to $TARGET_DIR"
