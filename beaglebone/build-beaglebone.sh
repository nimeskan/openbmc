#!/usr/bin/env bash
# =============================================================================
#  build-beaglebone.sh
#
#  Sets up a Linux machine to build OpenBMC for the BeagleBone Black and then
#  builds the SD card image. It does the same steps as the GitHub Actions
#  workflow (.github/workflows/build-beaglebone.yml), but on your own computer.
#
#  What it does, in order:
#    1. Checks your computer: OS, CPU type, memory, free disk space.
#    2. Installs the Linux packages the Yocto build tools need (uses sudo).
#    3. Sets up the en_US.UTF-8 language setting ("locale") BitBake requires.
#    4. Allows "user namespaces" on Ubuntu 23.10+ (BitBake uses them).
#    5. Downloads (clones) the OpenBMC source code, unless you already have it.
#    6. Creates a build directory with the BeagleBone configuration.
#    7. Checks that the configuration loads (no compiling yet).
#    8. Builds the image (this is the part that takes hours).
#    9. Copies the finished SD card image to an easy-to-find folder.
#
#  Usage:   ./build-beaglebone.sh [options]
#  Run      ./build-beaglebone.sh --help      for the list of options.
#
#  Safe to run again: every step checks whether it is already done. If the
#  build is interrupted (power cut, Ctrl+C, out of disk), run the script again
#  and BitBake continues where it stopped instead of starting over.
#
#  Full explanation of everything here: beaglebone/README.md
# =============================================================================

# -----------------------------------------------------------------------------
# Bash safety settings.
#   -e           stop the script as soon as any command fails
#   -o pipefail  a pipeline ("a | b") fails if any part of it fails
#   -u           using a variable that was never set is an error (catches typos)
# -----------------------------------------------------------------------------
set -euo pipefail

# -----------------------------------------------------------------------------
# Settings. Each one can be changed with a command-line option (see --help)
# or by setting the environment variable of the same name before running.
# -----------------------------------------------------------------------------

# Where the OpenBMC source code comes from. This is the repository that
# contains the BeagleBone layer (meta-evb/meta-evb-beaglebone).
REPO_URL="${REPO_URL:-https://github.com/nimeskan/openbmc.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

# Where the source code lives on your disk. Left empty here; worked out
# below (if this script is inside a checkout, that checkout is used).
REPO_DIR="${REPO_DIR:-}"

# Where the build happens. This directory gets BIG (60+ GB at its peak), so
# put it on a disk with plenty of free space. It holds:
#   conf/           your build configuration (local.conf, bblayers.conf)
#   downloads/      every source archive BitBake downloaded (~4 GB)
#   sstate-cache/   finished pieces of the build, reused on the next build
#   tmp/            work area, and tmp/deploy/images/ with the results
BUILD_DIR="${BUILD_DIR:-$HOME/openbmc-build/beaglebone}"

# Where the finished image gets copied at the end, so you don't have to dig
# through tmp/deploy/images/.
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/openbmc-build/beaglebone-images}"

# The Yocto "machine" (which board) and "image" (which collection of software)
# to build. Don't change these unless you know you want something else.
MACHINE="evb-beaglebone"
IMAGE="obmc-phosphor-image"

# The layer's template directory. It holds local.conf.sample and
# bblayers.conf.sample, which become conf/local.conf and conf/bblayers.conf
# in a new build directory. Path is relative to the source checkout.
TEMPLATE_DIR="meta-evb/meta-evb-beaglebone/conf/templates/default"

# Minimum resources. Below these the script warns you (it doesn't refuse).
MIN_DISK_GB=60      # free space in the build directory's filesystem
MIN_RAM_GB=8        # total memory

# Behaviour switches (changed by options below).
SKIP_PACKAGES=0     # 1 = don't install packages with apt
CHECK_ONLY=0        # 1 = stop after checking the configuration loads
ASSUME_YES=0        # 1 = don't ask "Continue?" questions

