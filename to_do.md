## Scenarios to handle
[] How to route client's requests. Leader? What if leader has crashed? - Route to netwrok server and nw server routes to a random alive server in the required cluster
[] Do we need to handle the scenario when leader crashes after executing client's command but before responding? - 
[] Do we need to handle scenario when leader crashes before replicating it on others or does the client have to retry?
[] Lock table? 
[] Read input from file 
[] Node restoration from failure. - Read from disk file

## Scenarios tested
[X] Single intra-shard operation
[X] Single intra-shard operation, third server joins after few operations
[] (DOES NOT WORK IN SOME RANDOM SCENARIO. NOT CONSISTENTLY REPRODUCIBLE) Single intra-shard operation, third server joins after few operations and new request is sent immediately. 
Say servers 1,2 finish few operations. Send another request on client and immediately after that start the 3rd server. Seems like that request isn't sent. 
[X] (REQUEST IS LOST. NEEDS TO BE RESENT) Current leader crashes. Intra-shard operation after leader crash before new leader is elected. 
[X] Current leader crashes. Intra-shard operation after leader crash after new leader is elected.
[X] (NO PROGRESS ON REQUEST. RESUMES ONCE MAJORITY ARE UP) Majority of servers crash 
[] (DOES NOT WORK SINCE LEADER IS NONE) Send intra-shard operation before leader is determined i.e leaderId = None
[X] Concurrent intra-shard transactions on different items for same set of servers
[X] Concurrent intra-shard transactions on same items
[] (FAILS) Concurrent intra-shard transactions on different items on different sets of servers
[] (FAILS) Concurrent intra-shard transactions on different items on same set of servers 

Unending election for 

