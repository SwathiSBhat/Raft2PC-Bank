import constants
import threading
import random
import common_utils
from common_utils import Message
from time import sleep

class RaftConsensus:
    def __init__(self, pid, network_server_conn):
        self.pid = pid
        self.cluster = common_utils.get_cluster(pid)
        self.connected_servers = common_utils.get_servers_in_cluster(self.cluster)
        self.network_server_conn = network_server_conn
        self.quorum = (len(self.connected_servers) + 1) // 2 + 1
        # Start off as follower
        self.state = constants.RaftState.FOLLOWER
        self.term = 0
        self.voted_for = None
        self.log = []
        self.commit_index = 0
        self.next_index = {}
        self.last_log_index = 0
        self.last_log_term = 0
        # Initialize election timeout to some random value
        self.election_timeout = random.random(3.0, 5.0);
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()
        self.leader = None
        # Lock to ensure only one thread updates the logs and vote count
        self.lock = threading.Lock()
        # TODO - maintain a thread for state machine

    def reset_election_timer(self):
        self.election_timer.cancel()
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()

    def start_heartbeat_timer(self):
        threading.Thread(target=self.send_heartbeat).start()

    def send_heartbeat(self):
        '''
        Send heartbeat to all servers in a separate thread every 0.5 seconds
        if current state is leader
        '''
        while self.state == constants.RaftState.LEADER:
            for server in self.connected_servers:
                # TODO - Heartbeat is basically append_entries with empty log
                self.network_server_conn.sendall(Message(constants.MessageType.HEARTBEAT, server, self.term), "utf-8")
            sleep(0.5)

    def handle_message(self, msg):
        if msg["msg_type"] == constants.MessageType.VOTE_REQUEST:
            self.handle_vote_request(msg)
        elif msg["msg_type"] == constants.MessageType.VOTE_RESPONSE:
            self.handle_vote_response(msg)
        elif msg["msg_type"] == constants.MessageType.APPEND_ENTRIES:
            self.handle_append_entries(msg)
        elif msg["msg_type"] == constants.MessageType.APPEND_ENTRIES_RESPONSE:
            self.handle_append_entries_response(msg)
        elif msg["msg_type"] == constants.MessageType.HEARTBEAT:
            self.handle_heartbeat(msg)
        elif msg["msg_type"] == constants.MessageType.CLIENT_REQUEST:
            self.handle_client_request(msg)
        elif msg["msg_type"] == constants.MessageType.CLIENT_RESPONSE:
            self.handle_client_response(msg)

    def start_election(self):
        '''
        Start election process by incrementing term and voting for self
        Send vote request to all servers
        '''
        self.state = constants.RaftState.CANDIDATE
        self.term += 1
        self.voted_for = self.pid
        self.votes = 1;
        self.send_vote_request()
        self.reset_election_timer()


    def send_vote_request(self):
        for server in self.connected_servers:
            self.network_server_conn.sendall(Message(constants.MessageType.VOTE_REQUEST, self.term, self.pid, self.last_log_index, self.last_log_term, server), "utf-8")

    def handle_vote_request(self, msg):
        '''
        If term > currentTerm, currentTerm ← term (step down if leader or candidate)
        If term == currentTerm, votedFor is null or candidateId,
        and candidate's log is at least as complete as local log, grant vote and reset election timeout
        '''
        sender_server_id = msg["candidate_id"]

        if msg["term"] > self.term or \
        ((msg["term"] == self.term and (self.voted_for is None or self.voted_for == sender_server_id)) and \
         (msg["last_log_index"] >= self.last_log_index and msg["last_log_term"] >= self.last_log_term)):
            # vote for candidate
            self.state = constants.RaftState.FOLLOWER
            self.term = msg["term"]
            self.voted_for = sender_server_id
            self.leader = sender_server_id
            # reset election timer
            self.reset_election_timer()
            self.network_server_conn.sendall(Message(constants.MessageType.VOTE_RESPONSE, sender_server_id, self.term, vote=True), "utf-8")
        else:
            # Reject vote and send term in response so that the sender can update its term
            self.network_server_conn.sendall(Message(constants.MessageType.VOTE_RESPONSE, sender_server_id, self.term, vote=False), "utf-8")

    def handle_vote_response(self, msg):
        '''
        1. If votes received from majority of servers, become leader
        2. If term in response is greater, update term and step down as candidate
        '''
        if msg["vote"]:
            with self.lock:
                self.votes += 1
                if self.votes >= self.quorum:
                    # reset vote count to prevent other threads from updating it
                    self.votes = 0
                    self.state = constants.RaftState.LEADER
                    self.leader = self.pid
                    self.start_heartbeat_timer()
        else:
            # Update term if term in response is greater
            if msg["term"] > self.term:
                self.term = msg["term"]
                self.state = constants.RaftState.FOLLOWER
                self.voted_for = None
                self.leader = None
                self.reset_election_timer()

    def handle_heartbeat(self, msg):
        '''
        If heartbeat received from leader, reset election timer
        '''
        # TODO - Check conditions for valid heartbeat

    def handle_client_request(self, msg):
        '''
        If leader, append client request to log and send append entries to all servers
        Else, redirect client request to leader
        '''
        if self.state == constants.RaftState.LEADER:
            self.log.append(msg)
            self.send_append_entries(msg)
        else:
            self.network_server_conn.sendall(Message(constants.MessageType.CLIENT_REQUEST, self.leader), "utf-8")
        
    def send_append_entries(self, msg):
        '''
        Invoked by leader to replicate log entries and discover inconsistencies
        '''


    def handle_append_entries(self, msg):
        '''
        If leader's term < current term, reject append entries and send term in response
        If leader's term > current term, reset election timer, update term and step down to follower.
            Return failure if log doesn't contain an entry at prevLogIndex whose term matches prevLogTerm
            If an existing entry conflicts with a new one, delete the existing entry and all that follow it
            Append any new entries not already in the log
            Advance state machine by applying newly committed entries
        '''