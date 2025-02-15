import threading
from time import sleep
import json
from constants import MessageType

def get_cluster(server_id):
	'''
	Return the servers part of server_id's cluster
	1,2,3 -> 1
	4,5,6 -> 2
	7,8,9 -> 3
	'''
	cluster = (server_id - 1) // 3
	return cluster

def get_servers_in_cluster(cluster, server_id=None):
	'''
	Return the servers part of cluster apart from the server itself
	1,2,3 -> 1
	4,5,6 -> 2
	7,8,9 -> 3
	'''
	start = cluster * 3 + 1
	end = start + 3
	if server_id is not None:
		servers = [i for i in range(start, end) if i != server_id]
	else:
		servers = [i for i in range(start, end)]
	return servers

def send_msg(conn, msg):
	'''
	Send message to the server
	'''
	msg = json.dumps(msg) + "\n"
	conn.sendall(msg.encode("utf-8"))

class HeartbeatMessage():
	def __init__(self, sender_server_id, dest_id, term):
		self.term = term
		self.sender_server_id = sender_server_id
		self.dest_id = dest_id
		self.msg_type = MessageType.HEARTBEAT

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["sender_server_id"] = self.sender_server_id
		msg["dest_id"] = self.dest_id
		return msg

class ClientRequestMessage():
	def __init__(self, command, client_id, dest_id):
		self.command = command
		self.client_id = client_id
		self.dest_id = dest_id
		self.msg_type = MessageType.CLIENT_REQUEST

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["command"] = self.command
		msg["client_id"] = self.client_id
		msg["dest_id"] = self.dest_id
		return msg
	
class VoteRequestMessage():
	def __init__(self, term, dest_id, candidate_id, last_log_index, last_log_term):
		self.term = term
		self.dest_id = dest_id
		self.candidate_id = candidate_id
		self.last_log_index = last_log_index
		self.last_log_term = last_log_term
		self.msg_type = MessageType.VOTE_REQUEST

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["dest_id"] = self.dest_id
		msg["candidate_id"] = self.candidate_id
		msg["last_log_index"] = self.last_log_index
		msg["last_log_term"] = self.last_log_term
		return msg
	
class VoteResponseMessage():
	def __init__(self, dest_id, term, vote):
		self.term = term
		self.dest_id = dest_id
		self.vote = vote
		self.msg_type = MessageType.VOTE_RESPONSE

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["dest_id"] = self.dest_id
		msg["vote"] = self.vote
		return msg
	
class AppendEntriesMessage():
	def __init__(self, dest_id, term, leader_id, prev_log_index, prev_log_term, entries, commit_index):
		self.term = term
		self.dest_id = dest_id
		self.leader_id = leader_id
		self.prev_log_index = prev_log_index
		self.prev_log_term = prev_log_term
		self.entries = entries
		self.commit_index = commit_index
		self.msg_type = MessageType.APPEND_ENTRIES

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["dest_id"] = self.dest_id
		msg["leader_id"] = self.leader_id
		msg["prev_log_index"] = self.prev_log_index
		msg["prev_log_term"] = self.prev_log_term
		msg["entries"] = self.entries
		msg["commit_index"] = self.commit_index
		return msg
	
class AppendEntriesResponseMessage():
	def __init__(self, dest_id, sender_server_id, term, success):
		self.term = term
		self.dest_id = dest_id
		self.sender_server_id = sender_server_id
		self.success = success
		self.msg_type = MessageType.APPEND_ENTRIES_RESPONSE

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["dest_id"] = self.dest_id
		msg["sender_server_id"] = self.sender_server_id
		msg["success"] = self.success
		return msg
	
class LogEntry:
	def __init__(self, term, command, index, client_id):
		self.term = term
		self.command = command
		self.index = index
		self.client_id = client_id
		self.id = None
		
	def __repr__(self):
		return f"LogEntry(term={self.term}, command={self.command}, index={self.index}, client_id={self.client_id})"
	
	def __str__(self):
		return f"LogEntry(term={self.term}, command={self.command}, index={self.index}, client_id={self.client_id})"
	
	def __eq__(self, other):
		return self.term == other.term and self.index == other.index and self.client_id == other.client_id
	
	def __ne__(self, other):
		return not self.__eq__(other)	
