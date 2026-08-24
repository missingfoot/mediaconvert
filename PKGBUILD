# Maintainer: James <claude@jamessparkes.com>
pkgname=mediaconvert
pkgver=1.0.0
pkgrel=1
pkgdesc="Drag-and-drop image/video/audio format conversion"
arch=('any')
license=('MIT')
depends=('pyside6' 'python' 'ffmpeg' 'imagemagick' 'libwebp')
source=()
sha256sums=()

# This package is fully local and non-distributed (source=() is intentionally
# empty), so we install straight from $startdir rather than $srcdir. Do not
# "fix" this to a source=() per-file array - makepkg flattens local file
# sources to their basename, which breaks these paths.
package() {
    install -Dm755 "$startdir/mediaconvert" "$pkgdir/usr/bin/mediaconvert"
    install -Dm644 "$startdir/src/mediaconvert.desktop" "$pkgdir/usr/share/applications/mediaconvert.desktop"
    install -Dm644 "$startdir/src/mediaconvert/__init__.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/__init__.py"
    install -Dm644 "$startdir/src/mediaconvert/__main__.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/__main__.py"
    install -Dm644 "$startdir/src/mediaconvert/categorize.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/categorize.py"
    install -Dm644 "$startdir/src/mediaconvert/converter.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/converter.py"
    install -Dm644 "$startdir/src/mediaconvert/image_convert.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/image_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/media_convert.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/media_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/naming.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/naming.py"
    install -Dm644 "$startdir/src/mediaconvert/ui.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/ui.py"
}
