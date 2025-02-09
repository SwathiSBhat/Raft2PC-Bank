import threading
from time import sleep
import json

def get_cluster(server_id):
	'''
	Return the servers part of server_id's cluster
	1,2,3 -> 1
	4,5,6 -> 2
	7,8,9 -> 3
	'''
	cluster = (server_id - 1) // 3
	return cluster

def get_servers_in_cluster(cluster, server_id):
	'''
	Return the servers part of cluster apart from the server itself
	1,2,3 -> 1
	4,5,6 -> 2
	7,8,9 -> 3
	'''
	start = cluster * 3 + 1
	end = start + 3
	servers = [i for i in range(start, end) if i != server_id]
	return servers

def send_msg(conn, msg):
	'''
	Send message to the server
	'''
	msg = json.dumps(msg) + "\n"
	conn.sendall(msg.encode("utf-8"))

class Message:
	def __init__(self, msg_type, dest_id, term=None, candidate_id=None, last_log_index=None, last_log_term=None, vote=None):
		self.msg_type = msg_type
		self.term = term
		self.candidate_id = candidate_id
		self.last_log_index = last_log_index
		self.last_log_term = last_log_term
		self.dest_id = dest_id
		self.vote = vote

	def get_message(self):
		msg = {}
		msg["msg_type"] = self.msg_type
		msg["term"] = self.term
		msg["candidate_id"] = self.candidate_id
		msg["last_log_index"] = self.last_log_index
		msg["last_log_term"] = self.last_log_term
		msg["dest_id"] = self.dest_id
		msg["vote"] = self.vote
		return msg
	
