#ifndef NVI_OCTOMAP_H
#define NVI_OCTOMAP_H
#include <octomap/octomap.h>
#include <octomap/ColorOcTree.h>
#include <octomap_msgs/Octomap.h>
#include <octomap/math/Vector3.h>
struct OctomapMsg
{
    std::string id;
    double resolution;
    std::vector<int8_t> data;
    OctomapMsg() : id(""), resolution(0.1) {}
    OctomapMsg(std::string id_, double resolution_, std::vector<int8_t> &data_) : id(id_), resolution(resolution_),data(data_) {}
};

// struct Point{
//     double x, y, z;
//     Point() : x(0), y(0), z(0) {}
//     Point(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}
// };

// class leaf_iterator{
// public:
//     leaf_iterator() : iterator (){}
//     leaf_iterator(const leaf_iterator &iterator_) : iterator(iterator_.iterator) {}
//     inline void next() { ++iterator; }
//     static inline bool equal(leaf_iterator iterator_1, leaf_iterator iterator_2) { return iterator_1.iterator == iterator_2.iterator; }
//     static inline bool notEqual(leaf_iterator iterator_1, leaf_iterator iterator_2) { return iterator_1.iterator != iterator_2.iterator; }
//     inline double getX() { return iterator.getX(); }
//     inline double getY() { return iterator.getY(); }
//     inline double getZ() { return iterator.getZ(); }
//     inline octomap::ColorOcTreeNode::Color getColor() { return iterator->getColor(); }
//     inline const octomap::OcTreeKey &getKey() { return iterator.getKey(); }

// private:
//     octomap::ColorOcTree::leaf_iterator iterator;
// };

class ColorOctree{
public:
    ColorOctree() : tree(0){}
    ColorOctree(OctomapMsg &msg);

    // conversion
    bool getMapFromMsg(OctomapMsg &msg);
    OctomapMsg getMsgFromMap();
    octomath::Vector3 getMetricMax();
    octomath::Vector3 getMetricMin();
    inline void deleteNode(const octomap::OcTreeKey &key) { tree->deleteNode(key); }
    inline octomap::ColorOcTree::leaf_iterator begin_leafs() { return tree->begin_leafs(); }
    inline octomap::ColorOcTree::leaf_iterator end_leafs() { return tree->end_leafs(); }
    inline octomap::ColorOcTree::leaf_bbx_iterator begin_leafs_bbx(const octomath::Vector3 &min, const octomath::Vector3 &max) { return tree->begin_leafs_bbx(min, max); }
    inline octomap::ColorOcTree::leaf_bbx_iterator end_leafs_bbx() { return tree->end_leafs_bbx(); }
    inline bool isMapExist(){if(tree){return true; }return false;}
    // octomap::ColorOcTreeNode::Color

private:
    octomap::ColorOcTree *tree;
};

#endif