# -----------------------------------------------------------------------------
# Small helper functions for readable, coloured output.
# "tput" asks the terminal which colour codes it understands; if the output
# isn't a terminal (e.g. redirected to a file) we skip colours entirely.
# -----------------------------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    BOLD="$(tput bold)"; RED="$(tput setaf 1)"; GREEN="$(tput setaf 2)"
    YELLOW="$(tput setaf 3)"; BLUE="$(tput setaf 4)"; RESET="$(tput sgr0)"
else
    BOLD=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi

STEP_NO=0
step() {                       # Print a numbered step heading.
    STEP_NO=$((STEP_NO + 1))
    printf '\n%s%s==> Step %d: %s%s\n' "$BOLD" "$BLUE" "$STEP_NO" "$*" "$RESET"
}
info()  { printf '    %s\n' "$*"; }
ok()    { printf '    %s✔ %s%s\n' "$GREEN" "$*" "$RESET"; }
warn()  { printf '    %s⚠ %s%s\n' "$YELLOW" "$*" "$RESET" >&2; }
die()   { printf '\n%s%s✘ ERROR: %s%s\n' "$BOLD" "$RED" "$*" "$RESET" >&2; exit 1; }

# Ask a yes/no question. Returns success for "y"/"yes". With --yes, always yes.
confirm() {
    [ "$ASSUME_YES" -eq 1 ] && return 0
    local answer
    read -r -p "    $* [y/N] " answer || return 1
    case "$answer" in [yY]|[yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

usage() {
    cat <<EOF
Build OpenBMC for the BeagleBone Black.

Usage: $0 [options]

Options:
  --repo-dir DIR     Use (or clone into) this OpenBMC source directory.
                     Default: the checkout this script is in, else ~/openbmc
  --build-dir DIR    Build directory. Default: $BUILD_DIR
  --output-dir DIR   Where to copy the finished image. Default: $OUTPUT_DIR
  --repo-url URL     Git URL to clone from. Default: $REPO_URL
  --branch NAME      Git branch to clone. Default: $REPO_BRANCH
  --skip-packages    Don't install system packages (you did it already,
                     or your distribution isn't Debian/Ubuntu).
  --check-only       Set everything up and check the configuration, but
                     don't start the long build.
  -y, --yes          Don't ask for confirmation.
  -h, --help         Show this help.

Example:
  $0 --build-dir /mnt/bigdisk/obmc-build
EOF
}

# -----------------------------------------------------------------------------
# Read the command-line options.
# "$#" is the number of arguments left; "shift" drops the first one.
# -----------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --repo-dir)      REPO_DIR="${2:?--repo-dir needs a value}"; shift 2 ;;
        --build-dir)     BUILD_DIR="${2:?--build-dir needs a value}"; shift 2 ;;
        --output-dir)    OUTPUT_DIR="${2:?--output-dir needs a value}"; shift 2 ;;
        --repo-url)      REPO_URL="${2:?--repo-url needs a value}"; shift 2 ;;
        --branch)        REPO_BRANCH="${2:?--branch needs a value}"; shift 2 ;;
        --skip-packages) SKIP_PACKAGES=1; shift ;;
        --check-only)    CHECK_ONLY=1; shift ;;
        -y|--yes)        ASSUME_YES=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               usage >&2; die "Unknown option: $1" ;;
    esac
done

# Turn relative paths (like "../build") into full paths, because the script
# changes directory later and a relative path would then point elsewhere.
# "realpath -m" works even if the directory doesn't exist yet.
BUILD_DIR="$(realpath -m "$BUILD_DIR")"
OUTPUT_DIR="$(realpath -m "$OUTPUT_DIR")"

# Work out the source directory. This script lives at <checkout>/beaglebone/,
# so if the directory above it has the BeagleBone layer, use that checkout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$REPO_DIR" ]; then
    if [ -d "$SCRIPT_DIR/../meta-evb/meta-evb-beaglebone" ]; then
        REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    else
        REPO_DIR="$HOME/openbmc"
    fi
