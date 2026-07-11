# nvi_speech

A ROS package for speech-to-text in navigation for visually impaired person application.

This package mainly uses the [pyAudio](https://pypi.org/project/PyAudio/) & [ASET Speech](https://github.com/nl8590687/ASRT_SpeechRecognition) package. Users can conveniently use this package to create their speech-to-text application in ROS. 

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

This package requires pyAudio and dimsim to make this application come true. 
```sh
$ sudo apt install python3-pyaudio portaudio19-dev
$ pip install PyAudio
$ pip install dimsim
```

## Problems

1. Check whether sound input is avaliable in system sound setting. If the bluetooth headphone is set to unsuitable profile (usually A2DP, which only contains output) by default, you can add the "scripts/change_profile.sh" into udev rules. 

2. If 1. doesn't work, run `pactl list cards` and make sure `headset-head-unit` profile is avaliable. Otherwise, install [pipewire](https://forum.ubuntu.com.cn/viewtopic.php?t=493482).

### Compile

compile this package in your workspace
```bash
$ catkin_make
```

### Run

run the launch file to run this package node
```bash
roslaunch nvi_speech nvi_speech.launch
```
if there are some errors, running this command make give some help
```bash
chmod +x nvi_speech/scripts/nvi_speech_node.py
```


### Test

speak the command in config list in chinese, you will get the translated command message in '/speech/command' if the voice is matched.
```
rostopic echo /speech/command
```

## Author

- Name: Lixuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn

This project exists thanks to the [pyAudio](https://pypi.org/project/PyAudio/) & [ASET Speech](https://github.com/nl8590687/ASRT_SpeechRecognition) support.


## License
This package is released under GPLv3 as part of this repository. The bundled
ASRT Speech Recognition Tool code remains under its original GPLv3-or-later
terms. See the repository root `README.md` license section and `LICENSE` for
details.
