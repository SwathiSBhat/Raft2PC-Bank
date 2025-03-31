# Raft2PC-Bank
## Objective
This project implements a fault-tolerant distributed transaction processing system that supports a simple banking application. The data for users with ID ranging from 1-3000 is sharded across 3 clusters. Each cluster consists of 3 servers to replicate the data to ensure fault-tolerance. 
The application mainly supports 2 kinds of transactions - `intra-shard` and `cross-shard`. `Intra-shard` transaction occurs between users whose data is part of the same shard while `Cross-shard` transaction occurs between users whose data is stored across different shards.

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


## Architecture
The architecture consists of multiple clients (the diagram shows just 3), a network server and 3 clusters of servers each containing 3 servers. All messages go through the network server. The network server provides commands to create network partititoning and fail servers. 
<img width="576" alt="Screenshot 2025-03-30 at 7 06 21 PM" src="https://github.com/user-attachments/assets/c0f83ec5-ac9d-43c5-ab6c-eea325fd7116" />

