import time

class AsyncRate:
    def __init__(self,rate) -> None:
        self.rate = rate
        self.delta_time = 1.0 / self.rate
        self.sync_time = time.perf_counter()
    
    def sleep(self):
        time_now = time.perf_counter()
        if time_now - self.sync_time >self.delta_time:
            self.sync_time = time_now
            return True
        return False
    
    def reset(self):
        self.sync_time = time.perf_counter()