fi
REPO_DIR="$(realpath -m "$REPO_DIR")"

printf '%sOpenBMC for BeagleBone Black — build script%s\n' "$BOLD" "$RESET"
info "Source code:      $REPO_DIR"
info "Build directory:  $BUILD_DIR"
info "Image output:     $OUTPUT_DIR"

# =============================================================================
step "Check this computer"
# =============================================================================

# BitBake refuses to run as root (the administrator account), because a
# mistake in a build recipe could then damage your system. Run the script as
# your normal user; it uses "sudo" only for the few steps that need it.
if [ "$(id -u)" -eq 0 ]; then
    die "Don't run this script as root or with sudo. Run it as your normal user."
fi
ok "Running as normal user '$(id -un)'"

# Must be Linux. (On Windows, use WSL2 with Ubuntu; see the README.)
[ "$(uname -s)" = "Linux" ] || die "This script only runs on Linux."

# Yocto's prebuilt helper ("uninative") exists for x86-64 and 64-bit ARM PCs.
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|aarch64) ok "CPU architecture $ARCH is supported" ;;
    *) warn "CPU architecture $ARCH is not tested with Yocto; the build may fail." ;;
esac

# Read the distribution name from /etc/os-release (a standard file on every
# modern Linux). "ID" is e.g. "ubuntu" or "debian".
OS_ID="unknown"; OS_NAME="unknown"
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    OS_ID="$(. /etc/os-release && echo "${ID:-unknown}")"
    # shellcheck disable=SC1091
    OS_NAME="$(. /etc/os-release && echo "${PRETTY_NAME:-unknown}")"
fi
info "Operating system: $OS_NAME"
case "$OS_ID" in
    ubuntu|debian) ok "Ubuntu/Debian detected (tested on Ubuntu 24.04)" ;;
    *) warn "Not Ubuntu/Debian. The script is written for Ubuntu 24.04; other systems may need changes." ;;
esac
if [ "$SKIP_PACKAGES" -eq 0 ] && ! command -v apt-get >/dev/null 2>&1; then
    die "This script installs packages with apt (Ubuntu/Debian). On another
    distribution, install the Yocto host packages yourself (see README) and
    re-run with --skip-packages."
fi

# CPU cores: BitBake runs that many tasks in parallel. More = faster build.
CPUS="$(nproc)"
info "CPU cores:        $CPUS  (a first build takes several hours; more cores = faster)"

# Memory: /proc/meminfo reports kB. Compiling big C++ projects in parallel
# needs about 2 GB per core.
RAM_GB=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
if [ "$RAM_GB" -lt "$MIN_RAM_GB" ]; then
    warn "Only ${RAM_GB} GB of memory. ${MIN_RAM_GB}+ GB is recommended; the build may run out of memory."
else
    ok "Memory: ${RAM_GB} GB"
fi

# Free disk space where the build directory will be. The directory may not
# exist yet, so walk up until we find a parent that does, then ask "df".
probe="$BUILD_DIR"
while [ ! -d "$probe" ]; do probe="$(dirname "$probe")"; done
FREE_GB=$(( $(df --output=avail -k "$probe" | tail -1) / 1024 / 1024 ))
if [ "$FREE_GB" -lt "$MIN_DISK_GB" ]; then
    warn "Only ${FREE_GB} GB free at $probe. The build needs about ${MIN_DISK_GB} GB."
    warn "Pick another place with --build-dir, or free some space."
    confirm "Continue anyway?" || die "Stopped. Not enough disk space."
else
    ok "Free disk space: ${FREE_GB} GB"
fi

if [ "$CHECK_ONLY" -eq 0 ]; then
    info ""
    info "This will install packages (with sudo), download about 4 GB, and"
    info "then build for several hours."
    confirm "Continue?" || die "Stopped at your request."
fi

