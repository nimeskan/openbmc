#!/bin/bash
# =============================================================================
#  sim3-poll.sh — read the SIM3 I2C sensor and publish its readings on D-Bus
#
#  Runs on the BMC (the BeagleBone), started by sim3-poll.service.
#
#  The SIM3 is the example 3-register chip from the guide
#  (beaglebone/redfish-i2c-sensor/README.md):
#
#    register 0x00  TEMP    signed 8-bit, 1 °C per step     (0x19 = 25 °C)
#    register 0x01  VOLT    unsigned 8-bit, 20 mV per step  (0xA5 = 3.300 V)
#    register 0x02  STATUS  bit 0 = data ready, bit 1 = alert, bit 7 = fault
#
#  How it fits together:
#    entity-manager reads beaglebone-sim3.json and tells dbus-sensors'
#    "externalsensor" program to create two empty sensors on D-Bus:
#      /xyz/openbmc_project/sensors/temperature/SIM3_Temperature
#      /xyz/openbmc_project/sensors/voltage/SIM3_Voltage
#    This script fills them in: every few seconds it reads the chip with
#    i2cget and writes the numbers into those sensors' "Value" property with
#    busctl. bmcweb then shows them in Redfish and the web UI.
#
#  If this script stops (or the chip reports a fault), it stops writing, and
#  after the "Timeout" from the JSON (10 s) the sensors become "not
#  available" instead of showing a stale number.
#
#  Settings come from environment variables (set them in
#  /etc/default/sim3-poll, which the service reads):
#    SIM3_BUS        I2C bus number            (default 2  = /dev/i2c-2)
#    SIM3_ADDR       7-bit I2C address         (default 0x48)
#    SIM3_INTERVAL   seconds between readings  (default 2)
#    SIM3_SIMULATE   1 = make up readings instead of using I2C (default 0),
#                    so you can try everything without the chip
# =============================================================================
set -u

BUS="${SIM3_BUS:-2}"
ADDR="${SIM3_ADDR:-0x48}"
INTERVAL="${SIM3_INTERVAL:-2}"
SIMULATE="${SIM3_SIMULATE:-0}"

# Where the sensors live on D-Bus. The service name belongs to dbus-sensors'
# externalsensor program; the object paths are built from the JSON:
#   /xyz/openbmc_project/sensors/<type from Units>/<Name, spaces -> _>
SERVICE="xyz.openbmc_project.ExternalSensor"
TEMP_PATH="/xyz/openbmc_project/sensors/temperature/SIM3_Temperature"
VOLT_PATH="/xyz/openbmc_project/sensors/voltage/SIM3_Voltage"
VALUE_IFACE="xyz.openbmc_project.Sensor.Value"

# Status register bits.
STATUS_READY=0x01
STATUS_ALERT=0x02
STATUS_FAULT=0x80

log() { echo "sim3-poll: $*"; }   # stdout goes to the journal (journalctl -u sim3-poll)

# --- Reading the chip ---------------------------------------------------------

# read_reg <register>  ->  prints the register's value as a decimal number.
# "i2cget -y <bus> <addr> <reg> b" reads one byte and prints it like "0x19".
# -y means "don't ask for confirmation". Returns non-zero if the chip
# doesn't answer (wrong wiring, wrong address, missing pull-ups...).
read_reg() {
    local hex
    hex=$(i2cget -y "$BUS" "$ADDR" "$1" b 2>/dev/null) || return 1
    echo $(( hex ))
}

# In simulation mode, pretend: temperature wanders between 20 and 29 °C,
# voltage between 3.24 and 3.36 V, status always "ready".
SIM_TICK=0
read_all_simulated() {
    SIM_TICK=$(( SIM_TICK + 1 ))
    RAW_TEMP=$(( 20 + SIM_TICK % 10 ))
    RAW_VOLT=$(( 162 + SIM_TICK % 7 ))
    RAW_STATUS=$STATUS_READY
}

read_all() {
    if [ "$SIMULATE" = "1" ]; then
        read_all_simulated
        return 0
    fi
    RAW_STATUS=$(read_reg 0x02) || return 1
    RAW_TEMP=$(read_reg 0x00)   || return 1
    RAW_VOLT=$(read_reg 0x01)   || return 1
}

