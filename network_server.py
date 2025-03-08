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
from common_utils import (
    send_msg, get_servers_in_cluster, MessageType, ClientRequestMessage,
    get_cluster_from_dataitem ,get_cluster
)
import random

server_socks = {}
client_socks = {}
alive_servers = {}


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

    command = data["command"]
    from_account = int(command.split(",")[0])
    to_account = int(command.split(",")[1])

    from_cluster = (from_account - 1) // 1000 + 1
    to_cluster = (to_account - 1) // 1000 + 1
    amount = float(command.split(",")[2])

    if from_cluster == to_cluster:
        # intra-shard

        # create CLIENT_REQUEST message to random alive server in the cluster
        # send the message to the server
        
        dest_id = random.choice(get_servers_in_cluster(from_cluster))

        while alive_servers.get(dest_id, False) == False:
            dest_id = random.choice(get_servers_in_cluster(from_cluster))
            
        #dest_id = 1
        print(f"[DEBUG] Forwarding intra-shard message to server {dest_id}")
        msg = ClientRequestMessage(command, data["client_id"], dest_id, data["trans_id"])
        send_msg(server_socks[dest_id], msg.get_message())

    else:
        if (data["msg_type"] == "client_commit"):
            for i in get_servers_in_cluster(from_cluster):
                if (alive_servers.get(i, False) == True):
                    send_msg(server_socks[i], data)

            for i in get_servers_in_cluster(to_cluster):
                if (alive_servers.get(i, False) == True):
                    send_msg(server_socks[i], data)
        else:
            # cross-shard
            # create CLIENT_REQUEST message to random alive server in the cluster
            # send the message to the server
            
            dest_id1 = random.choice(get_servers_in_cluster(from_cluster))
            while alive_servers.get(dest_id1, False) == False:
                dest_id1 = random.choice(get_servers_in_cluster(from_cluster))

            dest_id2 = random.choice(get_servers_in_cluster(to_cluster))
            while alive_servers.get(dest_id2, False) == False:
                dest_id2 = random.choice(get_servers_in_cluster(to_cluster))

            msg = ClientRequestMessage(command, data["client_id"], dest_id1, data["trans_id"])
            send_msg(server_socks[dest_id1], msg.get_message())
            msg = ClientRequestMessage(command, data["client_id"], dest_id2, data["trans_id"])
            send_msg(server_socks[dest_id2], msg.get_message())
            print(f"[DEBUG] Forwarding inter-shard message to server {dest_id1} and {dest_id2}")


def handle_server_msg(conn, data):
    global server_socks
    global client_socks
    global alive_servers

    try:
        if data["msg_type"] == MessageType.SERVER_INITIALIZE:
            # Init: Connected to server <node_id>
            node_id = int(data["node_id"])
            server_socks[node_id] = conn
            alive_servers[node_id] = True
            print(f"[CONNECTION] Connected to server {node_id}")

        elif data["msg_type"] == MessageType.CLIENT_INITIALIZE:
            # Init: Connected to client <client_id>
            client_id = int(data["node_id"])
            client_socks[client_id] = conn
            print(f"[CONNECTION] Connected to client {client_id}")

        elif data["msg_type"] == MessageType.CLIENT_REQUEST_INIT:
            # Forward request to any random alive server in the cluster
            forward_msg(data)

        elif data["msg_type"] == MessageType.PRINT_BALANCE:
            print(f"[DEBUG] Received print balance request: {data}")
            # Send message to all alive servers in corresponding cluster
            cluster = get_cluster_from_dataitem(data["command"])
            for i in get_servers_in_cluster(cluster):
                if (alive_servers.get(i, False) == True):
                    send_msg(server_socks[i], data)

        elif data["msg_type"] == MessageType.BALANCE_RESPONSE:
            # Send response to client
            dest_id = data["client_id"]
            if dest_id not in client_socks:
                print(f"[CONNECTION] client {dest_id} not connected")
            else:
                print(f"[DEBUG] Forwarding message to client {dest_id}")
                send_msg(client_socks[dest_id], data)

        elif data["msg_type"] == "server_exit":
            # Server exit: Server <node_id> has exited
            node_id = int(data["node_id"])
            alive_servers[node_id] = False
            print(f"[CONNECTION] Server {node_id} has exited")

        elif data["msg_type"] == "client_response":
            dest_id = data["dest_id"]
            if dest_id not in client_socks:
                print(f"[CONNECTION] client {dest_id} not connected")
            else:
                print(f"[DEBUG] Forwarding message to client {dest_id}")
                send_msg(client_socks[dest_id], data)

        elif data["msg_type"] == "client_commit":
            forward_msg(data)

        # Forward message to destination server in the cluster
        else:
            dest_id = data["dest_id"]
            src_id = data["sender_id"]
            print(f"[DEBUG] Forwarding message from server {src_id} to server {dest_id}")
            # print(f"Link status: {config.LINKS}")
            
            # Don't forward if server is not alive or link is down
            if dest_id not in server_socks or alive_servers[dest_id] == False or \
                config.LINKS.get((src_id, dest_id), True) == False or \
                config.LINKS.get((dest_id, src_id), True) == False:
                print(f"[CONNECTION] Server {dest_id} not connected")
            else:
                print(
                    f"[DEBUG] Forwarding message of type {data['msg_type']} to server {dest_id}")
                send_msg(server_socks[dest_id], data)
    except:
        print("[ERROR] Exception in handling server message at network server")


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
                threading.Thread(target=handle_server_msg,
                                 args=(conn, data)).start()
            except json.JSONDecodeError:
                print("[ERROR] Error in decoding JSON")
                break
            except:
                print(
                    "[ERROR] Exception in handling server message at network server")
                break


