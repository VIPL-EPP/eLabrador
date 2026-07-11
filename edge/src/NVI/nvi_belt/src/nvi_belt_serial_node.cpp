#include <ros/ros.h>
#include <serial/serial.h>
#include <iostream>
#include <string>
#include <queue>
#include "std_msgs/String.h"

class NVISerial{
public:
    NVISerial(ros::NodeHandle &nh);
    ~NVISerial();

    void blCallback(const std_msgs::String::ConstPtr &msg);
    void spin();
    static void clear_queue(std::queue<std::string> &q);
    ros::NodeHandle serialHandle;
    ros::Subscriber sub;

    serial::Serial serialPort;

    std::queue<std::string> cmd_buffer;

    int baudrate = 9600;
    std::string port = "dev";
};


NVISerial::NVISerial(ros::NodeHandle &nh){
    serialHandle = nh;
    sub = serialHandle.subscribe("/nvi_belt/serial", 20, &NVISerial::blCallback, this);
    
    serial::Timeout to = serial::Timeout::simpleTimeout(100);

    serialHandle.getParam("/belt_serial/serialPort", port);
    serialHandle.getParam("/belt_serial/serialBaudrate", baudrate);
    std::cout << port << std::endl;
    serialPort.setPort(port);
    serialPort.setBaudrate(baudrate);
    serialPort.setTimeout(to);

    try
    {
        serialPort.open();
    }
    catch (serial::IOException &e)
    {
        ROS_ERROR_STREAM("Unable to open port " << port << ".");
        exit;
    }

    if (serialPort.isOpen())
    {
        ROS_INFO_STREAM(port<<" is opened.");
    }
    else
    {
        exit;
    }
}

NVISerial::~NVISerial(){
    serialPort.close();
}

void NVISerial::spin()
{
    ros::Rate loop_rate(1);
    int count = 0;
    while (ros::ok())
    {
        if (!cmd_buffer.empty()){
            std::string cmd = cmd_buffer.back();
            clear_queue(cmd_buffer);
            uint8_t buffer[10];
            uint8_t mode = cmd[0];
            uint8_t pos = cmd[1];
            uint8_t degree = cmd[2];
            buffer[0] = '$';
            buffer[1] = mode;
            buffer[2] = pos;
            buffer[3] = degree;
            serialPort.write(buffer, 4);

        }
        ros::spinOnce();
        loop_rate.sleep();
    }
}

void NVISerial::clear_queue(std::queue<std::string> &q){
    std::queue<std::string> empty;
    swap(empty, q);
}

void NVISerial::blCallback(const std_msgs::String::ConstPtr &msg)
{
    ROS_INFO("I heard: [%s]", msg->data.c_str());

    cmd_buffer.push(std::string(msg->data.c_str()));
    if(cmd_buffer.size() >20){  // max size 20
        cmd_buffer.pop();
    }
    // std::cout << cmd_buffer.back() << std::endl;


    // uint8_t buffer[10];
    // uint8_t mode = msg->data[0];
    // uint8_t pos = msg->data[1];
    // uint8_t degree = msg->data[2];
    // buffer[0] = '$';
    // buffer[1] = mode;
    // buffer[2] = pos;
    // buffer[3] = degree;

    // serialPort.write(buffer, 4);
}

int main(int argc, char **argv)
{
    ros::init(argc, argv, "nvi_seria");
    ros::NodeHandle nh;
    NVISerial nviSerial(nh);
    nviSerial.spin();

    return 0;
}