// #include <octomap_generator/octomap_generator_ros.h>
// #include <pcl_ros/transforms.h>
// #include <pcl_ros/impl/transforms.hpp>
// #include <octomap_msgs/conversions.h>
// #include <pcl/conversions.h>
// #include <cmath>
// #include <sstream>
// #include <cstring> 
// # subscribe to /semantic_pcl/semantic_pcl, and publish topic to /semantic/2dmap
// void Get_2dmap(const sensor_msgs::PointCloud2::ConstPtr& cloud_msg)
// {
//   // Voxel filter to down sample the point cloud
//   // Create the filtering object
//   pcl::PCLPointCloud2::Ptr cloud (new pcl::PCLPointCloud2 ());
//   pcl_conversions::toPCL(*cloud_msg, *cloud);
  
// }

// int main(int argc, char** argv)
// {
//   ros::init(argc, argv, "2dmap_generator");
//   ros::NodeHandle nh;
  
//   return 0;
// }