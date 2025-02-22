# file location to store the logs for each server
C1_LOGS = {1: "logs/server1.log", 2: "logs/server2.log", 3: "logs/server3.log"}
C2_LOGS = {4: "logs/server4.log", 5: "logs/server5.log", 6: "logs/server6.log"}
C3_LOGS = {7: "logs/server7.log", 8: "logs/server8.log", 9: "logs/server9.log"}

# Enum to store states for Raft - FOLLOWER, CANDIDATE, LEADER
class RaftState:
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

# Message types for Raft
class MessageType:
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"
    APPEND_ENTRIES = "append_entries"
    APPEND_ENTRIES_RESPONSE = "append_entries_response"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_RESPONSE = "heartbeat_response"
    CLIENT_REQUEST = "client_request"
    CLIENT_RESPONSE = "client_response"
    CLIENT_COMMIT = "client_commit"