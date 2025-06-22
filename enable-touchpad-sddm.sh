#!/bin/bash

# -----------------------------------------------------------------------------
# enable-touchpad-sddm.sh
#
# This script:
#   1. Adds the 'sddm' user to the 'input' group (needed for touchpad at login).
#   2. Creates a libinput touchpad config in /etc/X11/xorg.conf.d/ to enable
#      tap-to-click and natural scrolling system-wide (including SDDM).
#   3. Restarts the SDDM display manager to apply changes.
#
# USAGE:
#   sudo bash enable-touchpad-sddm.sh
#
# WIKI:
#   - SDDM (Simple Desktop Display Manager) is the login greeter for many Linux distros.
#   - By default, SDDM might not have permission to access touchpad events.
#   - Adding 'sddm' to the 'input' group gives it permission.
#   - Libinput options like Tapping and NaturalScrolling improve user experience.
#
# NOTE: Requires root privileges.
# -----------------------------------------------------------------------------

# Ensure the script is run as root
if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo bash $0)"
  exit 1
fi

echo "Adding 'sddm' user to 'input' group..."
usermod -aG input sddm

echo "Creating /etc/X11/xorg.conf.d/30-touchpad.conf with tap-to-click and natural scrolling enabled..."
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/30-touchpad.conf << EOF
Section "InputClass"
    Identifier "libinput touchpad catchall"
    MatchIsTouchpad "on"
    MatchDevicePath "/dev/input/event*"
    Driver "libinput"
    Option "Tapping" "on"
    Option "TappingButtonMap" "lrm"
    Option "NaturalScrolling" "on"
EndSection
EOF

echo "Restarting SDDM to apply changes..."
systemctl restart sddm

echo "Done! Your touchpad should now work (with tap-to-click) at the login screen."