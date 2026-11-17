#!/usr/bin/env bash
# Собирает RPM-пакет spoticube из текущего рабочего дерева.
#
#   ./packaging/build-rpm.sh
#
# Сборка идёт в отдельной папке (/tmp/opencode/rpmbuild), системные каталоги
# не затрагиваются. Готовый пакет печатается последней строкой.

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
NAME=spoticube
VERSION=$(awk '/^Version:/ {print $2; exit}' "$ROOT/packaging/$NAME.spec")
TOPDIR=${RPM_TOPDIR:-/tmp/opencode/rpmbuild}

echo "==> сборка $NAME-$VERSION в $TOPDIR"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{SOURCES,SPECS,BUILD,BUILDROOT,RPMS,SRPMS}

# исходники: рабочее дерево, а не git HEAD — чтобы в пакет попало то, что видно
tar -czf "$TOPDIR/SOURCES/$NAME-$VERSION.tar.gz" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --transform "s,^,$NAME-$VERSION/," \
    -C "$ROOT" main.py spoticube assets packaging README.md LICENSE

rpmbuild -bb --define "_topdir $TOPDIR" "$ROOT/packaging/$NAME.spec"

echo "==> готово"
find "$TOPDIR/RPMS" -name '*.rpm' -printf '%p\n'
