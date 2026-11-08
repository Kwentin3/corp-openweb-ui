#!/bin/sh
# Native AWG lifecycle only. UDP daemon stays in root; TUN and proxy use netns.
set -eu
NS=awg-egress
IFACE=awge0
HOST_LINK=awge-host
PEER_LINK=awge-peer
MARKER=/run/corp-awg-egress.owned

case "${1:-}" in
  prepare)
    test ! -e "/run/netns/$NS"
    if ip link show "$HOST_LINK" >/dev/null 2>&1; then exit 1; fi
    if ip link show "$IFACE" >/dev/null 2>&1; then exit 1; fi
    : > "$MARKER"
    ip netns add "$NS"
    ip link add "$HOST_LINK" type veth peer name "$PEER_LINK"
    ip link set "$PEER_LINK" netns "$NS"
    ip address add 10.203.0.1/30 dev "$HOST_LINK"
    ip link set "$HOST_LINK" up
    ip -n "$NS" address add 10.203.0.2/30 dev "$PEER_LINK"
    ip -n "$NS" link set "$PEER_LINK" up
    ip -n "$NS" link set lo up
    ;;
  configure)
    : "${AWG_MTU:?Missing native MTU}" "${AWG_ADDRESSES:?Missing profile addresses}"
    count=0
    until awg show "$IFACE" listen-port >/dev/null 2>&1; do
      count=$((count + 1))
      test "$count" -le 100 || exit 1
      sleep 0.05
    done
    awg setconf "$IFACE" /etc/amnezia/egress/interface.conf
    ip link set "$IFACE" mtu "$AWG_MTU"
    # Let the daemon read the new MTU in the root namespace before the move.
    sleep 1
    ip link set "$IFACE" netns "$NS"
    for address in $AWG_ADDRESSES; do
      ip -n "$NS" address add "$address" dev "$IFACE"
    done
    ip -n "$NS" link set "$IFACE" up
    ip -n "$NS" route add default dev "$IFACE"
    ip -n "$NS" -6 route add unreachable default
    ;;
  cleanup)
    test -e "$MARKER" || exit 0
    if test -e "/run/netns/$NS"; then
      count=0
      while test -n "$(ip netns pids "$NS")"; do
        count=$((count + 1))
        test "$count" -le 30 || exit 1
        sleep 0.1
      done
    fi
    if ip link show "$HOST_LINK" >/dev/null 2>&1; then ip link delete "$HOST_LINK"; fi
    if test -e "/run/netns/$NS"; then ip netns delete "$NS"; fi
    rm -f "$MARKER"
    ;;
  *) echo 'Usage: awg-egress-netns.sh prepare|configure|cleanup' >&2; exit 2 ;;
esac
