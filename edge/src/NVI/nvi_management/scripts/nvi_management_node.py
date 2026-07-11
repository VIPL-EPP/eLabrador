#!/usr/bin/env python3

from management_pkg import main
import rospy


if __name__ == '__main__':
    rospy.init_node('nvi_management', anonymous=True)
    main()
