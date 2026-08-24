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

package() {
    site_packages="usr/lib/python3.$(python3 -c 'import sys; print(sys.version_info.minor)')/site-packages"
    install -Dm755 "$startdir/mediaconvert" "$pkgdir/usr/bin/mediaconvert"
    install -Dm644 "$startdir/src/mediaconvert.desktop" "$pkgdir/usr/share/applications/mediaconvert.desktop"
    install -Dm644 "$startdir/src/mediaconvert/__init__.py" "$pkgdir/$site_packages/mediaconvert/__init__.py"
    install -Dm644 "$startdir/src/mediaconvert/__main__.py" "$pkgdir/$site_packages/mediaconvert/__main__.py"
    install -Dm644 "$startdir/src/mediaconvert/categorize.py" "$pkgdir/$site_packages/mediaconvert/categorize.py"
    install -Dm644 "$startdir/src/mediaconvert/converter.py" "$pkgdir/$site_packages/mediaconvert/converter.py"
    install -Dm644 "$startdir/src/mediaconvert/image_convert.py" "$pkgdir/$site_packages/mediaconvert/image_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/media_convert.py" "$pkgdir/$site_packages/mediaconvert/media_convert.py"
    install -Dm644 "$startdir/src/mediaconvert/naming.py" "$pkgdir/$site_packages/mediaconvert/naming.py"
    install -Dm644 "$startdir/src/mediaconvert/ui.py" "$pkgdir/$site_packages/mediaconvert/ui.py"
}
