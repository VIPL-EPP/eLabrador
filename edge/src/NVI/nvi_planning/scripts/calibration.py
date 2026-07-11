from collections import deque
from global_planning.gnss_compute import get_p2pgeodesic
from global_planning.gps_transform import wgs842gcj02
from progress.bar import Bar
import rospy
import numpy as np
import message_filters
from nav_msgs.msg import Odometry
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Float32MultiArray

class GPSVIOCalibration:
    '''
    Calibrate the magnetometer direction bias by synchronized Magn-GPS-VIO.
    Algorithm:
        Step1: estimate the rigid transform matrix from GPS coordinate system to VIO coordinate system.
        Step2: transfrom the magnetometer orientation to VIO coordinate system by estimated matrix R.
        Step3: calculate the direction difference between magnetometer orientation and VIO orientation.
        Step4: set the average of the difference of a fixed window size as the calibration value: diretcion_bias.
    Note: The GPS coordinate system is aligned to magnetometer coordinate system when computing GPS coordinates. 
    '''
    def __init__(self,MIN_TRANSFORM_SIZE=16,MIN_DELTA_DISTANCE=1.5):
        self.MIN_TRANSFORM_SIZE = MIN_TRANSFORM_SIZE
        self.MIN_DELTA_DISTANCE = MIN_DELTA_DISTANCE
        self.vio_buffer = deque(maxlen=64)
        self.lla_buffer = deque(maxlen=64)
        self.init_gps_point = None
        self.R, self.T = None,None
        self.data_collection_bar = None
        self.lla_seq = -1

        self.lla_filter_sub = message_filters.Subscriber("/ublox_driver/receiver_lla", NavSatFix)
        self.vio_filter_sub = message_filters.Subscriber("/vins_estimator/odometry", Odometry)
        self.sync_gps_vio = message_filters.ApproximateTimeSynchronizer([self.lla_filter_sub,self.vio_filter_sub], 512, 0.1)
        self.sync_gps_vio.registerCallback(self.sync_gps_vio_callback)
        rospy.loginfo('Calibration node started.')
        self.calibration_pub = rospy.Publisher("/gps_vio_calib", Float32MultiArray, queue_size=1)
        self.init_gps_pub = rospy.Publisher("/gps_vio_init_lla",NavSatFix,queue_size=1,latch=True)
        self.init_gps_sent = False

    def sync_gps_vio_callback(self,gps_msg,vio_msg):
        if abs(gps_msg.header.seq - self.lla_seq) > 100:
            self.reset()
            rospy.logwarn("lla message discontinue, reset the global planner.")
        self.lla_seq = gps_msg.header.seq
        gcj_loc = {
            'lat': gps_msg.latitude,
            'lon': gps_msg.longitude
        }
        now_point = (gcj_loc['lat'], gcj_loc['lon'])
        vio_point = (vio_msg.pose.pose.position.x,vio_msg.pose.pose.position.y)
        if not self.append_gps_vio_point(now_point,vio_point):
            return
        
        if len(self.vio_buffer) > self.MIN_TRANSFORM_SIZE:
            self.R, self.T = self.estimate_rigid_transform(self.lla_buffer, self.vio_buffer)
            msg = Float32MultiArray(data=self.R.reshape(-1).tolist()+self.T.tolist())
            self.calibration_pub.publish(msg)

    def append_gps_vio_point(self,gps_point,vio_point):
        '''
        gps_point: (x, y)
        vio_point: (x, y)
        return True when the point pair is accepted.
        '''
        if self.init_gps_point is None:
            self.init_gps_point = gps_point
            self.last_gps_point = gps_point
            self.last_vio_point = vio_point
            self.lla_buffer.append([0,0])
            self.data_collection_bar = Bar('Global-Local calibration', max=self.MIN_TRANSFORM_SIZE)
            if not self.init_gps_sent:
                init_msg = NavSatFix()
                init_msg.header.stamp = rospy.Time.now()
                init_msg.header.frame_id = 'gps'
                init_msg.latitude = float(gps_point[0])
                init_msg.longitude = float(gps_point[1])
                init_msg.altitude = 0.0
                # init_msg.status = 0
                # init_msg.status.service = 1
                self.init_gps_pub.publish(init_msg)
                self.init_gps_sent = True
        else:
            distance = np.linalg.norm(np.array(vio_point)-np.array(self.last_vio_point))
            if distance < self.MIN_DELTA_DISTANCE:
                return False
            self.last_gps_point = gps_point
            self.last_vio_point = vio_point
            distance, azimuth=get_p2pgeodesic(self.init_gps_point,gps_point)
            azimuth = - np.deg2rad(azimuth)
            self.lla_buffer.append([distance*np.cos(azimuth),distance*np.sin(azimuth)])
        self.vio_buffer.append([vio_point[0],vio_point[1]])
        if self.data_collection_bar.index == self.MIN_TRANSFORM_SIZE:
            # self.data_collection_bar.finish()
            pass
        else:
            self.data_collection_bar.next()
        return True

    @staticmethod
    def estimate_rigid_transform(src, tgt):
        '''
        estimate rigid transform from GPS coordinate system to VIO coordinate system.
        return True when estimate sucessfully.
        '''
        assert len(src)==len(tgt), "Input src dimension %d is not matched with tgt dimension %d"%(len(src),len(tgt))
        src,tgt = np.array(src),np.array(tgt)
        centroid_src,centoid_tgt = np.mean(src,axis=0),np.mean(tgt,axis=0)
        normal_src,normal_tgt = src -centroid_src, tgt-centoid_tgt
        # H = np.matmul(np.transpose(normal_src),normal_tgt)
        # U,S,Vt = np.linalg.svd(H)
        # R = np.matmul(Vt.T,U.T)
        # The following seven lines replace the original three-line implementation.
        H = np.matmul(np.transpose(normal_src), normal_tgt)
        U, S, Vt = np.linalg.svd(H)
        # Ensure a proper rotation (det(R)=+1). If det<0, correct the last singular vector.
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = Vt.T @ U.T
            
        T = -np.matmul(R, centroid_src) + centoid_tgt
        return R, T

    def reset(self):
        self.vio_buffer.clear() 
        self.lla_buffer.clear()
        self.init_gps_point = None
        self.R, self.T = None,None
        self.data_collection_bar = None
        self.init_gps_sent = False

if __name__ == "__main__":
    rospy.init_node("nvi_calibration", anonymous=True)
    calibration = GPSVIOCalibration()
    rospy.spin()