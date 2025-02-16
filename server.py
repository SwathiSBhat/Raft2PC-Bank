'''
Common file for servers 1-9
'''

import config
import socket
import threading
from sys import argv, stdout
from os import _exit
from consensus_module import RaftConsensus
from common_utils import send_msg
import json

def handle_server_msg(conn, data):    
    data = json.loads(data)
    try:
        raft.handle_message(data)
    except:
	    print("Exception in handling message from network server")

def recv_msg(conn, addr):
    buffer = ""
    while True:
        try:
            data = conn.recv(1024)
        except:
            break
        if not data:
            conn.close()
            break
        buffer += data.decode()

        while "\n" in buffer:
            msg, buffer = buffer.split("\n", 1)
            try:
                # Spawn new thread for every msg to ensure IO is non-blocking
                threading.Thread(target=handle_server_msg, args=(conn, msg)).start()
            except:
                print("[ERROR] Exception in handling message at server {pid}")
                break

def get_user_input():
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]

        if cmd == "exit":
            # send msg to network server about exit so that it can be marked as down
            msg = {"msg_type": "server_exit", "node_id": pid}
            send_msg(network_sock, msg)
            stdout.flush()
			# exit program with status 0
            _exit(0)


if __name__ == "__main__":

    pid = int(argv[1])

    SERVER_IP = socket.gethostname()
    SERVER_PORT = config.SERVER_PORTS[int(pid)]

    # listen for user input in separate thread - mostly just exit commands
    threading.Thread(target=get_user_input).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((SERVER_IP, SERVER_PORT))

    # Connect to network server
    network_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    network_sock.connect((SERVER_IP, config.NETWORK_SERVER_PORT))
    threading.Thread(target=recv_msg, args=(network_sock, (SERVER_IP, config.NETWORK_SERVER_PORT))).start()
    # Send test message to network server
    msg = {"msg_type": "init", "node_id": pid}
    send_msg(network_sock, msg)

    # Create Raft consensus object for current server
    raft = RaftConsensus(pid, network_sock)