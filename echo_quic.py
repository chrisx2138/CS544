from typing import Coroutine, Callable, Optional

class QuicStreamEvent:
    def __init__(self, stream_id, data, end_stream):
        self.stream_id = stream_id
        self.data = data
        self.end_stream = end_stream
        
class EchoQuicConnection:
    def __init__(self, send: Coroutine[QuicStreamEvent, None, None], 
                 receive: Coroutine[None, None, QuicStreamEvent],
                 close: Optional[Callable[[], None]], 
                 new_stream: Optional[Callable[[], int]]):
        self.send = send
        self.receive = receive
        self.close = close
        self.new_stream = new_stream
        self.client_connections = []

    def add_client_connection(self, handler):
        self.client_connections.append(handler)

    async def broadcast(self, data: bytes):
        for client in self.client_connections:
            await client.send_data_to_client(data)
