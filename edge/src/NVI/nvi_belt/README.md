# nvi_belt

A ROS package for communication with vibrational belt in navigation for visually impaired person application.

This package supports three methods to connect the vibrational belt: HC-05 Bluetooth/RFCOMM, BLE, and wired serial. The final public hardware uses the HC-05 Bluetooth serial module. BLE is kept for legacy compatibility, and wired serial is mainly used for debugging.

## Table of Contents

- [Environment](#Environment)
- [Usage](#Usage)
    - [Install](#Install)
    - [Compile](#Compile)
    - [Run](#Run)
    - [Test](#Test)
- [Author](#Author)
- [License](#license)

## Environment
- Linux
- ROS noetic
- Python3

## Usage

Firstly install this package and move it to your workspace.

### Install

#### HC-05 Bluetooth
Dowanload [pybluez](https://github.com/pybluez/pybluez) in Github, and install it by setup.py file. The according node file is nvi_belt_bt_node.py
```sh
$ sudo apt install libglib2.0-dev libbluetooth-dev bluetooth bluez python-bluez
$ cd pybluez
$ sudo ~/anaconda3/envs/blind/bin/python setup.py install
```
#### ble
Install [bluepy](https://github.com/IanHarvey/bluepy) by pip or Github like bluetooth. The according node file is nvi_belt_node.py
```sh
$ sudo apt install python3-pip libglib2.0-dev
$ sudo pip3 install bluepy
```

#### serial
Install ROS [serial](http://wiki.ros.org/serial) package.
```sh
sudo apt install ros-$ROS_DISTRO-serial
```

### Compile

Compile this package in your workspace
```bash
$ catkin_make
```

### Run

Pair the HC-05 module with Ubuntu first, then export the module MAC address:

```bash
export BELT_BLUETOOTH_MAC="00:00:00:00:00:00"
```

Choose the connection mode in `launch/nvi_belt.launch`. Enable one connection mode at a time. For the final HC-05 Bluetooth path:

```bash
roslaunch nvi_belt nvi_belt.launch device_bt:=true device_ble:=false device_serial:=false bluetooth_mac_address:=$BELT_BLUETOOTH_MAC
```
or (the deafult mode in this launch file is bluetooth connection.)
```bash
roslaunch nvi_belt nvi_belt.launch 
```

Do not commit a real `bluetooth_mac_address` to the launch file. Use `BELT_BLUETOOTH_MAC` or pass the launch argument locally. The HC-05 serial baud rate on the belt firmware side is `9600`.

### Test

Publish a topic to the belt node to control vibration.
```bash
rostopic pub /local_planning/belt nvi_msgs/HeaderString "header:
  stamp: now
data: '${MODE}${POSITION}${DEGREE}'"
```
E.g.
```bash
rostopic pub /local_planning/belt nvi_msgs/HeaderString "header:
  stamp: now
data: '001'"
```

## Author

- Name: Lixuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn



## License
This package is released under GPLv3 as part of this repository. See the
repository root `README.md` license section and `LICENSE` for third-party
notices.
