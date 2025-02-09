import threading
from time import sleep

def handle_client_msg(conn, data):
    sleep(3)
    data = data.decode()
    words = data.split()

    try:
        # TODO - Add handling here 
        print(f"Received message from client: {data}")
    except:
	    print("Exception in handling client message")

def recv_msg(conn, addr):
	while True:
		try:
			data = conn.recv(1024)
		except:
			break
		if not data:
			conn.close()
			break
        # Spawn new thread for every msg to ensure IO is non-blocking
		threading.Thread(target=handle_client_msg, args=(conn, data)).start()

def get_cluster(server_id):
	'''
	Return the servers part of server_id's cluster
	1,2,3 -> 1
	4,5,6 -> 2
	7,8,9 -> 3
	'''
	cluster = (server_id - 1) // 3
	return cluster

def get_servers_in_cluster(cluster):
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

class Message:
	def __init__(self, msg_type, dest_id, term=None, candidate_id=None, last_log_index=None, last_log_term=None, vote=None):
		self.msg_type = msg_type
		self.term = term
		self.candidate_id = candidate_id
		self.last_log_index = last_log_index
		self.last_log_term = last_log_term
		self.dest_id = dest_id
		self.vote = vote
