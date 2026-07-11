cmake_minimum_required(VERSION 2.8)
project(semantic_cloud)

set(PACKAGE_DEPENDENCIES
  roscpp
	rospy
  sensor_msgs
  nvi_msgs
)

find_package(catkin REQUIRED COMPONENTS ${PACKAGE_DEPENDENCIES})

# add_message_files(
#   FILES
#   stamp_float32array.msg
# )

# Make modules in include/ visible to work place
catkin_python_setup()

# generate_messages(
#   DEPENDENCIES
#   std_msgs
# )

include_directories(
  ${catkin_INCLUDE_DIRS}
)
# CATKIN_DEPENDS roscpp rospy std_msgs message_runtime



catkin_package(
  CATKIN_DEPENDS  ${PACKAGE_DEPENDENCIES}
)
