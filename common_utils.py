import threading
from time import sleep

def handle_client_msg(conn, data):
    sleep(3)
    data = data.decode()
    words = data.split()

    try:
        # TODO - Add handling here 
        print(f"Received message from client: {data}")
    except:
	    print("Exception in handling client message")

def recv_msg(conn, addr):
	while True:
		try:
			data = conn.recv(1024)
		except:
			break
		if not data:
			conn.close()
			break
        # Spawn new thread for every msg to ensure IO is non-blocking
		threading.Thread(target=handle_client_msg, args=(conn, data)).start()


