'''
Create timer class that keeps track of heartbeat timer
and election timeout timer for each server. 
Each server has its own timer object which tracks the time.
'''

import threading

class RaftTimer:
    def __init__(self, election_timeout, heartbeat_timeout):
        self.timeout = election_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.election_timer = None
        self.heartbeat_timer = None

    def start_election(self):
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()

    def start_heartbeat(self):
        self.heartbeat_timer = threading.Timer(self.heartbeat_timeout, self.start_heartbeat)
        self.heartbeat_timer.start()

    def reset_election(self):
        self.election_timer.cancel()
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()

    def reset_heartbeat(self):
        self.heartbeat_timer.cancel()
        self.heartbeat_timer = threading.Timer(self.heartbeat_timeout, self.start_heartbeat)
        self.heartbeat_timer.start()
        
    def cancel_election(self):
        self.election_timer.cancel()
        self.election_timer = None

    def cancel_heartbeat(self):
        self.heartbeat_timer.cancel()
        self.heartbeat_timer = None