import numpy as np
# from map_api import beginEnd2waypoints
from  .map_api  import *
from .gnss_compute import get_p2pdistance,get_p2ldistance,get_p2pazimuth,get_p2pgeodesic
from .tools import AsyncRate
from collections import deque
import time
from functools import reduce

class GlobalPlanner:
    '''
    class for global planning

    all points are based on gcj UCS with format (latitude,longitude).
    
    stauts: -1: None, >1: road 

    '''
    def __init__(self,start_point,end_point,preset_way=None):
        self.set_planner(start_point, end_point, preset_way=preset_way)
        self.action_set = ['直行','左转','右转','向后转']
        self.deviate_zh = '偏离'
        self.direction_zh = '方'
        self.ready_zh = '准备前方'
        self.current_zh = '当前'
        self.instruction_zh = '沿{}向{}步行{}米{}'
        self.DELTA_TIME = 5
        # self.TURN_DIS = 20
        self.TURN_DIS = 30
        # When the pedestrian gets close enough to the next road raw_polyline,
        # treat that next road as effectively reached. The unit is meters.
        self.NEXT_ROAD_NEAR = 10.0
        # Blend the target heading toward the next road before the intersection.
        self.TURN_BLEND_START = 25.0   # Start blending while still 25 m from the turn.
        self.TURN_BLEND_END   = 10.0   # Fully align with the next road within 10 m.
        self.RESET_DIS = 25
        # --- Replan debounce / cooldown ---
        self.REPLAN_COUNT_TH = 5      # Require N consecutive frames beyond RESET_DIS before replanning.
        self.REPLAN_COOLDOWN_SEC = 10 # Minimum interval between two replans, in seconds.
        # --- sub_status cost  + continuity window  ---
        self.SUB_LAMBDA_AZ = 0.5   # weight for azimuth penalty (meters per degree)
        self.SUB_WIN_BACK = 2      # allow looking back this many indices
        self.SUB_WIN_FWD = 6       # allow looking forward this many indices

        self.POINT_BUFFER_SIZE = 100
        self.DIRECTION_EST_SIZE = int(self.POINT_BUFFER_SIZE / 10) + 2
        self.DESTINATION_DIS = 5
        self.aduio_feedback_reset_rate = AsyncRate(1/120)

    def set_planner(self,start_point,end_point,preset_way=None):
        # APIs require 6 decimal float 
        self.start_point = (round(start_point[0],6),round(start_point[1],6)) 
        self.end_point = (round(end_point[0],6),round(end_point[1],6))
        self.status = -1
        self.sub_status = -1
        self.sub_status_switch = False
        self.is_switch = False
        self.is_turn = False
        self.is_last_turn = False
        self.road_num = 0
        
        # Status hysteresis state.
        self._status_cand = -1 
        self._status_cand_cnt = 0
        # --- Replan debounce state ---
        self._replan_over_cnt = 0
        self._last_replan_time = 0.0

        self.point_buffer = deque([])
        self.direction = None
        self.direction_variance = 1e4 
        self.cmd_buffer = {'cmd':'','time':time.perf_counter()}
        self.is_set = False
        if get_p2pdistance(self.start_point,self.end_point) > 5000:
            print('The destination is too far, please reset.')
            return
        if preset_way is not None:
            self.roads = preset_way
        else:
            print('The start point is:')
            print(self.start_point)
            print('The end point is:')
            print(self.end_point)
            self.roads = beginEnd2waypoints(self.start_point,self.end_point)
        print('The planning path is:')
        print(self.roads)
        for road in self.roads:
            road_points = []
            road_azimuth = []
            road_length = []
            points= road['polyline'].split(';')
            points =  reduce(lambda x,y:x if y in x else x + [y], [[], ] + points)
            raw_polyline = []
            for p in points:
                lon, lat = p.split(',')
                raw_polyline.append((float(lat), float(lon)))

            road["raw_polyline"] = raw_polyline
            for i in range(0,len(points)-1):
                point = points[i]
                lon, lat = point.split(',')
                road_points.append((float(lat),float(lon)))
                point = points[i+1]
                lon, lat = point.split(',')
                road_points.append((float(lat), float(lon)))
                road_azimuth.append(get_p2pazimuth(road_points[-2],road_points[-1]))
                road_length.append(get_p2pdistance(road_points[-2], road_points[-1]))
                road['polyline'] = road_points[1::2]
                road['polyazimuth'] = road_azimuth
                road['polylength'] = road_length
                road['abstract_line'] = [road_points[0],road_points[-1]]
                road['azimuth'] = get_p2pazimuth(road_points[0],road_points[-1])
            self.road_num +=1
        self.is_road_instruction_feedback = np.zeros((self.road_num,2),dtype=bool)
        self.is_set = True
        print("********find roads!!**********")
        print(self.roads)

    def update(self,now_point):
        '''
        return the global planning code
        '''
        # self.update_direction(now_point)
        self.update_status(now_point)
        if hasattr(self,'init_point'):
            if get_p2pdistance(self.last_point,now_point)>10:
                self.init_point = now_point
                self.last_point = now_point
                self.path = []
                self.path.append((0,0))
            else: 
                # Convert the current latitude/longitude to planar coordinates with
                # respect to the initialization point, then append it to the path.
                self.last_point = now_point
                distance, azimuth=get_p2pgeodesic(self.init_point,now_point)
                azimuth = - np.deg2rad(azimuth)
                # self.path stores a 2D trajectory in meters with init_point as the origin.
                self.path.append((distance*np.cos(azimuth),distance*np.sin(azimuth)))
        else:
            self.init_point = now_point
            self.last_point = now_point
            self.path = []
            self.path.append((0,0))
        # cmd = self.get_cmd()
        # if cmd == self.cmd_buffer['cmd']:
        #     if time.perf_counter() - self.cmd_buffer['time'] < self.DELTA_TIME:
        #         self.cmd_buffer['time'] = time.perf_counter()
        #         cmd = None
        # else:
        #     self.cmd_buffer['cmd'] = cmd 
        #     self.cmd_buffer['time'] = time.perf_counter()
        # if cmd == 'G||':
        #     cmd = None
        # return 

    '''
    update direction by diff
    '''    
    # def update_direction(self,now_point):
    #     self.point_buffer.append(now_point)
    #     if len(self.point_buffer) > self.POINT_BUFFER_SIZE:
    #         self.point_buffer.popleft()
    #     if len(self.point_buffer) >= self.DIRECTION_EST_SIZE:
    #         self.direction =  get_p2pazimuth(self.point_buffer[0],self.point_buffer[-1])
    #         self.direction_variance = 1/get_p2pdistance(self.point_buffer[0],self.point_buffer[-1])
    
    '''
    update direction by mag/imu input
    '''
    def update_direction(self,direction):
        self.direction= direction
        self.direction_variance = 1e-4

    def _point_to_segment_distance_latlon(self, p, a, b):
        """Approximate point-to-segment distance in lat/lon with a local Euclidean projection."""
        px, py = p  # (lat, lon)
        ax, ay = a
        bx, by = b

        apx, apy = px - ax, py - ay
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        if ab2 < 1e-12:
            return np.hypot(apx, apy)

        t = (apx * abx + apy * aby) / ab2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0

        projx = ax + t * abx
        projy = ay + t * aby
        return np.hypot(px - projx, py - projy)

    def _point_to_raw_polyline_min_dist(self, now_point, raw_polyline):
        """Return the minimum distance from now_point to a raw polyline."""
        if raw_polyline is None or len(raw_polyline) == 0:
            return 1e9
        if len(raw_polyline) == 1:
            return get_p2pdistance(now_point, raw_polyline[0])

        dmin = 1e9
        for i in range(len(raw_polyline) - 1):
            d = self._point_to_segment_distance_latlon(
                now_point, raw_polyline[i], raw_polyline[i + 1]
            )
            if d < dmin:
                dmin = d
        return dmin

    def update_status(self,now_point):
        p2ldis=[]
        for road in self.roads:
            p2ldis.append(get_p2ldistance(now_point,road['abstract_line']))
        # min_idx = np.argmin(p2ldis)
        
        # Lightweight status update: only compare against the current road and the next road.
        if self.status < 0:
            new_idx = int(np.argmin(p2ldis))
        else:
            cand_idx = [self.status]
            if self.status + 1 < self.road_num:
                cand_idx.append(self.status + 1)

            cand_d = []
            for idx in cand_idx:
                raw_poly = self.roads[idx].get("raw_polyline", [])
                cand_d.append(self._point_to_raw_polyline_min_dist(now_point, raw_poly))

            new_idx = cand_idx[int(np.argmin(cand_d))]

        # Hysteresis: require three consecutive frames before switching status.
        if new_idx != self.status:
            if new_idx == self._status_cand:
                self._status_cand_cnt += 1
            else:
                self._status_cand = new_idx
                self._status_cand_cnt = 1

            if self._status_cand_cnt >= 3:
                min_idx = new_idx
            else:
                min_idx = self.status
        else:
            self._status_cand = self.status
            self._status_cand_cnt = 0
            min_idx = self.status

        min_idx = int(min_idx)  # Defensive cast.

        is_turn_tmp = False
        if  get_p2pdistance(now_point,self.roads[min_idx]['abstract_line'][-1])<self.TURN_DIS: # turn judge 
            is_turn_tmp = min_idx + 1 < self.road_num
            self.is_last_turn = min_idx + 1 == self.road_num                    
        if min_idx != self.status or is_turn_tmp != self.is_turn:
            self.is_switch = True
        self.status = min_idx
        self.is_turn = is_turn_tmp
        # print('debug',min_idx,self.is_turn,get_p2pdistance(now_point,self.roads[min_idx]['abstract_line'][-1]))
        if not self.is_turn:
            # if p2ldis[min_idx] > self.RESET_DIS:
            #     self.set_planner(now_point,self.end_point)
            # Do not replan on one or two noisy frames; replan only after sustained deviation,
            # and keep a cooldown to avoid repeatedly calling the API.
            if p2ldis[min_idx] > self.RESET_DIS:
                self._replan_over_cnt += 1
            else:
                self._replan_over_cnt = 0

            if self._replan_over_cnt >= self.REPLAN_COUNT_TH:
                now_t = time.perf_counter()
                if now_t - self._last_replan_time > self.REPLAN_COOLDOWN_SEC:
                    try:
                        self.set_planner(now_point, self.end_point)
                    except Exception as e:
                        print(f"[WARN] set_planner failed during replan: {e}")
                    self._last_replan_time = now_t
                self._replan_over_cnt = 0
            else:
                # l2lazimuth = []
                # road = self.roads[min_idx]
                # # print(min_idx,road)
                # for i in range(len(road['polyline'])):
                #     # azimuth = get_p2pazimuth(now_point, road['polyline'][i])
                #     p2p_length, p2p_azimuth = get_p2pgeodesic(now_point, road['polyline'][i])
                #     dazimuth = abs(self.get_dazimuth(road['polyazimuth'][i],p2p_azimuth))
                #     # print(dazimuth,p2p_length)
                #     if dazimuth >= 90:
                #         l2lazimuth.append(0)
                #     else:
                #         l2lazimuth.append(dazimuth/p2p_length)
                # # print(l2lazimuth)
                # sub_status_now = np.argmax(l2lazimuth)
                """
                Parameter tuning hints:
                - If the index still jumps backward occasionally, reduce SUB_WIN_BACK (for example to 1).
                - If the pedestrian moves quickly and the window cannot keep up, increase SUB_WIN_FWD (for example to 8-10).
                - If the azimuth term is too strong and blocks a reasonable nearby point, reduce SUB_LAMBDA_AZ (for example to 0.2-0.4).
                - If parallel roads or forks are often confused, increase SUB_LAMBDA_AZ (for example to 0.8-1.2).
                """
                road = self.roads[min_idx]
                poly = road.get('polyline', [])
                n_poly = len(poly)
                if n_poly == 0:
                    return

                # Search only within a window around the previous sub_status.
                if self.sub_status < 0 or self.sub_status >= n_poly:
                    i_min, i_max = 0, n_poly - 1
                else:
                    i_min = max(0, self.sub_status - self.SUB_WIN_BACK)
                    i_max = min(n_poly - 1, self.sub_status + self.SUB_WIN_FWD)

                costs = []
                idxs = []
                for i in range(i_min, i_max + 1):
                    p2p_length, p2p_azimuth = get_p2pgeodesic(now_point, poly[i])
                    road_az = road['polyazimuth'][min(i, len(road['polyazimuth']) - 1)]
                    dazimuth = abs(self.get_dazimuth(road_az, p2p_azimuth))
                    if dazimuth >= 90:
                        cost = 1e9
                    else:
                        # cost = distance + lambda * azimuth error, with distance as the dominant term.
                        cost = p2p_length + self.SUB_LAMBDA_AZ * dazimuth
                    costs.append(cost)
                    idxs.append(i)

                sub_status_now = idxs[int(np.argmin(costs))]
                if sub_status_now != self.sub_status:
                    self.sub_status = sub_status_now
                    self.sub_status_switch =True
                # else:
                #     self.sub_status_switch =False

    def get_geodesic(self,point1,point2):
        '''
        return the distance between p1 and p2 and the azimuth angle of point2 relative to point1
        '''
        return get_p2pgeodesic(point1,point2)

    def is_arrived(self,now_point):
        distance = get_p2pdistance(now_point,self.end_point)
        return distance < self.DESTINATION_DIS, distance
        # if get_p2pdistance(now_point,self.end_point) <self.DESTINATION_DIS:
        #     return True
        # return False

    def get_audio_feedback(self):
        if self.aduio_feedback_reset_rate.sleep():
            self.reset_audio_feedback()
        feedback = None
        if (self.is_turn or self.is_last_turn) and not self.is_road_instruction_feedback[self.status][1]:
            feedback = self.ready_zh
            action, assistant_action = self.roads[self.status]['action'], self.roads[self.status]['assistant_action']
            feedback += action if self.is_turn and action else assistant_action
            self.is_road_instruction_feedback[self.status][1] = True
        elif not self.is_road_instruction_feedback[self.status][0]:
            feedback = self.current_zh
            action, assistant_action = self.roads[self.status]['action'], self.roads[self.status]['assistant_action']
            distance = sum(self.roads[self.status]['polylength'][self.sub_status:])
            feedback += self.instruction_zh.format(self.roads[self.status]['road'],self.roads[self.status]['orientation'],int(distance),action if action else assistant_action)
            # feedback += self.roads[self.status]['instruction']
            self.is_road_instruction_feedback[self.status][0] = True
        if feedback is not None:
            self.aduio_feedback_reset_rate.reset()
        return feedback
    
    def reset_audio_feedback(self):
        '''
        reset the audio feedback status
        '''
        self.is_road_instruction_feedback = np.zeros((self.road_num,2),dtype=bool)

    def get_cmd(self):
        _mode = 'G'
        _action = '|'
        _description = '|'
        if self.is_switch:
            self.is_switch = False
            _description += self.get_instruction()
        else:
            if self.status >= 0 and  not self.is_turn and self.direction is not None:
                dazimuth = self.get_dazimuth(self.roads[self.status]['azimuth'],self.direction)
                if abs(dazimuth) >45:
                    # _mode = 'M'
                    _description += self.deviate_zh+self.roads[self.status]['orientation']+self.direction_zh
                    if abs(dazimuth) > 135:
                        _action += self.action_set[3]
                    else:
                        if dazimuth >0:
                            _action += self.action_set[1]
                        else:
                            _action += self.action_set[2]
            elif self.is_turn:
                _action += self.ready_zh
                _action += self.get_instruction()
        
        return _mode+_action+_description

    def get_instruction(self):
        if self.status != -1:
            if self.is_turn>0:
                action_ = self.roads[self.status]['action']
                if len(action_)>0:
                    return self.roads[self.status]['action']
                else:
                    return self.roads[self.status]['assistant_action']
            else:
                return self.roads[self.status]['instruction']
        else:
            return ''
    
    def get_status(self):
        if self.status >= 0:    
            # return self.roads['road']
            return self.roads[self.status]['road']
        return '' 

    @staticmethod
    def get_dazimuth(degree1,degree2):
        '''
        return the delta azimuth of the line at degree1
        '''
        dazimuth = degree2 - degree1
        if dazimuth > 180:
            return dazimuth -360
        elif dazimuth < -180:
            return dazimuth +360
        return dazimuth
    
    def get_target_azimuth(self, now_point):
        """
        Compute the global target azimuth.

        The current implementation uses the road-network polyline rather than
        the live GPS point as the azimuth baseline:

        1. Pick the current sub-segment start point on the active road.
        2. In normal line-following mode, point toward the current segment end.
        3. During a turn, smoothly blend from the current-road heading to the
           next-road heading as the pedestrian approaches the intersection.
        4. Normalize the final azimuth to the (-180, 180] range.

        now_point is only used to measure how far the pedestrian is from the
        turn pivot; it is not used as the azimuth origin itself.
        """
        status, sub_status = self.status, self.sub_status
        if status < 0:
            raise ValueError("Not defined next waypoint")

        # 1. Current road and the corresponding polyline start point.
        road = self.roads[status]
        sub_road_num = len(road['polyline'])
        if sub_road_num == 0:
            raise ValueError("Current road has no polyline points")
        cur_idx = min(max(sub_status, 0), sub_road_num - 1)
        # sub_status points to the current segment end; outside turns the active segment is (cur_idx-1 -> cur_idx).
        if cur_idx > 0:
            origin_point = road['polyline'][cur_idx - 1]
            cur_end_point = road['polyline'][cur_idx]
        else:
            origin_point = road['polyline'][cur_idx]
            cur_end_point = road['polyline'][min(cur_idx + 1, sub_road_num - 1)]

        # 2. During turns, keep the current-road start point and aim toward a look-ahead point on the next road.
        if self.is_turn and status < len(self.roads) - 1:
            next_road = self.roads[status + 1]
            next_num = len(next_road['polyline'])
            if next_num == 0:
                raise ValueError("Next road has no polyline points")
            # Prefer index 2 as the next-road look-ahead point; fall back to 1 or 0 when needed.
            if next_num == 1:
                lookahead_idx = 0
            elif next_num == 2:
                lookahead_idx = 1
            else:
                lookahead_idx = min(2, next_num - 1)
            next_dest_point = next_road['polyline'][lookahead_idx]
            # Current-road heading az_cur measured from origin_point.
            _, az_cur = get_p2pgeodesic(origin_point, cur_end_point)
            # Next-road heading az_next.
            # _, az_next = get_p2pgeodesic(origin_point, next_dest_point)

            # Blend the current-road heading with the first heading segment on the next road for smoother turns.
            # Use polyline[0] -> polyline[1] when available; otherwise fall back to the overall abstract_line direction.
            if next_num >= 2:
                seg_p0 = next_road['polyline'][0]
                seg_p1 = next_road['polyline'][1]
            else:
                seg_p0, seg_p1 = next_road['abstract_line'][0], next_road['abstract_line'][-1]
            _, az_next = get_p2pgeodesic(seg_p0, seg_p1)

            # Distance to the turn pivot.
            turn_pivot = road['abstract_line'][-1]  # Use the current road endpoint as the intersection pivot.
            d_turn = get_p2pdistance(now_point, turn_pivot)

            if d_turn >= self.TURN_BLEND_START:
                # Still far from the turn: keep following the current-road heading.
                dest_point = cur_end_point

            elif d_turn <= self.TURN_BLEND_END:
                # Very close to the intersection: fully switch to the next-road heading.
                # Return az_next directly so the result matches the end of the blending interval.
                az_full_next = (az_next + 180) % 360 - 180
                return az_full_next

            else:
                # Inside the turn-transition zone: interpolate between az_cur and az_next.
                # alpha moves from 0 to 1 as distance shrinks from START to END.
                alpha = (self.TURN_BLEND_START - d_turn) / (self.TURN_BLEND_START - self.TURN_BLEND_END)
                alpha = max(0.0, min(1.0, alpha))

                # Use get_dazimuth to follow the shortest angular difference and avoid wraparound artifacts.
                delta = self.get_dazimuth(az_cur, az_next)
                blended_az = az_cur + alpha * delta
                blended_az = (blended_az + 180) % 360 - 180

                # Return the blended azimuth directly instead of using the fallback origin->dest_point logic below.
                return blended_az

        else:
            # 3. Normal case: follow the currently active segment.
            dest_point = cur_end_point

        # 4. Compute the azimuth from the segment start point to the chosen destination point.
        _, target_azimuth = get_p2pgeodesic(origin_point, dest_point)
        # Defensive fallback: if duplicate points collapse the segment, use the overall road azimuth.
        if get_p2pdistance(origin_point, dest_point) < 1e-3:
            target_azimuth = road.get('azimuth', 0.0)
        # 5. Normalize the angle to (-180, 180].
        target_azimuth = (target_azimuth + 180) % 360 - 180
        return target_azimuth

