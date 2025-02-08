'''
The network server just connected to all the 9 servers and relays messages between servers 
The network server also provides the following commands:
1. failNode <node_id> - This command will kill the server node with the given node_id.
2. failLink <node_id1> <node_id2> - This command will kill the link between the two servers with the given node_id1 and node_id2.
'''

import socket
from sys import stdout
from os import _exit
import threading
import time
import os
import random
import config
import common_utils

def get_user_input():
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]

        if cmd == "exit":
			# close all client sockets
            for sock in out_socks:
                sock[0].close()
            stdout.flush()
			# exit program with status 0
            _exit(0)
                  
        elif cmd == "failNode":
            # failNode <node_id>
            node_id = int(user_input.split()[1])
            # kill the server node with the given node_id
            for sock, addr in out_socks:
                if addr[1] == node_id:
                    sock.close()
                    print(f"Killed server node with node_id: {node_id}")
                    break
        elif cmd == "failLink":
            # failLink <node_id1> <node_id2>
            node_id1 = int(user_input.split()[1])
            node_id2 = int(user_input.split()[2])
            # kill the link between the two servers with the given node_id1 and node_id2
            # Update the status of the link between the two servers from config dictionary
            if node_id1 < node_id2:
                config.LINKS[(node_id1, node_id2)] = False
            else:
                config.LINKS[(node_id2, node_id1)] = False
        elif cmd == "fixLink":
            # fixLink <node_id1> <node_id2>
            node_id1 = int(user_input.split()[1])
            node_id2 = int(user_input.split()[2])
            # fix the link between the two servers with the given node_id1 and node_id2
            # Update the status of the link between the two servers from config dictionary
            if node_id1 < node_id2:
                config.LINKS[(node_id1, node_id2)] = True
            else:
                config.LINKS[(node_id2, node_id1)] = True

if __name__ == "__main__":

    NETWORK_SERVER_IP = socket.gethostname()
    NETWORK_SERVER_PORT = config.NETWORK_SERVER_PORT

    # listen for user input in separate thread
    threading.Thread(target=get_user_input).start()

    # Create in_sock to listen for incoming connections from all servers
    in_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    in_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    in_sock.bind((NETWORK_SERVER_IP, NETWORK_SERVER_PORT))

    in_sock.listen()
    out_socks = []

    # infinite loop to keep waiting for incoming connections from other clients
    while True:
        try:
            # accept incoming connection
            conn, addr = in_sock.accept()
        except:
            break
        out_socks.append((conn, addr))
		# Start a new thread to handle incoming connections from other clients
        threading.Thread(target=common_utils.recv_msg, args=(conn,addr)).start()