def get_user_input():
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]
        print(cmd)
        if cmd == "exit":
            # close all client sockets
            for sock in out_socks:
                sock[0].close()
            stdout.flush()
            # exit program with status 0
            _exit(0)

        elif cmd == "fail_node":
            # failNode <node_id>
            node_id = int(user_input.split()[1])
            #print(out_socks , " output socket")
            # kill the server node with the given node_id
            for sock, addr in out_socks:
                if addr[1] == node_id:
                    sock.close()
                    print(
                        f"[CONNECTION] Killed server node with node_id: {node_id}")
                    alive_servers[node_id] = False
                    break
                
        elif cmd == "fail_node_links":
            # Fail all links to the given node_id
            node_id = int(user_input.split()[1])
            servers = get_servers_in_cluster(get_cluster(node_id))
            for i in servers:
                if i != node_id:
                    if i < node_id:
                        config.LINKS[(i, node_id)] = False
                    else:
                        config.LINKS[(node_id, i)] = False
                    print(
                        f"[CONNECTION] Killed link between server {i} and server {node_id}")
                    
        elif cmd == "fix_node_links":
            # Fix all links to the given node_id
            node_id = int(user_input.split()[1])
            servers = get_servers_in_cluster(get_cluster(node_id))
            for i in servers:
                if i != node_id:
                    if i < node_id:
                        config.LINKS[(i, node_id)] = True
                    else:
                        config.LINKS[(node_id, i)] = True
                    print(
                        f"[CONNECTION] Fixed link between server {i} and server {node_id}")

        elif cmd == "fail_link":
            # failLink <node_id1> <node_id2>
            node_id1 = int(user_input.split()[1])
            node_id2 = int(user_input.split()[2])
            # kill the link between the two servers with the given node_id1 and node_id2
            # Update the status of the link between the two servers from config dictionary
            if node_id1 < node_id2:
                config.LINKS[(node_id1, node_id2)] = False
                print(
                    f"[CONNECTION] Killed link between server {node_id1} and server {node_id2}")
            else:
                config.LINKS[(node_id2, node_id1)] = False
                print(
                    f"[CONNECTION] Killed link between server {node_id2} and server {node_id1}")

        elif cmd == "fix_link":
            # fixLink <node_id1> <node_id2>
            node_id1 = int(user_input.split()[1])
            node_id2 = int(user_input.split()[2])
            # fix the link between the two servers with the given node_id1 and node_id2
            # Update the status of the link between the two servers from config dictionary
            if node_id1 < node_id2:
                config.LINKS[(node_id1, node_id2)] = True
                print(
                    f"[CONNECTION] Fixed link between server {node_id1} and server {node_id2}")
            else:
                config.LINKS[(node_id2, node_id1)] = True
                print(
                    f"[CONNECTION] Fixed link between server {node_id2} and server {node_id1}")


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
        threading.Thread(target=recv_msg, args=(conn, addr)).start()
