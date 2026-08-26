# Maintainer: James <claude@jamessparkes.com>
pkgname=mediaconvert
pkgver=2.0.0
pkgrel=10
pkgdesc="Drag-and-drop image/video/audio format conversion"
arch=('any')
license=('custom')
depends=('pyside6' 'python' 'ffmpeg' 'imagemagick' 'libwebp' 'pngquant' 'oxipng' 'jpegoptim')
source=()
sha256sums=()

# This package is fully local and non-distributed (source=() is intentionally
# empty), so we install straight from $startdir rather than $srcdir. Do not
# "fix" this to a source=() per-file array - makepkg flattens local file
# sources to their basename, which breaks these paths.
package() {
    install -Dm644 "$startdir/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm755 "$startdir/mediaconvert" "$pkgdir/usr/bin/mediaconvert"
    install -Dm644 "$startdir/src/mediaconvert.desktop" "$pkgdir/usr/share/applications/mediaconvert.desktop"
    install -Dm644 "$startdir/src/mediaconvert.png" "$pkgdir/usr/share/icons/hicolor/512x512/apps/mediaconvert.png"
    install -Dm644 "$startdir/src/mediaconvert/__init__.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/__init__.py"
    install -Dm644 "$startdir/src/mediaconvert/__main__.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/__main__.py"
    install -Dm644 "$startdir/src/mediaconvert/categorize.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/categorize.py"
    install -Dm644 "$startdir/src/mediaconvert/control.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/control.py"
    install -Dm644 "$startdir/src/mediaconvert/converter.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/converter.py"
    install -Dm644 "$startdir/src/mediaconvert/icons.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/icons.py"
    install -Dm644 "$startdir/src/mediaconvert/image_convert.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/image_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/image_options_dialog.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/image_options_dialog.py"
    install -Dm644 "$startdir/src/mediaconvert/media_convert.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/media_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/naming.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/naming.py"
    install -Dm644 "$startdir/src/mediaconvert/settings_dialog.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/settings_dialog.py"
    install -Dm644 "$startdir/src/mediaconvert/ui.py" "$pkgdir/usr/share/mediaconvert/mediaconvert/ui.py"
}
