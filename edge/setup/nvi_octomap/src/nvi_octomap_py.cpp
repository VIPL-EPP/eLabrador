#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "nvi_octomap.h"
#include <string>

namespace py = pybind11;

PYBIND11_MODULE(nvi_octomap, m)
{
    m.doc() = "an octomap python api for navigation for visually impaired people project.";

    // py::class_<Point>(m, "Point")
    //     .def(py::init<>())
    //     .def(py::init<double, double, double>(), "initialize Point with three double number")
    //     .def("__str__", [](const Point &p)
    //          { return "(" + std::to_string(p.x) + ", " + std::to_string(p.y) + ", " + std::to_string(p.z) + ")"; })
    //     .def_readwrite("x", &Point::x)
    //     .def_readwrite("y", &Point::y)
    //     .def_readwrite("z", &Point::z);

    // Point3d <- Vector3
    typedef octomath::Vector3 Point3d;
    py::class_<Point3d>(m, "Point3d")
        .def(py::init<>())
        .def(py::init<const Point3d &>())
        .def(py::init<float, float, float>())
        .def("cross", &Point3d::cross)
        .def("dot", &Point3d::dot)
        .def("x", py::overload_cast<>(&Point3d::x, py::const_))
        .def("y", py::overload_cast<>(&Point3d::y, py::const_))
        .def("z", py::overload_cast<>(&Point3d::z, py::const_))
        .def("roll", py::overload_cast<>(&Point3d::roll, py::const_))
        .def("pitch", py::overload_cast<>(&Point3d::pitch, py::const_))
        .def("yaw", py::overload_cast<>(&Point3d::yaw, py::const_))
        // .def("")
        ;

    // Color
    typedef octomap::ColorOcTreeNode::Color node_color;
    py::class_<node_color>(m, "Color")
        .def(py::init<>())
        .def(py::init<uint8_t, uint8_t, uint8_t>())
        .def("__eq__", [](const node_color &c1, const node_color &c2)
             { return c1 == c2; })
        .def("__ne__", [](const node_color &c1, const node_color &c2)
             { return c1 != c2; })
        .def("__str__", [](const node_color &c){
        return "(" + std::to_string(c.r) + ", " + std::to_string(c.g) + ", " + std::to_string(c.b) + ")"; })
        .def_readwrite("r", &node_color::r)
        .def_readwrite("g", &node_color::g)
        .def_readwrite("b", &node_color::b);

    // OCTreeKey
    typedef octomap::OcTreeKey octree_key;
    py::class_<octree_key>(m, "OcTreeKey")
        .def(py::init<>())
        .def(py::init<octomap::key_type, octomap::key_type, octomap::key_type>())
        .def(py::init<const octree_key &>())
        .def("__eq__", [](const octree_key &k1, const octree_key &k2)
             { return k1 == k2; })
        .def("__ne__", [](const octree_key &k1, const octree_key &k2)
             { return k1 != k2; });
    // .def_readwrite("k",&octree_key::k);

    // leaf_iterator
    typedef octomap::ColorOcTree::leaf_iterator color_leaf_iterator;
    py::class_<color_leaf_iterator>(m, "leaf_iterator")
        .def(py::init<>())
        .def(py::init<const color_leaf_iterator &>())
        .def("get_coordinate", &color_leaf_iterator::getCoordinate)
        .def("get_x", &color_leaf_iterator::getX)
        .def("get_y", &color_leaf_iterator::getY)
        .def("get_z", &color_leaf_iterator::getZ)
        .def("get_size", &color_leaf_iterator::getSize)
        .def("get_depth", &color_leaf_iterator::getDepth)
        .def("get_key", &color_leaf_iterator::getKey)
        .def("get_index_key", &color_leaf_iterator::getIndexKey)
        .def("get_color", [](const color_leaf_iterator &it)
             { return it->getColor(); })
        .def("get_occupancy", [](const color_leaf_iterator &it)
             { return it->getOccupancy(); })
        .def("next", [](color_leaf_iterator &it)
             { return ++it; })
        .def("__eq__", [](const color_leaf_iterator &it1, const color_leaf_iterator &it2)
             { return it1 == it2; })
        .def("__ne__", [](const color_leaf_iterator &it1, const color_leaf_iterator &it2)
             { return it1 != it2; });

    // leaf_bbx_iterator
    typedef octomap::ColorOcTree::leaf_bbx_iterator color_leaf_bbx_iterator;
    py::class_<color_leaf_bbx_iterator>(m, "leaf_bbx_iterator")
        .def(py::init<>())
        .def(py::init<const color_leaf_bbx_iterator &>())
        .def("get_coordinate", &color_leaf_bbx_iterator::getCoordinate)
        .def("get_x", &color_leaf_bbx_iterator::getX)
        .def("get_y", &color_leaf_bbx_iterator::getY)
        .def("get_z", &color_leaf_bbx_iterator::getZ)
        .def("get_size", &color_leaf_bbx_iterator::getSize)
        .def("get_depth", &color_leaf_bbx_iterator::getDepth)
        .def("get_key", &color_leaf_bbx_iterator::getKey)
        .def("get_index_key", &color_leaf_bbx_iterator::getIndexKey)
        .def("get_color", [](const color_leaf_bbx_iterator &it)
             { return it->getColor(); })
        .def("get_occupancy", [](const color_leaf_bbx_iterator &it)
             { return it->getOccupancy(); })
        .def("next", [](color_leaf_bbx_iterator &it)
             { return ++it; })
        .def("__eq__", [](const color_leaf_bbx_iterator &it1, const color_leaf_bbx_iterator &it2)
             { return it1 == it2; })
        .def("__ne__", [](const color_leaf_bbx_iterator &it1, const color_leaf_bbx_iterator &it2)
             { return it1 != it2; });

    // OctomapMsg
    py::class_<OctomapMsg>(m, "OctomapMsg")
        .def(py::init<>())
        .def(py::init<std::string, double, std::vector<int8_t> &>())
        .def_readwrite("id", &OctomapMsg::id)
        .def_readwrite("resolution", &OctomapMsg::resolution)
        .def_readwrite("data", &OctomapMsg::data);

    // ColorOctree
    py::class_<ColorOctree>(m, "ColorOctree")
        .def(py::init<>())
        .def(py::init<OctomapMsg &>())
        .def("get_map_from_msg", &ColorOctree::getMapFromMsg)
        .def("get_msg_from_map", &ColorOctree::getMsgFromMap)
        .def("get_metric_max", &ColorOctree::getMetricMax)
        .def("get_metric_min", &ColorOctree::getMetricMin)
        .def("delete_node", &ColorOctree::deleteNode)
        .def("begin_leafs", &ColorOctree::begin_leafs)
        .def("end_leafs", &ColorOctree::end_leafs)
        .def("begin_leafs_bbx", &ColorOctree::begin_leafs_bbx)
        .def("end_leafs_bbx", &ColorOctree::end_leafs_bbx)
        .def("is_map_exist", &ColorOctree::isMapExist);

    // py::class_<leaf_iterator>(m, "leaf_iterator")
    //     .def(py::init<>())
    //     .def(py::init<leaf_iterator>())
    //     .def("get_x", &leaf_iterator::getX)
    //     .def("get_y", &leaf_iterator::getY)
    //     .def("get_z", &leaf_iterator::getZ)
    //     .def("next", &leaf_iterator::next)
    //     .def("__eq__", &leaf_iterator::equal)
    //     .def("__ne__", &leaf_iterator::notEqual);
}
    