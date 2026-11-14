#!/bin/zsh
set -eu
base="$PWD/logos/codex-metal-16931-build"
workspace="${base:h:h}"
profile="${1:?pass offline, photos or jev}"
shift
export PATH="$workspace/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin"
export CODEX_HOME="$base/home" HOME="$base/home" TMPDIR="$base/tmp"
export BLENDER_USER_RESOURCES="$base/blender" XDG_CACHE_HOME="$base/cache"
export LOGO_MAKER_CACHE="$base/cache" CYCLES_METAL_DISABLE_BINARY_ARCHIVES=1 PYTHONDONTWRITEBYTECODE=1
extra=()
case "$profile" in
offline)
    unset OPENROUTER_API_KEY TYPESAFE_API_KEY
    extra=(-c 'permissions.metal-trial.network.enabled=false' --allow-metal)
    ;;
photos|jev)
    if [[ "$profile" == photos ]]; then
        unset OPENROUTER_API_KEY TYPESAFE_API_KEY
        domains='{"commons.wikimedia.org"="allow","upload.wikimedia.org"="allow","thumb.wikimedia.org"="allow","en.wikipedia.org"="allow","openverse.org"="allow","api.openverse.org"="allow","images.pexels.com"="allow","live.staticflickr.com"="allow","i.etsystatic.com"="allow","images.metmuseum.org"="allow","collectionapi.metmuseum.org"="allow","www.bonsaiempire.com"="allow","goods.bonsaimirai.com"="allow","cdn.shopify.com"="allow","dockedge.com"="allow","dockbuilders.com"="allow","www.perko.com"="allow","envirofloat.com"="allow"}'
    else
        unset TYPESAFE_API_KEY
        domains='{"openrouter.ai"="allow"}'
    fi
    extra=(-c 'features.network_proxy=true' -c 'permissions.metal-trial.network.enabled=true'
        -c 'permissions.metal-trial.network.mode="full"' -c 'permissions.metal-trial.network.enable_socks5=false'
        -c "permissions.metal-trial.network.domains=$domains")
    ;;
*) print -u2 "unknown workspace profile: $profile"; exit 2 ;;
esac
exec "$workspace/.venv/bin/python" "$base/exec-environment.py" "$profile" "$base/target/debug/codex" sandbox -P metal-trial -C "$workspace" \
    -c 'permissions.metal-trial.filesystem={":root"="read",":workspace_roots"="write"}' \
    "${extra[@]}" -- "$@"
