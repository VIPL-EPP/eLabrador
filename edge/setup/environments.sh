apt-get update -q

# VINS-Mono
# git clone -b 3.2.5 --depth=1 https://gitlab.com/libeigen/eigen.git
apt-get install -y libgoogle-glog-dev libgflags-dev libatlas-base-dev libeigen3-dev libsuitesparse-dev
git clone https://gitlab.com/NikolausDemmel/ceres-solver.git
cd ceres-solver
git checkout dc8ef467e3bf33549373e128c864589e86d7b0b4 # 1.14.0
mkdir build
cd build
cmake ..
make -j3
make install
cd ../..
rm -rf ceres-solver

# Realsense
mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo `lsb_release -cs` main" | \
tee /etc/apt/sources.list.d/librealsense.list
apt-get update -q
apt-get install -y librealsense2 librealsense2-utils
apt-get install -y ros-$ROS_DISTRO-realsense2-camera

# Management
pip install json5 dimsim zhon

# Belt
apt-get install -y libglib2.0-dev libbluetooth-dev bluetooth bluez python-bluez
pip install bluepy
pip install pybluez

# Semantic-SLAM
apt-get install -y ros-$ROS_DISTRO-serial ros-$ROS_DISTRO-pcl-conversions ros-$ROS_DISTRO-pcl-msgs ros-$ROS_DISTRO-tf2-eigen ros-$ROS_DISTRO-pcl-ros ros-$ROS_DISTRO-octomap-msgs ros-$ROS_DISTRO-octomap ros-$ROS_DISTRO-octomap-rviz-plugins

# QFRTK
apt-get install -y libudev-dev ros-$ROS_DISTRO-nmea-msgs

# Servo
pip install gensim pkuseg distance scikit-learn==1.3.2

# Semantic
# link python3 to python
if [ ! -L /usr/bin/python ]; then
    ln -s /usr/bin/python3 /usr/bin/python
fi
pip install torch==1.13.1+cpu torchvision==0.14.1+cpu torchaudio==0.13.1 --extra-index-url https://download.pytorch.org/whl/cpu
pip install websocket-client mmcv-lite

# Calibration
pip install geographiclib progress

# OCR
pip install paddleocr==2.6
pip install paddlepaddle==2.6.2 anyio==4.5.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# planning
pip install pykalman jsonlines openai==1.82.0 typing-extensions==4.12.2
pip install ./nvi_octomap

# voice (tts)
apt install -y espeak
pip install zhtts sounddevice tensorflow-cpu==2.12.0 pyttsx3 edge_tts playsound

# speech (asr)
apt install -y portaudio19-dev
pip install PyAudio dashscope

# fix confict package versions
pip install pillow==9.0.1 grpcio==1.48.2 protobuf==4.25.8 numpy==1.23.5

# clean up
apt-get autoclean
apt-get autoremove
rm -rf /var/lib/apt/lists/*
rm -rf /root/.cache/pip