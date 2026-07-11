# Preparation

## Realsense Camera

Launch file is `nvi_realsense.launch`, please change `json_file_path` according to the light environment.
"realsense_auto" turns on auto_exposure, "realsense_AxB" sets autoexposure time to A and gain to B.
"realsense_4x64" is usually used in summer.

## Phone GPS

The default positioning input is Android phone GPS through `nvi_phone_gps.launch`.
The raw phone GPS topic is `/phone_gps/receiver_lla`; it is remapped to
`/ublox_driver/receiver_lla` for compatibility with existing planning nodes.
