SUMMARY = "SIM3 example I2C sensor for the BeagleBone BMC"
DESCRIPTION = "Entity-manager configuration that creates two ExternalSensor \
sensors, plus a small script that reads the SIM3 chip over I2C and writes \
its readings into them."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

# The files this recipe installs, from the sim3-sensor/ folder next to it.
SRC_URI = " \
    file://beaglebone-sim3.json \
    file://sim3-poll.sh \
    file://sim3-poll.service \
    "
S = "${UNPACKDIR}"

# "systemd" installs and enables the service; "allarch" because nothing
# here is compiled, so one package works for every CPU type.
inherit systemd allarch

SYSTEMD_SERVICE:${PN} = "sim3-poll.service"

# At run time we need: entity-manager (reads the JSON), dbus-sensors
# (externalsensor creates the sensors), i2c-tools (i2cget), bash, and
# systemd (busctl).
RDEPENDS:${PN} = "bash i2c-tools entity-manager dbus-sensors systemd"

do_install() {
    # entity-manager reads every JSON file in this folder at start-up.
    install -D -m 0644 ${S}/beaglebone-sim3.json \
        ${D}${datadir}/entity-manager/configurations/beaglebone-sim3.json

    install -D -m 0755 ${S}/sim3-poll.sh \
        ${D}${libexecdir}/sim3-sensor/sim3-poll.sh

    install -D -m 0644 ${S}/sim3-poll.service \
        ${D}${systemd_system_unitdir}/sim3-poll.service
}

FILES:${PN} += " \
    ${datadir}/entity-manager/configurations/beaglebone-sim3.json \
    ${libexecdir}/sim3-sensor \
    "
