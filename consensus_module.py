import constants
import threading
import random
import common_utils
import os
import json
import struct
from collections import defaultdict
import numpy as np
from common_utils import (
    send_msg, LogEntry, HeartbeatMessage,
    VoteResponseMessage, VoteRequestMessage, AppendEntriesMessage,
    AppendEntriesResponseMessage, ClientResponseMessage
)
from time import sleep
import config


class RaftConsensus:
    def __init__(self, pid, network_server_conn):
        self.pid = int(pid)
        self.total_servers_in_clusture = 3
        self.cluster = common_utils.get_cluster(self.pid)
        self.connected_servers = common_utils.get_servers_in_cluster(
            self.cluster, pid)
        print(f"Connected servers: {self.connected_servers}")
        self.network_server_conn = network_server_conn
        self.quorum = (len(self.connected_servers) + 1) // 2 + 1
        # Start off as follower
        self.state = constants.RaftState.FOLLOWER
        self.term = 0
        self.leader = None
        self.voted_for = None
        self.votes = 0
        self.commit_index = 0
        self.next_index = {}
        self.server_commit_index = {}
        self.last_log_index = 0
        self.last_log_term = 0
        self.log = [LogEntry(self.term, "", self.last_log_index, -1)]
        self.last_log_writtern_disk = 0
        # Initialize election timeout to some random value
        self.election_timeout = (self.pid)%3 + 2*config.NETWORK_DELAY#random.uniform(1.0, 4.0) + 2*config.NETWORK_DELAY

        # Lock to ensure only one thread updates the logs and vote count
        self.lock = threading.Lock()
        self.write_log_lock = threading.Lock()
        # self.state_machine_lock = threading.Lock()
        self.conditional_lock_state_machine = threading.Condition()
        self.processing_ids = defaultdict(int)
        self.pending_request = 0

        self.read_from_disk()
        self.write_to_disk()

        self.state_machine_write(1)

        self.heartbeat_timer = None
        self.heartbeat_timeout = 0.5 + 2*config.NETWORK_DELAY
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        self.election_timer.start()
        self.two_pc_log = {}
        # print(self.state_machine_read(1))
        # print(self.state_machine_read(10))

    # Function to compute the size of the serialized objects up to a given index

    def calculate_size_of_objects(self):
        # Serialize the objects up to the given index and calculate their byte size
        # Convert objects to JSON
        data = json.dumps([obj.to_json()
                          for obj in self.log[:self.last_log_writtern_disk]])
        print(data, " calculated data")
        return len(data.encode('utf-8'))-1  # Return the byte size

    def write_to_disk(self):
        '''
        Write current term, votedFor, log to disk
        '''
        # TODO  can we optimise it more?? because currently writing all the log file again even unmodified once but instead need to write only modified one
        filename = f'{config.FILEPATH}/server_{self.pid}.txt'
        # If file doesn't exist, create it and write the first batch of data
        with self.write_log_lock:
            if not os.path.exists(filename):

                with open(filename, 'w') as file:
                    new_data = [obj.to_json() for obj in self.log]
                    file.write(f"{self.commit_index}\n")
                    file.write(json.dumps(new_data))  # [1:-1])
                    print(file.tell(), " last written index")
                    # json.dump([obj.to_json() for obj in self.log], file)
                    self.last_log_writtern_disk = len(self.log)
                return

        if (self.last_log_writtern_disk < len(self.log)):
            with self.write_log_lock:
                # print(os.path.getsize(filename) , " :: total length")
                with open(filename, 'r+') as file:
                    file.write(f"{self.commit_index}\n")
                    new_data = [obj.to_json() for obj in self.log]
                    temp = json.dumps(new_data)

                    file.write(temp)
                self.last_log_writtern_disk = len(self.log)
        else:
            with self.write_log_lock:
                with open(filename, 'r+') as file:
                    file.write(f"{self.commit_index}\n")

    def reset_election_timer(self):
        self.election_timer.cancel()
        self.election_timer = threading.Timer(
            self.election_timeout, self.start_election)
        self.election_timer.start()

    def reset_heartbeat_timer(self):
        self.heartbeat_timer.cancel()
        self.heartbeat_timer = threading.Timer(
            self.heartbeat_timeout, self.start_heartbeat_timer)
        self.heartbeat_timer.start()

    def cancel_election_timer(self):
        self.election_timer.cancel()

    def start_heartbeat_timer(self):
        self.send_heartbeat()
        self.heartbeat_timer = threading.Timer(
            self.heartbeat_timeout, self.start_heartbeat_timer)
        self.heartbeat_timer.start()
        # threading.Thread(target=self.send_heartbeat).start()

    def send_heartbeat(self):
        '''
        Send heartbeat to all servers in a separate thread every 0.5 seconds
        if current state is leader
        '''
        if self.state == constants.RaftState.LEADER:
            for server in self.connected_servers:

                # If the follower's log is up to date, send a lightweight heartbeat message
                # since it doesn't need to update any logs
                if (self.server_commit_index[server] >= self.commit_index and self.pending_request == 0):
                    msg = HeartbeatMessage(
                        self.pid, server, self.term).get_message()
                    send_msg(self.network_server_conn, msg, self.pid)

                # If the follower's log is not up to date, send append entries message
                else:
                    msg = AppendEntriesMessage(
                        server,
                        self.term,
                        self.pid,
                        self.log[self.next_index[server] - 1].index,
                        self.log[self.next_index[server] - 1].term,
                        self.log[self.next_index[server]:],
                        self.commit_index).get_message()
                    send_msg(self.network_server_conn, msg, self.pid)

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
        elif msg["msg_type"] == constants.MessageType.CLIENT_COMMIT:
            self.handle_two_pc_commit(msg)

    def handle_two_pc_commit(self, msg):
        '''This function handles the two pc commit protocol'''
        if (msg["trans_id"] in self.two_pc_log):
            with self.lock:
                log_entry = self.two_pc_log[msg["trans_id"]]
            cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(log_entry.command.split(','))]#list(map(int, log_entry.command.split(",")))
            if (msg["commit"] == True):
                if (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000):
                    amt = self.state_machine_read(cmd[0])
                    # If balance is low but 2PC has sent a commit, something is wrong
                    if (amt < cmd[2]):
                        with self.conditional_lock_state_machine:
                            self.processing_ids[cmd[0]] -= 1
                            self.processing_ids[cmd[1]] -= 1
                            self.conditional_lock_state_machine.notify_all()
                        print("Something has gone wrong PLEASE CHECK!!!!: balance amount is low ",
                              amt, " for transaction: ", log_entry.command)
                        raise ValueError(
                            f"Something has gone wrong PLEASE CHECK!!!!: balance amount is low {amt} for transaction: {log_entry.command}")
                    # Update balance with new transaction amount
                    self.state_machine_write(cmd[0], amt - cmd[2])
                    
                elif (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000):
                    amt = self.state_machine_read(cmd[1])
                    self.state_machine_write(cmd[1], amt + cmd[2])

                with self.conditional_lock_state_machine:
                    self.processing_ids[cmd[0]] -= 1
                    self.processing_ids[cmd[1]] -= 1
                    self.conditional_lock_state_machine.notify_all()
                print(
                    f"SENT SUCCESS message for Two-PC message to Client: {msg['client_id']} for trans:{msg['command']} {self.processing_ids} {cmd}")
                msg = ClientResponseMessage(msg["command"],
                                            self.pid,
                                            msg["client_id"],
                                            True, msg["trans_id"]).get_message()
                send_msg(self.network_server_conn, msg, self.pid)
            else:
                with self.conditional_lock_state_machine:
                    self.processing_ids[cmd[0]] -= 1
                    self.processing_ids[cmd[1]] -= 1
                    self.conditional_lock_state_machine.notify_all()
                print(
                    f"SENT Failed message for Two-PC message to Client: {msg['client_id']} for trans: {msg['command']}")
                msg = ClientResponseMessage(msg["command"],
                                            self.pid,
                                            msg["client_id"],
                                            False, msg["trans_id"]).get_message()
                send_msg(self.network_server_conn, msg, self.pid)
            with self.lock:
                del self.two_pc_log[msg["trans_id"]]
        else:
            # this might be the case, when prepare phase has aborted due to lock or amt
            print(
                f"SENT Failed message for Two-PC message to Client: {msg['client_id']} for trans: {msg['command']}")
            msg = ClientResponseMessage(msg["command"],
                                        self.pid,
                                        msg["client_id"],
                                        False, msg["trans_id"]).get_message()
            send_msg(self.network_server_conn, msg, self.pid)

    def start_election(self):
        '''
        Start election process by incrementing term and voting for self
        Send vote request to all servers
        '''
        # If current state is leader, don't start election
        if self.state == constants.RaftState.LEADER:
            return
        self.state = constants.RaftState.CANDIDATE
        self.term += 1
        self.voted_for = self.pid
        self.votes = 1
        self.send_vote_request()
        self.reset_election_timer()

    def handle_client_request(self, msg):
        '''
        If leader, append client request to log and send append entries to all servers
        Else, redirect client request to leader        
        '''

        print(f"Received client request: {msg},  leader: {self.leader}")
        if self.state == constants.RaftState.LEADER:
            self.send_append_entries(msg)
        else:
            #TODO - if it doesnot know the leader then?? do we need to do election??
            # Route to leader
            msg["dest_id"] = self.leader
            print(f"Routing client request to leader: {self.leader}")
            send_msg(self.network_server_conn, msg, self.pid)

    def send_vote_request(self):
        for server in self.connected_servers:
            msg = VoteRequestMessage(
                self.term,
                server,
                self.pid,
                self.last_log_index,
                self.last_log_term).get_message()
            print(
                f"Sending vote request for term {self.term} to server {server}")
            send_msg(self.network_server_conn, msg, self.pid)

    def handle_vote_request(self, msg):
        '''
        If term > currentTerm, currentTerm ← term (step down if leader or candidate)
        If term == currentTerm, votedFor is null or candidateId,
        and candidate's log is at least as complete as local log, grant vote and reset election timeout
        '''
        sender_server_id = msg["candidate_id"]
        vote = False

        if msg["term"] > self.term or \
            ((msg["term"] == self.term and (self.voted_for is None or self.voted_for == sender_server_id)) and
             (msg["last_log_index"] >= self.last_log_index and msg["last_log_term"] >= self.last_log_term)):
            self.state = constants.RaftState.FOLLOWER
            self.term = msg["term"]
            self.voted_for = sender_server_id
            self.leader = sender_server_id
            self.reset_election_timer()
            vote = True
            print(f"Voted for server {sender_server_id} in term {self.term}")
        else:
            print(
                f"Rejected vote request from server {sender_server_id} for term {msg['term']}")

        self.write_to_disk()
        msg = VoteResponseMessage(
            sender_server_id, self.term, vote, self.commit_index).get_message()
        send_msg(self.network_server_conn, msg, self.pid)

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
                    self.pending_request = 0
                    self.votes = 0
                    self.state = constants.RaftState.LEADER
                    self.leader = self.pid
                    print(
                        f"Server {self.pid} became leader in term {self.term}")
                    # acquire lock to all the pending commits
                    for i in range(self.commit_index+1, len(self.log)):
                        log_entry = self.log[i]
                        cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(log_entry.command.split(','))]#list(map(float, log_entry.command.split(",")))
                        with self.conditional_lock_state_machine:
                            self.processing_ids[cmd[0]] += 1
                            self.processing_ids[cmd[1]] += 1
                    # Set next_index for all servers to last log index + 1
                    for server in self.connected_servers:
                        self.next_index[server] = self.last_log_index + 1
                        self.server_commit_index[server] = msg["sender_commit_index"]
                    self.start_heartbeat_timer()
                    self.heartbeat_timer = threading.Timer(
                        self.heartbeat_timeout, self.start_heartbeat_timer)
                    self.heartbeat_timer.start()
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
        self.leader = msg["sender_server_id"]
        self.reset_election_timer()

    def send_append_entries(self, msg):
        '''
        Invoked by leader to replicate log entries and discover inconsistencies
        1. Append command to local log
        2. Send append entries to all servers
        '''
        cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(msg["command"].split(','))]#list(map(int, msg["command"].split(",")))
        
        with self.conditional_lock_state_machine:
            # If either sender or receiver is locked i.e as part of another transaction 
            # wait until the transaction is completed
            while (self.processing_ids[cmd[0]] != 0 or self.processing_ids[cmd[1]] != 0):
                print(
                    f" STUCK in this this loop {cmd} {self.processing_ids} in line 345\n\n")
                
                # If it's a cross-shard transaction, 
                if (((cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000) and not (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000)) or \
                    (not (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000) and (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000))):
                    send_prepare_status = True
                    msg = ClientResponseMessage(msg["command"],
                                                self.pid,
                                                msg["client_id"],
                                                False, msg["trans_id"], send_prepare_status).get_message()
                    send_msg(self.network_server_conn, msg, self.pid)
                    return
                self.conditional_lock_state_machine.wait()
            self.pending_request += 1
            self.processing_ids[cmd[0]] = 1
            self.processing_ids[cmd[1]] = 1

        if (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000):
            amt = self.state_machine_read(cmd[0])
            # If sender's balance is low, reject the transaction
            if (amt < cmd[2]):
                self.pending_request -= 1
                send_prepare_status = not (
                    cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000)
                msg = ClientResponseMessage(msg["command"],
                                            self.pid,
                                            msg["client_id"],
                                            False, msg["trans_id"], send_prepare_status).get_message()
                self.processing_ids[cmd[0]] = 0
                self.processing_ids[cmd[1]] = 0
                with self.conditional_lock_state_machine:
                    self.conditional_lock_state_machine.notify_all()
                print("FAILED Transaction because of insufficient balance: ",
                      amt, " for transaction: ", msg["command"])
                send_msg(self.network_server_conn, msg, self.pid)
                return

        # Else, append command to local log and send append entries to all followers
        with self.lock:
            logEntry = LogEntry(
                self.term, msg["command"], self.last_log_index + 1, msg["client_id"], msg["trans_id"])
            self.last_log_index += 1
            self.last_log_term = self.term
            self.log.append(logEntry)
        self.reset_heartbeat_timer()
        for server in self.connected_servers:
            # If prev_log_index >= next_index for server, send append entries
            # with log entries starting at next_index for server

            msg = AppendEntriesMessage(
                server,
                self.term,
                self.pid,
                self.log[self.next_index[server] - 1].index,
                self.log[self.next_index[server] - 1].term,
                self.log[self.next_index[server]:],
                self.commit_index).get_message()

            send_msg(self.network_server_conn, msg, self.pid)

    def handle_append_entries(self, msg):
        '''
        1. If leader's term < current term, reject append entries and send term in response
        2. If leader's term > current term, reset election timer, update term and step down to follower.
        3. Return failure if log doesn't contain an entry at prevLogIndex whose term matches prevLogTerm
        4. If an existing entry conflicts with a new one, delete the existing entry and all that follow it
        5. Append any new entries not already in the log
        6. Advance state machine by applying newly committed entries
        '''
        leader = msg["leader_id"]
        if msg["term"] < self.term:
            msg = AppendEntriesResponseMessage(
                leader,
                self.pid,
                self.term,
                self.log[-1].index,
                self.commit_index,
                False).get_message()
            send_msg(self.network_server_conn, msg, self.pid)
            return
        elif msg["term"] > self.term:
            self.term = msg["term"]
            self.voted_for = None

        # If candidate or leader, step down to follower
        if self.state == constants.RaftState.CANDIDATE or self.state == constants.RaftState.LEADER:
            self.state = constants.RaftState.FOLLOWER
            self.leader = leader
            if (self.heartbeat_timer != None):
                self.heartbeat_timer.cancel()
                self.heartbeat_timer = None

        self.reset_election_timer()
        # Check if log contains an entry at prevLogIndex whose term matches prevLogTerm
        if msg["prev_log_index"] >= len(self.log) or \
                self.log[msg["prev_log_index"]].term != msg["prev_log_term"]:
            msg = AppendEntriesResponseMessage(
                leader,
                self.pid,
                self.term,
                self.log[-1].index,
                self.commit_index,
                False).get_message()
            send_msg(self.network_server_conn, msg, self.pid)
            return

        with self.lock:
            # Append any new entries not already in the log and delete conflicting entries
            self.log = self.log[:msg["prev_log_index"] + 1]
            n = len(self.log)
            j_temp = msg["prev_log_index"] + 1
            for i in msg["entries"]:
                if (j_temp < n):
                    self.log[j_temp] = LogEntry.from_dict(i)
                else:
                    self.log.append(LogEntry.from_dict(i))

                cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(self.log[j_temp].command.split(','))]#list(map(int, self.log[j_temp].command.split(",")))
                # If it's a cross-shard transaction, add it to 2PC log and
                # wait until resources are available to process it
                if (msg["commit_index"] < j_temp and not (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000) or not (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000)):
                    if (self.log[j_temp].id not in self.two_pc_log):
                        self.two_pc_log[self.log[j_temp].id] = self.log[j_temp]
                        with self.conditional_lock_state_machine:
                            # TODO - check if this wait is required??
                            while (self.processing_ids[cmd[0]] != 0 or self.processing_ids[cmd[1]] != 0):
                                print(
                                    f"STUCK in this this loop {cmd} {self.processing_ids} {self.log}in line 472\n\n")
                                self.conditional_lock_state_machine.wait()
                            self.processing_ids[cmd[0]] += 1
                            self.processing_ids[cmd[1]] += 1
                j_temp += 1
                
            for i in range(self.commit_index+1, msg["commit_index"]+1):
                log_entry = self.log[i]
                cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(log_entry.command.split(','))]#list(map(int, log_entry.command.split(",")))
                if (not (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000) or not (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000)):
                    # self.two_pc_log[log_entry.id] = log_entry
                    # print(self.two_pc_log, log_entry , i , len(self.log) , " second time it came")
                    # if (log_entry.id not in self.two_pc_log):
                    #     self.two_pc_log[log_entry.id] = log_entry
                    #     with self.conditional_lock_state_machine:
                    #         # TODO - check if this wait is required??
                    #         while (self.processing_ids[cmd[0]] != 0 or self.processing_ids[cmd[1]] != 0):
                    #             print(
                    #                 f"STUCK in this this loop {cmd} {self.processing_ids} {self.log}in line 474\n\n")
                    #             self.conditional_lock_state_machine.wait()
                    #         self.processing_ids[cmd[0]] += 1
                    #         self.processing_ids[cmd[1]] += 1
                    continue
                
                with self.conditional_lock_state_machine:
                    # TODO - check if this wait is required??
                    while (self.processing_ids[cmd[0]] != 0 or self.processing_ids[cmd[1]] != 0):
                        print(
                            f"STUCK in this this loop {cmd} {self.processing_ids} {log_entry}in 486 line\n\n")
                        self.conditional_lock_state_machine.wait()
                    self.processing_ids[cmd[0]] += 1
                    self.processing_ids[cmd[1]] += 1
                # if(not(cmd[0]>(self.cluster-1) *1000 and cmd[0]<=(self.cluster) *1000) or not(cmd[1]>(self.cluster-1) *1000 and cmd[1]<=(self.cluster) *1000)):
                    # self.two_pc_log[log_entry.id] = log_entry
                #    continue
                # else:
                amt = self.state_machine_read(cmd[0])
                if (amt < cmd[2]):
                    self.processing_ids[cmd[0]] -= 1
                    self.processing_ids[cmd[1]] -= 1
                    with self.conditional_lock_state_machine:
                        self.conditional_lock_state_machine.notify_all()
                    print("Something has gone wrong PLEASE CHECK!!!!: balance amount is low ",
                          amt, " for transaction: ", log_entry.command)
                    raise ValueError(
                        f"Something has gone wrong PLEASE CHECK!!!!: balance amount is low {amt} for transaction: {log_entry.command}")
                else:
                    # if(cmd[0]>(self.cluster-1) *1000 and cmd[0]<=(self.cluster) *1000):
                    self.state_machine_write(cmd[0], amt - cmd[2])
                # if(cmd[1]>(self.cluster-1) *1000 and cmd[1]<=(self.cluster) *1000):
                    amt = self.state_machine_read(cmd[1])
                    self.state_machine_write(cmd[1], amt + cmd[2])
                    self.processing_ids[cmd[0]] -= 1
                    self.processing_ids[cmd[1]] -= 1
                    with self.conditional_lock_state_machine:
                        self.conditional_lock_state_machine.notify_all()
            self.commit_index += (msg["commit_index"]-self.commit_index)
            # self.commit_index = msg["commit_index"]
            self.write_to_disk()
            self.last_log_index = self.log[-1].index
            self.last_log_term = self.log[-1].term

        msg = AppendEntriesResponseMessage(
            leader,
            self.pid,
            self.term,
            self.log[-1].index,
            self.commit_index,
            True).get_message()
        send_msg(self.network_server_conn, msg, self.pid)
        # self.write_to_disk()
        print(f"Server {self.pid} log: {self.log}")
        print(f"Server {self.pid} commit index: {self.commit_index}")
        print(f"Server {self.pid} term: {self.term}")
        print(f"Server {self.pid} state: {self.state}")

    def handle_append_entries_response(self, msg):
        '''
        1. If response is successful, update nextIndex and matchIndex for follower
        2. If response is not successful, decrement nextIndex and retry
        '''
        if msg["success"]:
            # since we have only 3 servers in cluster this should work
            # NOTE below will not work if there are more then 3 server in a cluster
            # self.commit_index+=1
            # TODO - check if the lock can be removed , (thinking:: whether two concurrent success then we should not commit twice)
            with self.lock:
                if (self.next_index[msg["sender_server_id"]] < msg["approve_index"]+1):
                    # TODO -check if its correct
                    self.next_index[msg["sender_server_id"]
                                    ] = msg["approve_index"]+1
                if (self.server_commit_index[msg["sender_server_id"]] < msg["sender_commit_index"]):
                    self.server_commit_index[msg["sender_server_id"]
                                             ] = msg["sender_commit_index"]
                for i in range(self.commit_index+1, msg["approve_index"]+1):
                    log_entry = self.log[i]
                    cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(log_entry.command.split(','))]#list(map(int, log_entry.command.split(",")))
                    if (not (cmd[0] > (self.cluster-1) * 1000 and cmd[0] <= (self.cluster) * 1000) or not (cmd[1] > (self.cluster-1) * 1000 and cmd[1] <= (self.cluster) * 1000)):
                        with self.conditional_lock_state_machine:
                            self.pending_request -= 1
                        self.two_pc_log[log_entry.id] = log_entry
                        msg1 = ClientResponseMessage(log_entry.command,
                                                     self.pid,
                                                     log_entry.client_id,
                                                     True, log_entry.id, True).get_message()
                        send_msg(self.network_server_conn, msg1, self.pid)
                    else:
                        # if(cmd[0]>(self.cluster-1) *1000 and cmd[0]<=(self.cluster) *1000):
                        amt = self.state_machine_read(cmd[0])
                        if (amt < cmd[2]):
                            self.processing_ids[cmd[0]] -= 1
                            self.processing_ids[cmd[1]] -= 1
                            with self.conditional_lock_state_machine:
                                self.pending_request -= 1
                                self.conditional_lock_state_machine.notify_all()
                            print("Something has gone wrong PLEASE CHECK!!!!: balance amount is low ",
                                  amt, " for transaction: ", log_entry.command)
                            raise ValueError(
                                f"Something has gone wrong PLEASE CHECK!!!!: balance amount is low {amt} for transaction: {log_entry.command}")
                        else:
                            self.state_machine_write(cmd[0], amt - cmd[2])
                            amt = self.state_machine_read(cmd[1])
                            self.state_machine_write(cmd[1], amt + cmd[2])
                            self.processing_ids[cmd[0]] -= 1
                            self.processing_ids[cmd[1]] -= 1
                            # print(self.processing_ids)
                            with self.conditional_lock_state_machine:
                                self.pending_request -= 1
                                self.conditional_lock_state_machine.notify_all()

                        msg1 = ClientResponseMessage(log_entry.command,
                                                     self.pid,
                                                     log_entry.client_id,
                                                     True, log_entry.id).get_message()
                        send_msg(self.network_server_conn, msg1, self.pid)
                if (msg["approve_index"] > self.commit_index):
                    self.commit_index += (msg["approve_index"] -
                                          self.commit_index)
                print("commitID: ", self.commit_index, " done  committing")

        else:
            if msg["term"] > self.term:
                self.term = msg["term"]
                self.state = constants.RaftState.FOLLOWER
                self.voted_for = None
                self.leader = None
                self.reset_election_timer()
            else:
                # Decrement nextIndex and send append entries again
                self.next_index[msg["sender_server_id"]] -= 1
                # self.send_append_entries(msg)
                server = msg['sender_server_id']
                msg = AppendEntriesMessage(
                    server,
                    self.term,
                    self.pid,
                    self.log[self.next_index[server] - 1].index,
                    self.log[self.next_index[server] - 1].term,
                    self.log[self.next_index[server]:],
                    self.commit_index).get_message()
                send_msg(self.network_server_conn, msg, self.pid)
                print("resent message")
        print("done with handle_append_entries_response")
        self.write_to_disk()
        print("done with writing in handle_append_entries_response")

    def read_from_disk(self):
        '''
        Read current term, votedFor, log from disk
        '''
        filename = f'{config.FILEPATH}/server_{self.pid}.txt'

        if os.path.exists(filename):
            with open(filename, 'r') as file:
                self.commit_index = int(file.readline())
                data = json.load(file)
                # print(data , "read log form disk")
                self.log = [LogEntry.from_dict(item) for item in data]
                self.last_log_writtern_disk = len(self.log)
                self.term = self.log[-1].term
                self.last_log_index = self.log[-1].index
                self.last_log_term = self.log[-1].term
        # print( self.commit_index, self.log, self.term, self.last_log_index , " all these are updated from disk")

    def state_machine_read(self, row_id):
        '''
        Read database based on ID
        '''
        filename = f'{config.FILEPATH}/stateMachine_{self.pid}.txt'
        # TODO - write more optimal solution because below loop over to find the offset
        # print("read request is ", row_id)
        try:
            with open(filename, 'r+b') as file:
                row_offset = row_id - (self.cluster-1) * 1000
                file.seek((row_offset-1) * 16)
                row = struct.unpack('dd', file.read(16))
                # value = struct.unpack('q', file.read(8))[0]
                # print(row ," row read")
                value = row[1]  # int(row.split()[1])

                return value
        except FileNotFoundError:
            print(f"The file '{filename}' does not exist.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def state_machine_write(self, row_id, val=None):
        # '''
        # write\update database based on ID
        # '''
        filename = f'{config.FILEPATH}/stateMachine_{self.pid}.txt'
        
        if not os.path.exists(filename):
            # data = np.random.randint(0, 100, size=100, dtype=np.int64)
            with open(filename, 'wb') as file:
                st = (self.cluster-1) * 1000+1
                # for now creating the random file but we need to have the actual file
                for i in range(st, st+1000):
                    # file.write(f"{struct.pack('q', i)} {struct.pack('q', 10)}\n".encode())
                    file.write(struct.pack('dd', np.float64(i), np.float64(10)))

        if (val!=None):
            with open(filename, 'r+b') as file:
                offset = 0
                row_offset = row_id - (self.cluster-1) * 1000
                file.seek((row_offset-1) * 16)
                file.write(struct.pack('dd', np.float64(row_id), np.float64(val)))