# =============================================================================
step "Install the packages the build tools need"
# =============================================================================
# This is the official Yocto list of "host packages" for Ubuntu/Debian:
#   https://docs.yoctoproject.org/ref-manual/system-requirements.html
#
#   build-essential  C/C++ compiler (gcc, g++) and make, used for the tools
#                    that run on your PC during the build
#   chrpath          fixes paths inside compiled programs
#   cpio, file, unzip, xz-utils, zstd, lz4, liblz4-tool
#                    archive and compression tools
#   debianutils      small helpers such as "which"
#   diffstat         summarises patches
#   gawk             GNU awk, a text-processing language
#   git              downloads source code repositories
#   iputils-ping     "ping", used by the network sanity check
#   libacl1          file permission (ACL) library
#   locales          language/encoding support (see next step)
#   python3 + python3-git/-jinja2/-pexpect/-subunit
#                    BitBake itself is written in Python
#   socat            network relay tool, used by some test tools
#   texinfo          documentation tools some packages need to build
#   wget             downloads source archives
if [ "$SKIP_PACKAGES" -eq 1 ]; then
    info "Skipped (--skip-packages)."
else
    PACKAGES=(
        build-essential chrpath cpio debianutils diffstat file gawk gcc git
        iputils-ping libacl1 liblz4-tool locales python3 python3-git
        python3-jinja2 python3-pexpect python3-subunit socat texinfo unzip
        wget xz-utils zstd lz4
    )
    info "You may be asked for your password (sudo)."
    # "apt-get update" refreshes the list of available packages first.
    sudo apt-get update
    # DEBIAN_FRONTEND=noninteractive stops packages from asking questions.
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"
    ok "Packages installed"
fi

# =============================================================================
step "Set up the en_US.UTF-8 locale"
# =============================================================================
# A "locale" tells programs which language and text encoding to use. BitBake
# insists on a UTF-8 one so file names and messages are handled consistently.
# "locale -a" lists the ones installed; the name may be spelled "en_US.utf8".
if locale -a 2>/dev/null | grep -qiE '^en_US\.utf-?8$'; then
    ok "en_US.UTF-8 is available"
elif [ "$SKIP_PACKAGES" -eq 1 ]; then
    warn "en_US.UTF-8 isn't installed and --skip-packages was given; BitBake may refuse to start."
else
    # Debian needs the line uncommented in /etc/locale.gen; Ubuntu just needs
    # locale-gen to be told the name. Doing both works on either.
    if [ -f /etc/locale.gen ]; then
        sudo sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen
    fi
    sudo locale-gen en_US.UTF-8
    ok "en_US.UTF-8 generated"
fi
# Use it for everything this script starts.
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# =============================================================================
step "Allow user namespaces (needed on Ubuntu 23.10 and newer)"
# =============================================================================
# BitBake runs each build task in an isolated "user namespace" so a recipe
# can't reach the internet when it shouldn't. Ubuntu 23.10+ blocks
# unprivileged user namespaces through AppArmor (a security module). We turn
# that restriction off for the current session only; it comes back after a
# reboot, and this script turns it off again next time you run it.
#
# To make it permanent instead, run once:
#   echo 'kernel.apparmor_restrict_unprivileged_userns = 0' | \
#       sudo tee /etc/sysctl.d/60-yocto-userns.conf
USERNS_SETTING=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
if [ -r "$USERNS_SETTING" ] && [ "$(cat "$USERNS_SETTING")" = "1" ]; then
    info "AppArmor restricts user namespaces; relaxing it until the next reboot."
    sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
    ok "User namespaces allowed"
else
    ok "Nothing to change on this system"
fi

# =============================================================================
step "Get the OpenBMC source code"
# =============================================================================
# The repository contains everything: BitBake (the build tool),
# OpenEmbedded-Core (the base recipes), the OpenBMC layers, and the
# BeagleBone layer. Nothing else needs to be cloned by hand; BitBake
# downloads each package's own source code during the build.
if [ -d "$REPO_DIR/.git" ]; then
    ok "Using existing checkout at $REPO_DIR"
    info "(Not updating it; run 'git -C $REPO_DIR pull' yourself if you want the latest.)"
