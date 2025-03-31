# Raft2PC-Bank
## Objective
This project implements a fault-tolerant distributed transaction processing system that supports a simple banking application. The data for users with ID ranging from 1-3000 is sharded across 3 clusters. Each cluster consists of 3 servers to replicate the data to ensure fault-tolerance. 
The application mainly supports 2 kinds of transactions - `intra-shard` and `cross-shard`. `Intra-shard` transaction occurs between users whose data is part of the same shard while `Cross-shard` transaction occurs between users whose data is stored across different shards.

**Client shard mapping**
| Cluster    | User IDs |
| -------- | ------- |
| C1  | \[1, 2, 3, ..., 1000\] |
| C2 | \[1001, 1002, 1003, ..., 2000\] |
| C3    | \[2001, 2002, 2003, ..., 3000\] |


### Intra-shard transaction
To process intra-shard transactions, Raft protocol is used to reach consensus for each individual transaction (of the form `x y amt`). The leader checks for 2 conditions:
- there are no locks on data items x and y
- the balance of x is at least equal to amt
If both conditions are met, the leader needs to obtain locks and all other nodes obtain locks too. The leader executes the Raft protocol. Once then entry is committed on the log, the data store is updated. The leader then sends a message back to the client letting the client know that the transaction has been committed. The client waits for a reply from the leader to accept the result. In case the client does not receive a response within a specified time, the client retries the same request.

### Cross-shard transaction
To process cross-shard transactions, 2 Phase-Commit (2PC) protocol is used across the clusters involved in the transaction. 
- The client acts as the co-ordinator for 2PC. The client initiates the request by sending the transaction to the respective clusters which initiate the Raft protocol.
- To prevent concurrent updates to the data items, all servers in both clusters acquire locks on accessed items (item x in one cluster and item y in the other). Upon reaching consensus, the transaction is considered committed, but it does not execute the operation on the data store (as would be normal in Raft). We wait till the transaction is committed. 
- The leader of each cluster sends either a `prepared/yes` or `abort` message back to the transaction coordinator.
- Upon receiving `prepared/yes` messages from both involved clusters, the client (coordinator) sends a commit message to all servers in both clusters. At this point, the transaction is truly considered committed, and the corresponding data store is updated.
- Conversely, if any cluster aborts the transaction or if the transaction coordinator times out, the coordinator will issue an abort message to all servers in both clusters. Now, the transaction is not executed on the data store.
- If the outcome is a commit, each server releases its locks. If the outcome is an abort or if a timeout occurs, the server will not execute the operation and releases its locks. In either scenario, the server sends an Ack message back to the coordinating client.

<img width="441" alt="Screenshot 2025-03-31 at 11 05 09 AM" src="https://github.com/user-attachments/assets/cf239858-1e2a-4e3f-a82e-6621a14724be" />


## Architecture
The architecture consists of multiple clients (the diagram shows just 3), a network server and 3 clusters of servers each containing 3 servers. All messages go through the network server. The network server provides commands to create network partititoning and fail servers. 

<img width="576" alt="Screenshot 2025-03-30 at 7 06 21 PM" src="https://github.com/user-attachments/assets/c0f83ec5-ac9d-43c5-ab6c-eea325fd7116" />

<img width="438" alt="Screenshot 2025-03-31 at 11 04 48 AM" src="https://github.com/user-attachments/assets/fb02a84c-8d36-4c79-ae9f-4c3ff5f59060" />

<img width="680" alt="Screenshot 2025-03-31 at 11 04 58 AM" src="https://github.com/user-attachments/assets/30eb2e06-b84b-4f59-8b35-00164a6747b5" />

## Running the code
The code requires `Python3` to be installed and there are no other dependencies. Follow the below order to start each of the processes in different instances of your terminal.
**NOTE** - Make sure all the files in `/data` folder are empty or deleted before starting the servers. These files store the committed entries on disk based on Raft consensus. 

1. Start network server
```
python3 network_server.py
```
2. Start clients - Syntax is `python3 client.py <client_num>`
```
python3 client.py 1
python3 client.py 2
...
```
3. Start servers - Syntax is `python3 server.py <server_num>`
```
python3 server.py 1
python3 server.py 2
...
python3 server.py 9
```

### Supported commands
1. Printing balance of an account - `print_balance <user id>` prints the balance of user with the given id on all the 3 servers in the cluster it is stored in. 

<img width="257" alt="Screenshot 2025-03-31 at 3 35 15 PM" src="https://github.com/user-attachments/assets/5a124a0f-bd31-4c8a-b90e-5a76727cf7ad" />

2. Intra-shard or cross shard transaction - `sender_id, receiver_id, amount` initiates a transfer of `amount` from the sender to the receiver.

<img width="1099" alt="Screenshot 2025-03-31 at 3 37 32 PM" src="https://github.com/user-attachments/assets/5ed7242b-2692-4aaa-89d5-4b92fc2110b0" />

<img width="1099" alt="Screenshot 2025-03-31 at 3 38 03 PM" src="https://github.com/user-attachments/assets/1c614133-b13c-4e4a-a3dd-d750b3956b62" />

3. Printing committed transactions in Raft log - `print_committed_txns` will print all the committed transactions in the logs of all the servers. This log will be consistent across servers in the same cluster.

<img width="256" alt="Screenshot 2025-03-31 at 3 39 14 PM" src="https://github.com/user-attachments/assets/e39f07c9-bbc6-49d4-b58b-cf38efbd2389" />
<img width="249" alt="Screenshot 2025-03-31 at 3 38 56 PM" src="https://github.com/user-attachments/assets/0994a75e-cbd4-4587-8769-8314dd53a1dd" />

4. Performance - Displays the performance of all transactions initiated from the given client. 

<img width="264" alt="Screenshot 2025-03-31 at 3 39 29 PM" src="https://github.com/user-attachments/assets/16c0d1de-e665-46bc-8ea5-4f78252090d6" />

## Supported scenarios
1. All combinations of concurrent transactions - intra-shard and cross-shard.
2. Servers make progress as long as majority of the servers are up. If not, the client retries after a certain time until a result is obtained.
3. All network partitioning scenarios - If a network partition has a majority of servers, it will make progress and on recovery from partitioning, the partitioned server will update it's log.
4. Recovery from failure and partitioning - The recovered server will automatically update it's log to the latest.

## Contributors


