cmake_minimum_required(VERSION 2.8.3)
project(nvi_phone_gps)

## Compile as C++11, supported in ROS Kinetic and newer
# add_compile_options(-std=c++11)

## Find catkin macros and libraries
## if COMPONENTS list like find_package(catkin REQUIRED COMPONENTS xyz)
## is used, also find other catkin packages
find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  nmea_msgs
  nav_msgs
  sensor_msgs 
)
catkin_package(
#  INCLUDE_DIRS include
   CATKIN_DEPENDS  
#    message_runtime 
    nmea_msgs
    nav_msgs
    sensor_msgs
    rospy
#  DEPENDS system_lib
)

include_directories(
  .
  ${catkin_INCLUDE_DIRScatkin_INCLUDE_DIRS}
)

catkin_install_python(PROGRAMS
  scripts/phone_gps.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
