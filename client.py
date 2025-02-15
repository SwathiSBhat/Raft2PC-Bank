'''
Gives commands to a server node part of a cluster.
Client knows the mapping of account shards to server nodes.
'''

from sys import argv, stdout, _exit
import socket
import config
import threading
from common_utils import send_msg, MessageType

def handle_server_msg(conn, data):    
    data = data.decode()
    print(f"Response from server: {data}")

def recv_msg(conn, addr):
    while True:
        try:
            data = conn.recv(1024)
        except:
            break
        if not data:
            conn.close()
            break

        try:
            # Spawn new thread for every msg to ensure IO is non-blocking
            threading.Thread(target=handle_server_msg, args=(conn, msg)).start()
        except:
            print("Exception in handling message at server {pid}")
            break

def get_user_input():
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]

        if cmd == "exit":
            stdout.flush()
			# exit program with status 0
            _exit(0)

        msg = {"msg_type" : "client_request", "command" : user_input, "client_id" : cid}
        send_msg(network_sock, msg)


if __name__ == "__main__":

    cid = int(argv[1])

    CLIENT_IP = socket.gethostname()
    CLIENT_PORT = config.CLIENT_PORTS[int(cid)]

    # Commands for exit, inter-shard and intra-shard
    threading.Thread(target=get_user_input).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((CLIENT_IP, CLIENT_PORT))

    # Connect to network server
    network_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    network_sock.connect((CLIENT_IP, config.NETWORK_SERVER_PORT))
    threading.Thread(target=recv_msg, args=(network_sock, (CLIENT_IP, config.NETWORK_SERVER_PORT))).start()
    
    # Send test message to network server
    msg = {"msg_type": "init_client", "node_id": cid}
    send_msg(network_sock, msg)