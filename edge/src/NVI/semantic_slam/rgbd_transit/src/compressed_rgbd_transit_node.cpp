#include <ros/ros.h>
#include <iostream>
#include <string>
#include <vector>
#include <message_filters/subscriber.h>
#include <message_filters/synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/CompressedImage.h>

#include "nvi_msgs/CompressedRGBDImage.h"

using sensor_msgs::CompressedImage;
using sensor_msgs::Image;
typedef message_filters::sync_policies::ApproximateTime<CompressedImage, Image> SyncPolicy;

class RGBDTransit
{
public:
    RGBDTransit(ros::NodeHandle &nh);

    void syncRgbdCallback(const sensor_msgs::CompressedImageConstPtr &rgb_msg, const sensor_msgs::ImageConstPtr &depth_msg);
    void clearRgbdBuffer();
    void spin();

    ros::NodeHandle rgbd_transit_handle;
    message_filters::Subscriber<sensor_msgs::CompressedImage> rgb_sub;
    message_filters::Subscriber<sensor_msgs::Image> depth_sub;
    message_filters::Synchronizer<SyncPolicy> rgbd_sync;
    ros::Publisher rgbd_pub;
    float rgbd_rate;

    std::vector<sensor_msgs::CompressedImageConstPtr> rgb_buffer;
    std::vector<sensor_msgs::ImageConstPtr> depth_buffer;
};

RGBDTransit::RGBDTransit(ros::NodeHandle &nh) : rgbd_sync(SyncPolicy(10), rgb_sub, depth_sub), rgbd_rate(1)
{
    rgbd_transit_handle = nh;
    rgb_sub.subscribe(rgbd_transit_handle, "/image/rgb/compressed", 1);
    depth_sub.subscribe(rgbd_transit_handle, "/image/depth", 1);
    rgbd_sync.registerCallback(boost::bind(&RGBDTransit::syncRgbdCallback, this, _1, _2));
    rgbd_pub = rgbd_transit_handle.advertise<nvi_msgs::CompressedRGBDImage>("/image/rgbd/compressed", 10);
    rgbd_transit_handle.getParam("/compressed_rgbd_transit/rgbd_rate", rgbd_rate);
}

void RGBDTransit::syncRgbdCallback(const sensor_msgs::CompressedImageConstPtr &rgb_msg, const sensor_msgs::ImageConstPtr &depth_msg)
{
    rgb_buffer.push_back(rgb_msg);
    depth_buffer.push_back(depth_msg);
}

void RGBDTransit::clearRgbdBuffer()
{
    rgb_buffer.clear();
    depth_buffer.clear();
}

void RGBDTransit::spin()
{
    ros::Rate loop_rate(rgbd_rate);
    while (ros::ok())
    {
        ros::spinOnce();
        if (!rgb_buffer.empty())
        {
            nvi_msgs::CompressedRGBDImage rgbd_msg;
            sensor_msgs::CompressedImageConstPtr rgb_msg(rgb_buffer.back());
            sensor_msgs::ImageConstPtr depth_msg(depth_buffer.back());
            rgbd_msg.header.frame_id = rgb_msg->header.frame_id;
            rgbd_msg.header.stamp = rgb_msg->header.stamp;
            rgbd_msg.rgb = *rgb_msg;
            rgbd_msg.depth = *depth_msg;
            this->rgbd_pub.publish(rgbd_msg);
            this->clearRgbdBuffer();
        }
        loop_rate.sleep();
    }
}

int main(int argc, char **argv)
{
    ros::init(argc, argv, "rgbd_transit");
    ros::NodeHandle nh;
    RGBDTransit rgbd_transit_node(nh);
    rgbd_transit_node.spin();

    return 0;
}