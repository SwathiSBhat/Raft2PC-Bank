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

**[FAILURE]** - print_committed_txns prints 1500,2,1 even though that's aborted

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
**[FAILURE]** 
In this case, 1 still keeps waiting to get response, client retries and the retry fails.
Then bring server 2 back up and wait for it's log to get updated.
Then bring server 3 back up. It gets stuck in loop in line 486. Any further intra-shard transactions does not go to server 3.
print_committed_txns prints 11,1200,1 in servers 4,5,6 

### Concurrent intra-shard transactions on same items with 


### Partition leader + 2 nodes and intra-shard transaction
**Output**
**[FAILURE]**
If request goes to partitioned leader, client retries and works in the majority nodes.
But on fixing the link for the partitioned server, it gives the error:
```
Traceback (most recent call last):
  File "/Users/swathi/.pyenv/versions/3.8.10/lib/python3.8/threading.py", line 932, in _bootstrap_inner
    self.run()
  File "/Users/swathi/.pyenv/versions/3.8.10/lib/python3.8/threading.py", line 870, in run
    self._target(*self._args, **self._kwargs)
  File "server.py", line 30, in handle_server_msg
    raft.handle_message(data)
  File "/Users/swathi/Documents/UCSB/CS 271/Project/Raft2PC-Bank/consensus_module.py", line 166, in handle_message
    self.handle_append_entries(msg)
  File "/Users/swathi/Documents/UCSB/CS 271/Project/Raft2PC-Bank/consensus_module.py", line 489, in handle_append_entries
    cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(self.log[j_temp].command.split(','))]#list(map(int, self.log[j_temp].command.split(",")))
  File "/Users/swathi/Documents/UCSB/CS 271/Project/Raft2PC-Bank/consensus_module.py", line 489, in <listcomp>
    cmd = [int(x) if i < 2 else float(x) for i, x in enumerate(self.log[j_temp].command.split(','))]#list(map(int, self.log[j_temp].command.split(",")))
ValueError: invalid literal for int() with base 10: ''
```

### Partition leader + 2 nodes on both clusters and cross-shard

### Partition leader with a node + another node and intra-shard transaction

### Intra-shard with amt > balance


### Cross-shard with amt > balance for 1 of them
Should abort

### Intra-shard with amt = balance

### Cross-shard with amt = balance

### Partition off non-leader and ensure request going to partitioned node is retried

### Recovery from partitioning after partitioning leader

### Recovery from partitioning after partitioning non-leader node
