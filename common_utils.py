import json
from constants import MessageType


def get_cluster_from_dataitem(data_item):
    '''
    Return the cluster to which the data item belongs
    '''
    data_item = int(data_item)
    if data_item < 1:
        print("[ERROR] Data item cannot be less than 1")
        return -1
    if data_item <= 1000:
        return 1
    elif data_item <= 2000:
        return 2
    else:
        return 3


def get_cluster(server_id):
    '''
    Return the servers part of server_id's cluster
    1,2,3 -> 1
    4,5,6 -> 2
    7,8,9 -> 3
    '''
    cluster = (server_id + 2) // 3
    return cluster


def get_servers_in_cluster(cluster, server_id=None):
    '''
    Return the servers part of cluster apart from the server itself
    1,2,3 -> 1
    4,5,6 -> 2
    7,8,9 -> 3
    '''
    start = (cluster-1) * 3 + 1
    end = start + 3
    if server_id is not None:
        servers = [i for i in range(start, end) if i != server_id]
    else:
        servers = [i for i in range(start, end)]
    return servers


def send_msg(conn, msg, sender_id=None):
    '''
    Send message to the server
    '''
    msg["sender_id"] = sender_id
    msg = json.dumps(msg) + "\n"
    # Add delay to simulate network latency
    # sleep(config.NETWORK_DELAY)
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
    def __init__(self, command, client_id, dest_id, trans_id):
        self.command = command
        self.client_id = client_id
        self.dest_id = dest_id
        self.trans_id = trans_id
        self.msg_type = MessageType.CLIENT_REQUEST

    def get_message(self):
        msg = {}
        msg["msg_type"] = self.msg_type
        msg["command"] = self.command
        msg["client_id"] = self.client_id
        msg["dest_id"] = self.dest_id
        msg["trans_id"] = self.trans_id
        return msg


class ClientResponseMessage():
    def __init__(self, command, server_id, dest_client_id, status, trans_id, send_prerare_status=False):
        self.command = command
        self.server_id = server_id
        self.dest_id = dest_client_id
        self.msg_type = MessageType.CLIENT_RESPONSE
        self.status = status
        self.trans_id = trans_id
        self.send_prepare_status = False
        if (send_prerare_status):
            self.send_prepare_status = True

    def get_message(self):
        msg = {}
        msg["msg_type"] = self.msg_type
        msg["command"] = self.command
        msg["server_id"] = self.server_id
        msg["dest_id"] = self.dest_id
        msg["status"] = self.status
        msg["trans_id"] = self.trans_id
        if (self.send_prepare_status):
            msg["prepare_status"] = self.status
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
    def __init__(self, dest_id, term, vote, commit_index):
        self.term = term
        self.dest_id = dest_id
        self.vote = vote
        self.commit_index = commit_index
        self.msg_type = MessageType.VOTE_RESPONSE

    def get_message(self):
        msg = {}
        msg["msg_type"] = self.msg_type
        msg["term"] = self.term
        msg["dest_id"] = self.dest_id
        msg["vote"] = self.vote
        msg["sender_commit_index"] = self.commit_index
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

    # def custom_serializer(self,obj):
    # 	if isinstance(obj, LogEntry):
    # 		print(obj, obj.to_json)
    # 		return obj.to_json()  # Convert Person object to dict
    # 	raise TypeError(f"Type {type(obj)} not serializable")

    def get_message(self):
        msg = {}
        msg["msg_type"] = self.msg_type
        msg["term"] = self.term
        msg["dest_id"] = self.dest_id
        msg["leader_id"] = self.leader_id
        msg["prev_log_index"] = self.prev_log_index
        msg["prev_log_term"] = self.prev_log_term
        # TODO - check if there is any optimal solution #json.dumps(self.entries,default=self.custom_serializer)
        msg["entries"] = [i.to_json() for i in self.entries]
        msg["commit_index"] = self.commit_index
        return msg


class AppendEntriesResponseMessage():
    def __init__(self, dest_id, sender_server_id, term, index, commit_index, success):
        self.term = term
        self.approve_index = index
        self.dest_id = dest_id
        self.sender_server_id = sender_server_id
        self.success = success
        self.commit_index = commit_index
        self.msg_type = MessageType.APPEND_ENTRIES_RESPONSE

    def get_message(self):
        msg = {}
        msg["msg_type"] = self.msg_type
        msg["term"] = self.term
        msg["approve_index"] = self.approve_index
        msg["dest_id"] = self.dest_id
        msg["sender_server_id"] = self.sender_server_id
        msg["success"] = self.success
        msg["sender_commit_index"] = self.commit_index
        return msg


class LogEntry:
    def __init__(self, term, command, index, client_id, id=None ,status=-1):
        self.term = term
        self.command = command
        self.index = index
        self.client_id = client_id
        self.id = id
        self.status = status # -1->pending 1->success 0-> failure

    @classmethod
    def from_dict(cls, data):
        return cls(data['term'], data['command'], data['index'], data['client_id'], data['id'],data['status'])

    def __repr__(self):
        return f"LogEntry(term={self.term}, command={self.command}, index={self.index}, client_id={self.client_id}, id={self.id}, status={self.status})"

    def __str__(self):
        return f"LogEntry(term={self.term}, command={self.command}, index={self.index}, client_id={self.client_id}, id={self.id}, status={self.status})"

    def __eq__(self, other):
        return self.term == other.term and self.index == other.index and self.client_id == other.client_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_json(self):
        # return self.__dict__
        return {"term": self.term, "command": self.command, "index": self.index, "client_id": self.client_id, "id": self.id, "status": self.status}

class Colors:
    VIOLET = '\033[94m'
    BLUE = '\033[36m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'    # yellow
    ERROR = '\033[91m'   # red
    ENDCOLOR = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'
    SUCCESS = '\033[42m'
    FAILED = '\033[41m'