#!/bin/sh
# Install Manbo into DESTDIR (used by both the RPM spec and `make deb`).
# Run from a source tree / tarball root. Usage: packaging/install.sh DESTDIR
set -eu
D="$1"
APP_ID=io.github.horiidonuts.Manbo

install -Dm755 bin/manbo "$D/usr/bin/manbo"
install -d "$D/usr/share/manbo/manbo" "$D/usr/share/manbo/data"
install -m644 manbo/*.py "$D/usr/share/manbo/manbo/"
cp -a data/sounds data/icons "$D/usr/share/manbo/data/"
install -Dm644 "data/$APP_ID.desktop" "$D/usr/share/applications/$APP_ID.desktop"
install -Dm644 "data/icons/hicolor/scalable/apps/$APP_ID.svg" \
    "$D/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
# D-Bus activation: the widget can start Manbo when it isn't running
install -Dm644 "data/$APP_ID.service" "$D/usr/share/dbus-1/services/$APP_ID.service"
# Plasma widget
install -d "$D/usr/share/plasma/plasmoids"
cp -a plasma/io.github.horiidonuts.manbo "$D/usr/share/plasma/plasmoids/"
# GNOME Shell extension (top bar timer); users turn it on in Extensions
install -d "$D/usr/share/gnome-shell/extensions"
cp -a gnome/manbo@horiidonuts.github.io "$D/usr/share/gnome-shell/extensions/"