# --- Converting raw numbers to real units --------------------------------------

# TEMP is "signed 8-bit": 0..127 are positive, 128..255 mean -128..-1.
to_celsius() {
    local raw=$1
    if [ "$raw" -gt 127 ]; then raw=$(( raw - 256 )); fi
    echo "$raw"
}

# VOLT is 20 mV per step. Bash only does whole numbers, so compute
# millivolts and print them as volts with three decimals (3300 -> 3.300).
to_volts() {
    local mv=$(( $1 * 20 ))
    printf '%d.%03d' $(( mv / 1000 )) $(( mv % 1000 ))
}

# --- Talking to D-Bus ------------------------------------------------------------

# set_value <object path> <number>
# Writes the sensor's Value property ("d" = a double, i.e. a decimal number).
set_value() {
    busctl set-property "$SERVICE" "$1" "$VALUE_IFACE" Value d "$2"
}

# Record an event in the BMC's event log (visible in Redfish under
# /redfish/v1/Systems/system/LogServices/EventLog/Entries and in the web UI's
# Event logs page, once bmcweb's redfish-dbus-log option is enabled).
log_event() {
    local severity=$1 message=$2
    busctl call xyz.openbmc_project.Logging /xyz/openbmc_project/logging \
        xyz.openbmc_project.Logging.Create Create "ssa{ss}" \
        "$message" "xyz.openbmc_project.Logging.Entry.Level.$severity" \
        2 "SENSOR" "SIM3" "I2C_DEVICE" "$BUS-$ADDR" > /dev/null ||
        log "could not create event log entry"
}

# Wait until entity-manager and externalsensor have created our sensors.
# "busctl introspect" fails while the object doesn't exist yet.
wait_for_sensors() {
    local tries=0
    until busctl introspect "$SERVICE" "$TEMP_PATH" > /dev/null 2>&1 &&
          busctl introspect "$SERVICE" "$VOLT_PATH" > /dev/null 2>&1; do
        tries=$(( tries + 1 ))
        if [ $(( tries % 15 )) -eq 1 ]; then
            log "waiting for $TEMP_PATH and $VOLT_PATH to appear on D-Bus..."
        fi
        sleep 2
    done
    log "sensors found on D-Bus"
}

# --- Main loop ---------------------------------------------------------------------

log "starting: bus $BUS, address $ADDR, every ${INTERVAL}s, simulate=$SIMULATE"
wait_for_sensors

last_state=""    # remembers the previous state so we only log changes

while true; do
    if ! read_all; then
        state="no-answer"
    elif (( RAW_STATUS & STATUS_FAULT )); then
        state="fault"
    elif ! (( RAW_STATUS & STATUS_READY )); then
        state="not-ready"
    else
        state="ok"
    fi

    if [ "$state" = "ok" ]; then
        temp=$(to_celsius "$RAW_TEMP")
        volts=$(to_volts "$RAW_VOLT")
        set_value "$TEMP_PATH" "$temp" || log "failed to write temperature"
        set_value "$VOLT_PATH" "$volts" || log "failed to write voltage"
        if (( RAW_STATUS & STATUS_ALERT )) && [ "$last_state" != "ok-alert" ]; then
            log "chip raised its ALERT bit (temp ${temp} °C, ${volts} V)"
            log_event Warning "SIM3 sensor raised its alert flag"
            state="ok-alert"
        elif (( RAW_STATUS & STATUS_ALERT )); then
            state="ok-alert"
        fi
    fi

    # Report state changes once, not every loop.
    if [ "$state" != "$last_state" ]; then
        case "$state" in
            ok)        log "readings OK" ;;
            no-answer) log "no answer from $ADDR on i2c-$BUS (check wiring, address, power)"
                       log_event Warning "SIM3 sensor is not responding on I2C" ;;
            fault)     log "chip reports FAULT (status 0x$(printf %02x "$RAW_STATUS"))"
                       log_event Critical "SIM3 sensor reports an internal fault" ;;
            not-ready) log "chip says data not ready yet" ;;
        esac
        last_state=$state
    fi

    sleep "$INTERVAL"
done