else
    if [ -e "$REPO_DIR" ] && [ -n "$(ls -A "$REPO_DIR" 2>/dev/null)" ]; then
        die "$REPO_DIR exists but isn't a git checkout. Move it away or use --repo-dir."
    fi
    info "Cloning $REPO_URL (branch $REPO_BRANCH) into $REPO_DIR"
    # A full clone (with history) is ~250 MB. Use "--depth 1" yourself if
    # you only want the latest files.
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
    ok "Cloned"
fi

# Make sure this checkout actually has the BeagleBone layer.
[ -f "$REPO_DIR/meta-evb/meta-evb-beaglebone/conf/machine/$MACHINE.conf" ] ||
    die "$REPO_DIR has no BeagleBone layer (meta-evb/meta-evb-beaglebone). Wrong repository or branch?"
[ -f "$REPO_DIR/$TEMPLATE_DIR/local.conf.sample" ] ||
    die "Template files missing in $REPO_DIR/$TEMPLATE_DIR"
ok "BeagleBone layer found"

# =============================================================================
step "Create the build directory"
# =============================================================================
# "oe-init-build-env" is the standard Yocto setup script. It must be
# "sourced" (run inside this shell with ".") rather than executed, because it
# changes this shell: it puts bitbake on the PATH and cd's into the build
# directory.
#
# TEMPLATECONF tells it which configuration templates to copy into a NEW
# build directory. If conf/ already exists, your existing (possibly edited)
# local.conf and bblayers.conf are kept as they are.
if [ -f "$BUILD_DIR/conf/local.conf" ]; then
    info "Build directory already set up; keeping its configuration."
else
    info "Creating $BUILD_DIR from the BeagleBone templates."
fi
mkdir -p "$BUILD_DIR"
cd "$REPO_DIR"
export TEMPLATECONF="$REPO_DIR/$TEMPLATE_DIR"
# The Yocto script uses variables that may be unset, which "set -u" would
# treat as an error, so relax that just while it runs.
set +u
# shellcheck disable=SC1091
. ./oe-init-build-env "$BUILD_DIR" > /dev/null
set -u
[ "$(pwd)" = "$BUILD_DIR" ] || die "oe-init-build-env didn't switch to $BUILD_DIR"
command -v bitbake >/dev/null || die "bitbake isn't on the PATH after oe-init-build-env"
ok "Build environment ready in $BUILD_DIR"
info "conf/local.conf     - build settings (machine, distro, rm_work, ...)"
info "conf/bblayers.conf  - which layers are used"

# =============================================================================
step "Check the configuration"
# =============================================================================
# "bitbake -e" reads all layers and recipes and prints the final value of
# every variable, without building anything. It's a quick way to catch
# configuration mistakes before committing to a multi-hour build. We pick out
# a few key values to show you.
info "Parsing recipes (takes a minute or two the first time)..."
ENV_DUMP="$BUILD_DIR/bitbake-env.txt"
if ! bitbake -e "$IMAGE" > "$ENV_DUMP" 2>&1; then
    tail -n 30 "$ENV_DUMP" >&2
    die "BitBake couldn't load the configuration (full output: $ENV_DUMP)"
fi
get_var() { sed -n "s/^$1=\"\(.*\)\"$/\1/p" "$ENV_DUMP" | head -n 1; }
info "MACHINE        = $(get_var MACHINE)"
info "DISTRO         = $(get_var DISTRO)"
info "IMAGE_FSTYPES  = $(get_var IMAGE_FSTYPES)"
info "WKS_FILE       = $(get_var WKS_FILE)"
[ "$(get_var MACHINE)" = "$MACHINE" ] ||
    die "MACHINE is '$(get_var MACHINE)', expected '$MACHINE'. Check $BUILD_DIR/conf/local.conf"
