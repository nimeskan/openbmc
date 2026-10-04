#!/usr/bin/env bash
# =============================================================================
#  watch-sensors.sh — watch the BMC's sensors over Redfish, from your PC
#
#  Logs in to the BMC's Redfish API, then every few seconds prints a table of
#  every sensor of one chassis: reading, units, health and state. Press
#  Ctrl+C to stop; the script logs out again.
#
#  Needs: bash, curl, jq   (Ubuntu: sudo apt-get install curl jq)
#
#  Usage:
#    ./watch-sensors.sh <bmc-ip> [chassis-id] [seconds]
#  Examples:
#    ./watch-sensors.sh 192.168.1.50
#    ./watch-sensors.sh 192.168.1.50 BeagleBone_BMC 5
#
#  User and password come from BMC_USER / BMC_PASS (default root / 0penBmc):
#    BMC_PASS='my-new-password' ./watch-sensors.sh 192.168.1.50
# =============================================================================
set -euo pipefail

BMC="${1:?Usage: $0 <bmc-ip> [chassis-id] [seconds]}"
CHASSIS="${2:-BeagleBone_BMC}"
INTERVAL="${3:-3}"
USER_NAME="${BMC_USER:-root}"
PASSWORD="${BMC_PASS:-0penBmc}"
BASE="https://$BMC"

for tool in curl jq; do
    command -v "$tool" >/dev/null || { echo "Please install $tool first." >&2; exit 1; }
done

# -k: accept the BMC's self-signed HTTPS certificate.
# -s: no progress meter. -S: but do show errors. -f: fail on HTTP errors.
CURL=(curl -k -s -S -f --max-time 10)

# --- Log in ------------------------------------------------------------------
# POST to the SessionService creates a session. The response has an
# X-Auth-Token header (the "key" for later requests) and a Location header
# (the session's own URL, which we DELETE to log out).
echo "Logging in to $BASE as $USER_NAME..."
HEADERS=$(mktemp)
trap 'rm -f "$HEADERS"' EXIT
"${CURL[@]}" -D "$HEADERS" -o /dev/null \
    -H "Content-Type: application/json" \
    -X POST "$BASE/redfish/v1/SessionService/Sessions" \
    -d "{\"UserName\": \"$USER_NAME\", \"Password\": \"$PASSWORD\"}" ||
    { echo "Login failed. Check the IP address, user and password." >&2; exit 1; }

TOKEN=$(awk 'tolower($1) == "x-auth-token:" {print $2}' "$HEADERS" | tr -d '\r')
SESSION=$(awk 'tolower($1) == "location:" {print $2}' "$HEADERS" | tr -d '\r')
[ -n "$TOKEN" ] || { echo "No X-Auth-Token in the login response." >&2; exit 1; }

get() { "${CURL[@]}" -H "X-Auth-Token: $TOKEN" "$BASE$1"; }

logout() {
    echo
    echo "Logging out."
    "${CURL[@]}" -H "X-Auth-Token: $TOKEN" -X DELETE "$BASE$SESSION" -o /dev/null || true
    rm -f "$HEADERS"
}
trap logout EXIT

# --- Find the sensors ------------------------------------------------------------
# /redfish/v1/Chassis/<id>/Sensors is a "collection": a list of links
# ("@odata.id") to each sensor resource.
if ! SENSOR_LIST=$(get "/redfish/v1/Chassis/$CHASSIS/Sensors"); then
    echo "Chassis '$CHASSIS' not found. Chassis on this BMC:" >&2
    get "/redfish/v1/Chassis" | jq -r '.Members[]."@odata.id"' >&2
    exit 1
fi

# --- Loop: read each sensor and print a table ----------------------------------------
while true; do
    clear 2>/dev/null || true
    printf 'Sensors of chassis %s on %s   (%s, every %ss, Ctrl+C to stop)\n\n' \
        "$CHASSIS" "$BMC" "$(date +%H:%M:%S)" "$INTERVAL"
    printf '%-34s %12s  %-10s %-9s %s\n' "SENSOR" "READING" "UNITS" "HEALTH" "STATE"
    printf '%-34s %12s  %-10s %-9s %s\n' "------" "-------" "-----" "------" "-----"

    # Re-read the collection each time, so new sensors show up too.
    SENSOR_LIST=$(get "/redfish/v1/Chassis/$CHASSIS/Sensors") || true
    for uri in $(echo "$SENSOR_LIST" | jq -r '.Members[]."@odata.id"'); do
        get "$uri" | jq -r '[
            .Name,
            (if .Reading == null then "n/a" else (.Reading | tostring) end),
            (.ReadingUnits // ""),
            (.Status.Health // ""),
            (.Status.State // "")
          ] | @tsv' |
        while IFS=$'\t' read -r name reading units health state; do
            printf '%-34s %12s  %-10s %-9s %s\n' "$name" "$reading" "$units" "$health" "$state"
        done
    done
    sleep "$INTERVAL"
done
