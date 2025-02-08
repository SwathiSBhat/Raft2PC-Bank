'''
Common file for servers 1-9
'''

import config
import socket
import threading
from sys import argv, stdout
from os import _exit
import common_utils

def get_user_input():
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]

        if cmd == "exit":
			# close all client sockets
            #for sock in out_socks:
            #    sock[0].close()
            stdout.flush()
			# exit program with status 0
            _exit(0)
        
        elif cmd == "intra-shard":
            # intra-shard <from account> <to account> <amount>
            # The balance for both accounts is stored in same cluster
            # Use Raft to achieve concensus within the cluster
            from_account = int(user_input.split()[1])
            to_account = int(user_input.split()[2])
            amount = int(user_input.split()[3])
        elif cmd == "inter-shard":
            # inter-shard <from account> <to account> <amount>
            # The balance for both accounts is stored in different clusters
            # Use 2PC and Raft to achieve concensus across clusters
            pass

if __name__ == "__main__":
    
    pid = argv[1]

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
    threading.Thread(target=common_utils.recv_msg, args=(network_sock, (SERVER_IP, config.NETWORK_SERVER_PORT))).start()
    # Send test message to network server
    network_sock.send(f"Connected to server {pid}".encode())