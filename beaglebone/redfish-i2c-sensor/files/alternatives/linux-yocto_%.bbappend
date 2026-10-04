# Add lm75.cfg (in the linux-yocto/ folder next to this file) to the kernel
# configuration. Goes in meta-evb/meta-evb-beaglebone/recipes-kernel/linux/.
FILESEXTRAPATHS:prepend := "${THISDIR}/linux-yocto:"
SRC_URI:append:evb-beaglebone = " file://lm75.cfg"
