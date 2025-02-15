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
from time import sleep
import config
import json
from common_utils import send_msg, get_servers_in_cluster, MessageType, ClientRequestMessage
import random

server_socks = {}
client_socks = {}
alive_servers = {};

def forward_msg(data):
    global server_socks
    global alive_servers

    '''
    The command is of the form: <from_account>,<to_account>,<amount>
    Mapping of account id to clusters:
    1-1000 => cluster 1 (servers 1,2,3)
    1001-2000 => cluster 2 (servers 4,5,6)
    2001-3000 => cluster 3 (servers 7,8,9)
    '''
    print(f"Forwarding client request: {data}")
    command = data["command"]
    from_account = int(command.split(",")[0])
    to_account = int(command.split(",")[1])
    
    from_cluster = (from_account - 1) // 1000 + 1
    to_cluster = (to_account - 1) // 1000 + 1
    amount = float(command.split(",")[2])
    print(f"From cluster: {from_cluster}, To cluster: {to_cluster} amount: {amount}")
    print(f"Alive servers: {alive_servers}")

    if from_cluster == to_cluster:
        # intra-shard
        # create CLIENT_REQUEST message to random alive server in the cluster
        # send the message to the server
        dest_id = random.choice(get_servers_in_cluster(from_cluster))

        while alive_servers.get(dest_id, False) == False:
            dest_id = random.choice(get_servers_in_cluster(from_cluster))

        print(f"Forwarding intra-shard message to server {dest_id}")
        msg = ClientRequestMessage(command, data["client_id"], dest_id)
        send_msg(server_socks[dest_id], msg.get_message())
    
    else:
        # inter-shard
        # create CLIENT_REQUEST message to random alive server in the cluster
        # send the message to the server
        dest_id1 = random.choice(get_servers_in_cluster(from_cluster))
        while alive_servers.get(dest_id1, False) == False:
            dest_id1 = random.choice(get_servers_in_cluster(from_cluster))

        dest_id2 = random.choice(get_servers_in_cluster(to_cluster))
        while alive_servers.get(dest_id2, False) == False:
            dest_id2 = random.choice(get_servers_in_cluster(to_cluster))

        print(f"Forwarding inter-shard message to server {dest_id1} and {dest_id2}")
        print(f"data: {data}")  
        msg = ClientRequestMessage(command, data["client_id"], dest_id1)
        send_msg(server_socks[dest_id1], msg.get_message())
        msg = ClientRequestMessage(command, data["client_id"], dest_id2)
        send_msg(server_socks[dest_id2], msg.get_message())
        print(f"Forwarding inter-shard message to server {dest_id1} and {dest_id2}")


def handle_server_msg(conn, data):
    global server_socks
    global client_socks
    global alive_servers

    try:
        if data["msg_type"] == "init":
            # Init: Connected to server <node_id>
            node_id = int(data["node_id"])
            server_socks[node_id] = conn
            alive_servers[node_id] = True
            print(f"Connected to server {node_id}")

        elif data["msg_type"] == "init_client":
            # Init: Connected to client <client_id>
            client_id = int(data["node_id"])
            print(f"Connected to client {client_id}")

        elif data["msg_type"] == "client_request_init":
            # Forward request to any random alive server in the cluster
            forward_msg(data)

        elif data["msg_type"] == "server_exit":
            # Server exit: Server <node_id> has exited
            node_id = int(data["node_id"])
            alive_servers[node_id] = False
            print(f"Server {node_id} has exited")
            
        # Forward message to destination server in the cluster
        else:
            dest_id = data["dest_id"]
            if dest_id not in server_socks or alive_servers[dest_id] == False:
                print(f"Server {dest_id} not connected")
            else:
                print(f"Forwarding message to server {dest_id}")
                send_msg(server_socks[dest_id], data)
    except:
	    print("Exception in handling server message at network server")

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
                data = json.loads(msg)
                # Spawn new thread for every msg to ensure IO is non-blocking
                threading.Thread(target=handle_server_msg, args=(conn, data)).start()
            except json.JSONDecodeError:
                print("Error in decoding JSON")
                break
            except:
                print("Exception in handling server message at network server")
                break

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
        threading.Thread(target=recv_msg, args=(conn,addr)).start()
