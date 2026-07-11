#!/usr/bin/env python3
import json
import math
import socket

import rospy
from nvi_msgs.msg import HeaderFloat32


def _to_float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_from_orientation_value(value):
    scalar = _to_float(value)
    if scalar is not None:
        return scalar

    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return _to_float(value[0])

    if isinstance(value, dict):
        for key in ("yaw", "azimuth", "heading", "alpha", "z", "x"):
            if key in value:
                scalar = _to_float(value[key])
                if scalar is not None:
                    return scalar
                nested = _extract_from_orientation_value(value[key])
                if nested is not None:
                    return nested
    return None


def extract_yaw(payload):
    if payload is None:
        return None, None

    if not isinstance(payload, dict):
        return _extract_from_orientation_value(payload), None

    timestamp = payload.get("timestamp")
    values = payload.get("values")
    sensor_type = payload.get("type")

    if "orientation" in sensor_type:
        yaw = _extract_from_orientation_value(values)
        if yaw is not None:
            return yaw, timestamp

    return None, None


class MobileOrientationReceiver:
    def __init__(self):
        rospy.init_node("mobile_orientation_receiver", anonymous=True)
        self.bind_ip = rospy.get_param("~bind_ip", "0.0.0.0")
        self.udp_port = int(rospy.get_param("~udp_port", 8080))
        self.buffer_size = int(rospy.get_param("~buffer_size", 4096))
        self.allowed_sender_ip = rospy.get_param("~allowed_sender_ip", "")
        self.input_in_degrees = bool(rospy.get_param("~input_in_degrees", True))
        self.yaw_offset_deg = float(rospy.get_param("~yaw_offset_deg", 0.0))
        self.out_topic = rospy.get_param("~out_topic", "/mobile/orientation")
        self.socket_timeout = float(rospy.get_param("~socket_timeout", 0.2))

        self.yaw_offset_rad = math.radians(self.yaw_offset_deg)
        self.orientation_pub = rospy.Publisher(self.out_topic, HeaderFloat32, queue_size=20)
        self.sock = None

    def init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.bind_ip, self.udp_port))
        self.sock.settimeout(self.socket_timeout)
        rospy.loginfo(
            "Mobile orientation UDP listener started on %s:%d (allowed_sender_ip=%s)",
            self.bind_ip,
            self.udp_port,
            self.allowed_sender_ip if self.allowed_sender_ip else "ANY",
        )

    @staticmethod
    def normalize_angle_rad(angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    def convert_yaw_to_rad(self, raw_yaw):
        yaw = float(raw_yaw)
        
        if self.input_in_degrees:
            yaw = math.radians(yaw)
        
        yaw += self.yaw_offset_rad
        
        # Normalize the final heading to the [-180, 180] degree range.
        yaw_deg = math.degrees(yaw)
        # yaw_deg = (yaw_deg + 180) % 360 - 180
        return yaw_deg

    def publish_yaw(self, yaw_rad, timestamp, sender_ip):
        msg = HeaderFloat32()
        
        secs = timestamp // 1000000000  # Convert nanoseconds to the integer seconds part.
        nsecs = timestamp % 1000000000  # Keep the remaining nanoseconds part.
        # msg.header.stamp = rospy.Time(secs, nsecs)  # Assign the exact sensor timestamp if needed.
        msg.header.stamp = rospy.Time.now()  # Use the local receipt time as the ROS timestamp.
        msg.header.frame_id = sender_ip
        msg.data = float(yaw_rad)
        self.orientation_pub.publish(msg)
        # print(f"------------{msg}-----------")


    def spin(self):
        self.init_socket()
        while not rospy.is_shutdown():
            try:
                data, addr = self.sock.recvfrom(self.buffer_size)
            except socket.timeout:
                continue
            except OSError:
                break

            sender_ip = addr[0]
            if self.allowed_sender_ip and sender_ip != self.allowed_sender_ip:
                continue

            raw = data.decode("utf-8", errors="ignore").strip()
            if not raw:
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                rospy.logwarn_throttle(5.0, "Mobile orientation: non-JSON UDP packet ignored.")
                continue

            yaw, timestamp = extract_yaw(payload)

            if yaw is None:
                rospy.logwarn_throttle(5.0, "Mobile orientation: no orientation field found in packet.")
                continue

            try:
                yaw_rad = self.convert_yaw_to_rad(yaw)   # Return a heading in degrees within [-180, 180], with north as 0 and clockwise positive.

            except Exception:
                rospy.logwarn_throttle(5.0, "Mobile orientation: invalid yaw value.")
                continue

            self.publish_yaw(yaw_rad, timestamp, sender_ip)

    def shutdown(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


if __name__ == "__main__":
    node = MobileOrientationReceiver()
    rospy.on_shutdown(node.shutdown)
    node.spin()
