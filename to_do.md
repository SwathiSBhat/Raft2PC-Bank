## Scenarios to handle
[] How to route client's requests. Leader? What if leader has crashed? - Route to netwrok server and nw server routes to a random alive server in the required cluster
[] Do we need to handle the scenario when leader crashes after executing client's command but before responding? - 
[] Do we need to handle scenario when leader crashes before replicating it on others or does the client have to retry?
[] Lock table? 
[] Read input from file 
[] Node restoration from failure. - Read from disk file



