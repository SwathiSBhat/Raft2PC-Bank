import constants
import threading
import random
import common_utils
from common_utils import Message, send_msg
from time import sleep
import config

class RaftConsensus:
    def __init__(self, pid, network_server_conn):
        self.pid = int(pid)
        self.cluster = common_utils.get_cluster(self.pid)
        self.connected_servers = common_utils.get_servers_in_cluster(self.cluster, pid)
        print(f"Connected servers: {self.connected_servers}")
        self.network_server_conn = network_server_conn
        self.quorum = (len(self.connected_servers) + 1) // 2 + 1
        # Start off as follower
        self.state = constants.RaftState.FOLLOWER
        self.term = 0
        self.leader = None
        self.voted_for = None
        self.votes = 0
        self.log = []
        self.commit_index = 0
        self.next_index = {}
        self.last_log_index = 0
        self.last_log_term = 0
        
        # Initialize election timeout to some random value
        self.election_timeout = random.uniform(3.0, 5.0);
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()
        
        # Lock to ensure only one thread updates the logs and vote count
        self.lock = threading.Lock()
        # TODO - maintain a thread for state machine

        self.write_to_disk()

    def write_to_disk(self):
        '''
        Write current term, votedFor, log to disk
        '''
        filename = f'{config.FILEPATH}/server_{self.pid}.txt'
        with open(filename, 'w+') as f:
            f.write(f'{self.term}\n')
            f.write(f'{self.voted_for}\n')
            f.write(f'{self.log}\n')

    def reset_election_timer(self):
        self.election_timer.cancel()
        self.election_timer = threading.Timer(self.election_timeout, self.start_election)
        self.election_timer.start()
    
    def cancel_election_timer(self):
        self.election_timer.cancel()

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
                msg = Message(constants.MessageType.HEARTBEAT, server, self.term).get_message()
                send_msg(self.network_server_conn, msg)
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
        # If current state is leader, don't start election
        # TODO - Make sure this doesn't cause problems
        if self.state == constants.RaftState.LEADER:
            return
        self.state = constants.RaftState.CANDIDATE
        self.term += 1
        self.voted_for = self.pid
        self.votes = 1;
        self.send_vote_request()
        self.reset_election_timer()

    def send_vote_request(self):
        for server in self.connected_servers:
            msg = Message(constants.MessageType.VOTE_REQUEST, server, self.term, self.pid, self.last_log_index, self.last_log_term).get_message()
            print(f"Sending vote request for term {self.term} to server {server}") 
            send_msg(self.network_server_conn, msg)

    def handle_vote_request(self, msg):
        '''
        If term > currentTerm, currentTerm ← term (step down if leader or candidate)
        If term == currentTerm, votedFor is null or candidateId,
        and candidate's log is at least as complete as local log, grant vote and reset election timeout
        '''
        sender_server_id = msg["candidate_id"]
        vote = False

        if msg["term"] > self.term or \
        ((msg["term"] == self.term and (self.voted_for is None or self.voted_for == sender_server_id)) and \
         (msg["last_log_index"] >= self.last_log_index and msg["last_log_term"] >= self.last_log_term)):
            self.state = constants.RaftState.FOLLOWER
            self.term = msg["term"]
            self.voted_for = sender_server_id
            self.leader = sender_server_id
            # TODO - reset election timer. Will need changes since heartbeat will also reset election timer
            self.reset_election_timer()
            vote = True
            print(f"Voted for server {sender_server_id} in term {self.term}")
        else:
            print(f"Rejected vote request from server {sender_server_id} for term {msg['term']}")

        self.write_to_disk()
        msg = Message(constants.MessageType.VOTE_RESPONSE, sender_server_id, self.term, vote=vote).get_message()
        send_msg(self.network_server_conn, msg)

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
                    print(f"Server {self.pid} became leader in term {self.term}")
                    self.start_heartbeat_timer()
        else:
            # Update term if term in response is greater
            if msg["term"] > self.term:
                self.term = msg["term"]
                self.state = constants.RaftState.FOLLOWER
                self.voted_for = None
                self.leader = None
                self.reset_election_timer()

        self.write_to_disk()

    def handle_heartbeat(self, msg):
        '''
        If heartbeat received from leader, reset election timer
        '''
        # TODO - Check conditions for valid heartbeat
        self.reset_election_timer()

    def handle_client_request(self, msg):
        '''
        If leader, append client request to log and send append entries to all servers
        Else, redirect client request to leader
        '''
        if self.state == constants.RaftState.LEADER:
            self.log.append(msg)
            self.send_append_entries(msg)
        else:
            msg = Message(constants.MessageType.CLIENT_REQUEST, self.leader).get_message()
            send_msg(self.network_server_conn, msg)
        
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