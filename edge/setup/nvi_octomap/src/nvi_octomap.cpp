#include  <octomap/octomap.h>
#include <octomap_msgs/Octomap.h>
#include "conversions.h"
#include "nvi_octomap.h"
#include <utility>


ColorOctree::ColorOctree(OctomapMsg &msg)
{
    octomap_msgs::Octomap fullMsg;
    fullMsg.id = msg.id;
    fullMsg.resolution = msg.resolution;
    fullMsg.data = std::move(msg.data);
    octomap::AbstractOcTree *absTree = octomap_msgs::fullMsgToMap(fullMsg);
    tree = dynamic_cast<octomap::ColorOcTree *>(absTree);
}

bool ColorOctree::getMapFromMsg(OctomapMsg &msg)
{
    if (tree){
        delete tree;
        tree = 0;
    }
    octomap_msgs::Octomap fullMsg;
    fullMsg.id = msg.id;
    fullMsg.resolution = msg.resolution;
    fullMsg.data = std::move(msg.data);
    octomap::AbstractOcTree *absTree = octomap_msgs::fullMsgToMap(fullMsg);
    tree = dynamic_cast<octomap::ColorOcTree *>(absTree);
    if (tree){
        return true;
    }else{
        return false;
    }
}

OctomapMsg ColorOctree::ColorOctree::getMsgFromMap()
{
    if(!tree){
        throw "warning: no map exists.";
    }
    octomap_msgs::Octomap fullMsg;
    octomap_msgs::fullMapToMsg(*tree, fullMsg);
    OctomapMsg msg;
    msg.id = fullMsg.id;
    msg.resolution = fullMsg.resolution;
    msg.data = std::move(fullMsg.data);
    return msg;
}

octomath::Vector3 ColorOctree::getMetricMax()
{
    double x, y, z;
    tree->getMetricMax(x, y, z);
    return octomath::Vector3(x, y, z);
}

octomath::Vector3 ColorOctree::getMetricMin()
{
    double x, y, z;
    tree->getMetricMin(x, y, z);
    return octomath::Vector3(x, y, z);
}


