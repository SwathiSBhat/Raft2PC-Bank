'''
Gives commands to a server node part of a cluster.
Client knows the mapping of account shards to server nodes.
'''

from sys import argv, stdout
from os import _exit
import socket
import config
import threading
from common_utils import send_msg, MessageType
from constants import TransactionStatus
import json
from rich.table import Table

# maintain list of transactions and their status
transactions = {}
# maintain list of watchdogs conditionals for each transaction
watchdogs = {}

def handle_server_msg(conn, data):
    global trans_id
    global prev_status_id
    global transactions
    
    data = json.loads(data)
    # If prepare status received from server for 2PC, send commit or abort based on how clusters have responded
    if ("prepare_status" in data):
        with lock:
            # If this is the first response, store the prepare status
            if (data["trans_id"] not in prev_status_id):
                prev_status_id[data["trans_id"]] = data["prepare_status"]
            else:
                # If both clusters have responded with a true, send commit
                if (prev_status_id[data["trans_id"]] and data["prepare_status"] == True):
                    print("PREPARE STATUS: YES from both the clusters")
                    msg = {"msg_type": "client_commit",
                           "command": data["command"], "client_id": cid, "trans_id": data["trans_id"], "commit": True}
                    send_msg(network_sock, msg)
                # Else, send abort
                else:
                    print(
                        f"PREPARE STATUS: NO from one of the clusters so transaction failed for : {data['command']}")
                    msg = {"msg_type": "client_commit",
                           "command": data["command"], "client_id": cid, "trans_id": data["trans_id"], "commit": False}
                    send_msg(network_sock, msg)
                del prev_status_id[data["trans_id"]]
        return

    if data["msg_type"] == MessageType.BALANCE_RESPONSE:
        print(
            f"Balance of account {data['account_id']} on server {data['server_id']} is {data['balance']}")
        return

    elif data["msg_type"] == MessageType.CLIENT_RESPONSE:
        transaction_id = data['trans_id']
        
        with lock:
            if transaction_id in transactions and transactions[transaction_id] == TransactionStatus.PENDING:
                if data['status']:
                    transactions[transaction_id] = TransactionStatus.SUCCESS
                else:
                    transactions[transaction_id] = TransactionStatus.FAILURE
                    
                # Notify the condition variable so the watchdog thread stops waiting
                if transaction_id in watchdogs:
                    with watchdogs[transaction_id]:
                        watchdogs[transaction_id].notify_all()
                        
        print(f"Response from server: {data}")

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
            
def transaction_watchdog(transactionid, msg, timeout=8*config.NETWORK_DELAY):
    '''
    Retry transaction if no response received from server within timeout
    '''
    global watchdogs
    
    condition = threading.Condition()
    
    # Store condition for transaction
    with lock:
        watchdogs[transactionid] = condition 
        
    with condition:
        success = condition.wait(timeout)
        if not success:
            print(f"Transaction {transactionid} timed out. Retrying...")
            # Retry transaction
            send_msg(network_sock, msg)
            # restart the watchdog
            threading.Thread(target=transaction_watchdog, args=(transactionid, msg)).start()
        else:
            print(f"Transaction {transactionid} completed successfully.")
            # Remove the condition from the dictionary
            with lock:
                del watchdogs[transactionid]

def get_user_input():
    global trans_id
    global transactions
    
    while True:
        # wait for user input
        user_input = input()
        cmd = user_input.split()[0]

        if cmd == "exit":
            stdout.flush()
            # exit program with status 0
            _exit(0)

        # If command is print_balance, print balance of account
        # from all servers in the cluster
        elif cmd == "print_balance":
            msg = {"msg_type": MessageType.PRINT_BALANCE,
                   "command": user_input.split()[1], "client_id": cid}

        else:
            # Transaction ID = clientId_transId
            with lock:
                temp_id = trans_id
                trans_id += 1
            transactionid = str(cid) + "_" + str(temp_id)
            msg = {"msg_type": "client_request_init", "command": user_input,
                   "client_id": cid, "trans_id": transactionid}
            with lock:
                # set transaction status to pending
                transactions[transactionid] = TransactionStatus.PENDING
                
            # start timer watchdog
            threading.Thread(target=transaction_watchdog, args=(transactionid, msg)).start()

        # print(f"Sending message to server: {msg}")
        send_msg(network_sock, msg)


if __name__ == "__main__":

    cid = int(argv[1])
    trans_id = 0
    prev_status_id = {}
    lock = threading.Lock()
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
    threading.Thread(target=recv_msg, args=(
        network_sock, (CLIENT_IP, config.NETWORK_SERVER_PORT))).start()

    # Send test message to network server
    msg = {"msg_type": "init_client", "node_id": cid}
    send_msg(network_sock, msg)
