'''
Common file for servers 1-9
'''

import config
import socket
import threading
from sys import argv, stdout
from os import _exit
from consensus_module import RaftConsensus
from common_utils import send_msg, MessageType
import json
from time import sleep


def handle_server_msg(conn, data):
    data = json.loads(data)

    # if its a print request, do not add delay
    if data["msg_type"] == MessageType.PRINT_BALANCE:
        balance = raft.state_machine_read(int(data["command"]))
        msg = {"msg_type": MessageType.BALANCE_RESPONSE, "balance": balance,
               "client_id": data["client_id"], "account_id": data["command"], "server_id": pid}
        # send response to network server
        send_msg(network_sock, msg)
        return

    sleep(config.NETWORK_DELAY)
    # try:
    raft.handle_message(data)
    # except:
    #    print("Exception in handling message from network server")


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
                threading.Thread(target=handle_server_msg,
                                 args=(conn, msg)).start()
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

        # used to print the balance of the id
        elif cmd == "print":
            id = int(user_input.split()[1])
            print(raft.state_machine_read(id))
        # TODO - The below commands can be removed once the client is implemented
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
    global network_sock

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
    threading.Thread(target=recv_msg, args=(
        network_sock, (SERVER_IP, config.NETWORK_SERVER_PORT))).start()
    # Send test message to network server
    msg = {"msg_type": "init", "node_id": pid}
    send_msg(network_sock, msg)

    # Create Raft consensus object for current server
    raft = RaftConsensus(pid, network_sock)
