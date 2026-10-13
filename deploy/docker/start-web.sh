#!/bin/sh
set -eu
fail() { printf '%s\n' 'WEB_CONFIG_UNAVAILABLE: explicit host and readable TLS files required' >&2; exit 78; }
host=${STUDY_SITE_HOST:-}
case "$host" in ''|*[!a-z0-9.-]*|.*|*.|-*|*-) fail ;; esac
printf '%s\n' "$host" | grep -Eq '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$' || fail
[ "${#host}" -le 253 ] || fail
[ -r /run/secrets/tls_certificate ] && [ -r /run/secrets/tls_private_key ] || fail
# The accepted DNS alphabet cannot inject sed expressions or nginx directives.
sed "s/@SITE_HOST@/$host/g" /opt/study/nginx.conf.template > /tmp/study-nginx.conf
exec nginx -c /tmp/study-nginx.conf -g 'daemon off;'
