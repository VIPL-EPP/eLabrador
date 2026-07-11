#!/bin/bash
sleep 2 # wait for the headset to fully connect                                 
sudo -u '#1000' XDG_RUNTIME_DIR=/run/user/1000 pactl set-card-profile bluez_card.02_22_10_28_07_13 headset-head-unit
# sudo -u '#1000' XDG_RUNTIME_DIR=/run/user/1000 pactl set-card-profile bluez_card.03_22_10_28_08_57 headset-head-unit
logger "Switched NANK-RUNNER CC3 headset to HFP profile"



# write a udev rule "/etc/udev/rules.d/99-change-headphone-profile.rules"
# KERNELS=="input*", ACTION=="add", SUBSYSTEM=="input", ATTR{phys}=="b0:3c:dc:b9:6a:8a", RUN+="<repo>/edge/src/NVI/nvi_speech/scripts/change_profile.sh"
