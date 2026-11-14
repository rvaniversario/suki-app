#!/bin/sh
# Container entrypoint: the scraper loop in the background, nginx in the foreground.
set -eu

mkdir -p "${SUKI_DATA_DIR:-/data}"
sed "s/__PORT__/${PORT:-80}/" /etc/nginx/conf.d/suki.conf.template > /etc/nginx/conf.d/suki.conf

scraper.sh &

exec nginx -g 'daemon off;'