ok "Configuration loads"

if [ "$CHECK_ONLY" -eq 1 ]; then
    printf '\n%sCheck finished (--check-only). Everything is ready to build.%s\n' "$GREEN" "$RESET"
    info "Start the build with:  $0 --build-dir $BUILD_DIR"
    exit 0
fi

# =============================================================================
step "Build the image (this takes hours)"
# =============================================================================
# "bitbake obmc-phosphor-image" builds the image and, first, everything it
# depends on: a cross-compiler for the BeagleBone's ARM CPU, the Linux
# kernel, U-Boot (the bootloader), and several hundred software packages.
# For each one it runs tasks like fetch, unpack, patch, configure, compile,
# install and package; then it assembles the root filesystem and the SD card
# image.
#
# Progress shows as "Running task 1234 of 6789". If it stops, re-run this
# script: finished work is reused from sstate-cache/ and tmp/.
#
# Everything BitBake prints also goes to a log file.
LOG_FILE="$BUILD_DIR/build-$(date +%Y%m%d-%H%M%S).log"
info "Log file: $LOG_FILE"
START_TIME=$(date +%s)
set +e
bitbake "$IMAGE" 2>&1 | tee "$LOG_FILE"
BUILD_RC=${PIPESTATUS[0]}
set -e
ELAPSED=$(( $(date +%s) - START_TIME ))
info "Build time: $((ELAPSED / 3600))h $(((ELAPSED % 3600) / 60))m"
if [ "$BUILD_RC" -ne 0 ]; then
    die "The build failed (exit code $BUILD_RC).
    Look for lines starting with 'ERROR:' in $LOG_FILE.
    Each failed task's own log is listed there (a file named log.do_<task>).
    See 'Troubleshooting' in beaglebone/README.md. Re-running this script
    continues from where it stopped."
fi
ok "Build finished"

# =============================================================================
step "Collect the SD card image"
# =============================================================================
# BitBake writes results to tmp/deploy/images/<machine>/. File names there
# include a timestamp; the names without one are symbolic links ("shortcuts")
# to the newest build, which is what we copy ("cp -L" follows the link).
#
#   *.wic.xz    the complete SD card image, xz-compressed
#   *.wic.bmap  a "block map" that lets bmaptool write the card faster
DEPLOY_DIR="$BUILD_DIR/tmp/deploy/images/$MACHINE"
WIC="$DEPLOY_DIR/$IMAGE-$MACHINE.rootfs.wic.xz"
BMAP="$DEPLOY_DIR/$IMAGE-$MACHINE.rootfs.wic.bmap"
[ -e "$WIC" ] || die "Expected image not found: $WIC"
mkdir -p "$OUTPUT_DIR"
cp -L "$WIC" "$OUTPUT_DIR/"
if [ -e "$BMAP" ]; then cp -L "$BMAP" "$OUTPUT_DIR/"; fi
# A checksum lets you confirm the file wasn't corrupted when copying it.
( cd "$OUTPUT_DIR" && sha256sum ./*.wic.* > SHA256SUMS )
ok "Image copied to $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"

cat <<EOF

${GREEN}${BOLD}Done!${RESET} Your OpenBMC image for the BeagleBone Black is:

    $OUTPUT_DIR/$(basename "$WIC")

Next steps (details in beaglebone/README.md, section "Flash and boot"):
  1. Write it to a microSD card (4 GB or larger), e.g. with balenaEtcher, or:
       xzcat "$OUTPUT_DIR/$(basename "$WIC")" | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
     (replace /dev/sdX with your card; check with 'lsblk' first!)
  2. Put the card in the BeagleBone, hold the S2 button, plug in power.
  3. Connect Ethernet, find the board's IP address in your router.
  4. Open https://<board-ip>/ and log in as root / 0penBmc
EOF
