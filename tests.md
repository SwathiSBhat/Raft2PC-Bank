## TODOs
1. Partitioning - Done
2. Performance and throughput functions
3. PrintDataStore function - Done
4. Support float for amt - Done
5. Fix transactions with amt = balance
6. Elections are overlapping a lot - Done
7. print_committed_txns prints transactions aborted due to 2PC but present in txt files

## Tests
### 1. Concurrent intra-shard with independent items in single cluster
client 1:
1,2,1
client 2:
4,5,1
client 3:
7,8,1

**Output**
1 - 9
2 - 11
4 - 9
5 - 11
7 - 9
8 - 11

### Concurrent intra-shard with independent items in different clusters
client 1:
100,101,1
client 2:
1100,1101,1
client 3:
2200,2201,1

**Output**
100 - 9
101 - 11
1100 - 9
1101 - 11
2200 - 9
2201 - 11

### Concurrent intra-shard with same items in single cluster
client 1:
1500,1501,1
client 2:
1500,1502,1
client 3:
1503,1500,1

**Output**
1500 - 9
1501 - 11
1502 - 11
1503 - 9

### Simple cross-shard transaction
client 1:
10,1010,1

**Output**
10 - 9
1010 - 11

### Concurrent cross-shard transactions on different items
client 1:
200,1200,1
client 2:
1300,2300,1
client 3:
2500,500,1

**Output**
200 - 9
1200 - 11
1300 - 9
2300 - 11
2500 - 9
500 - 11

### Concurrent cross-shard transactions on same items
client 1:
20,1020,1
client 2:
1020,30,1
client 3:
30,2020,1

**Output**
If 1 and 2 get aborted
20 - 10
30 - 9
1020 - 10
2020 - 11

### Concurrent cross-shard transactions on same items
client 1:
60,1600,1
client 2:
1600,66,1
client 3:
1800,55,1

**Output**
If request 2 gets aborted
55 - 11
60 - 9
66 - 10
1600 - 11
1800 - 9

### Concurrent intra-shard and cross-shard accessing different items
Client 1:
11,22,1
Client 2:
1222,2333,1
Client 3:
33,44,1

### Concurrent intra-shard and cross-shard accessing same items
Client 1:
1,2,1 (press enter first)
Client 2:
1500,2,1 (press enter second)
**Output**
If 1500,2,1 fails
1 - 9
2 - 11
1500 - 10

Client 1:
1,2,1 (press enter second)
Client 2:
2,1500,1 (press enter first)
**Output**
If both go through
1 - (9-1) = 8
2 - (11-1+1) = 11
1500 - 11

### Leader fails and then initiate concurrent transactions (intra-shard and cross-shard)
Client 1:
3,4,1
Client 2:
3,1300,1
**Output**
If second txn gets aborted
3 - 9
4 - 11
1300 - 10

### 2 nodes fail and then initiate intra-shard
**Output** 
No progress is made. Once nodes come back alive, transaction resumes

### 2 nodes fail and initiate cross-shard
Kill server 2,3, ensure 1 is the leader
Client 1:
11,1200,1
**Output**
1 should make no progress and wait until majority to send a YES/NO to client
Once 2 is up, it sends a YES for 2PC and executes txn. 3 also gets updated

### Concurrent intra-shard transactions on same items with 


### Partition leader + 2 nodes and intra-shard transaction
If server 3 is leader and it gets partitioned, send 1,2,1 from client
**Output**
If request goes to partitioned leader, client retries and works in the majority nodes to make progress.
1 - 9
2 - 11

### Partition leader + 2 nodes on both clusters and cross-shard
**Output**
A new leader should get elected and make progress. If the request goes to the old leader, it should timeout and the client will retry eventually reaching the group of 2 nodes. 

### Partition leader with a node + another node and intra-shard transaction
**Output**
Another node which is partitioned continuously tries to become leader but does not get enough votes. Leader and other node make progress.

### Intra-shard with amt > balance
**Output**
Aborts transaction

### Cross-shard with amt > balance for 1 of them
**Output**
Aborts transaction

### Intra-shard with amt = balance
**Output**
Works as expected

### Cross-shard with amt = balance
**Output**
Works as expected

### Partition off non-leader and ensure request going to partitioned node is retried
**Output**
Works fine

### Recovery from partitioning after partitioning leader

### Recovery from partitioning after partitioning non-leader node
