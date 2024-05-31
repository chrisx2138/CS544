import asyncio
from aioquic.asyncio import connect, serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived
from typing import Optional, Dict, Callable, Coroutine
from aioquic.tls import SessionTicket

import json

from echo_quic import EchoQuicConnection, QuicStreamEvent
import echo_server, echo_client

ALPN_PROTOCOL = "echo-protocol"

def build_server_quic_config(cert_file, key_file) -> QuicConfiguration:
    configuration = QuicConfiguration(
        alpn_protocols=[ALPN_PROTOCOL], 
        is_client=False
    )
    configuration.load_cert_chain(cert_file, key_file)
  
    return configuration

def build_client_quic_config(cert_file = None):
    configuration = QuicConfiguration(alpn_protocols=[ALPN_PROTOCOL], 
                                      is_client=True)
    if cert_file:
        configuration.load_verify_locations(cert_file)
  
    return configuration

SERVER_MODE = 0
CLIENT_MODE = 1

class AsyncQuicServer(QuicConnectionProtocol):
    client_connections = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._handlers: Dict[int, EchoServerRequestHandler] = {}
        self._client_handler: Optional[EchoClientRequestHandler] = None
        self._is_client: bool = self._quic.configuration.is_client
        self.username = None
        if self._is_client:
            self._client_handler = EchoClientRequestHandler(
                authority=self._quic.configuration.server_name,
                connection=self._quic,
                protocol=self,
                scope={},
                stream_ended=False,
                stream_id=None,
                transmit=self.transmit
            )
        else:
            AsyncQuicServer.client_connections.append(self)

    def set_username(self, username):
        self.username = username
        if self._client_handler:
            self._client_handler.set_username(username)

    def remove_handler(self, stream_id):
        self._handlers.pop(stream_id)

    def _broadcast_to_clients(self, message_data):
        for client in AsyncQuicServer.client_connections:
            if client != self:
                for handler in client._handlers.values():
                    asyncio.create_task(handler.send_data_to_client(message_data))

    def _quic_client_event_dispatch(self, event):
        if isinstance(event, StreamDataReceived):
            self._client_handler.quic_event_received(event)

    def _quic_server_event_dispatch(self, event):
        handler = None
        if isinstance(event, StreamDataReceived):
            if event.stream_id not in self._handlers:
                handler = EchoServerRequestHandler(
                    authority=self._quic.configuration.server_name,
                    connection=self._quic,
                    protocol=self,
                    scope={},
                    stream_ended=False,
                    stream_id=event.stream_id,
                    transmit=self.transmit
                )
                self._handlers[event.stream_id] = handler
                handler.quic_event_received(event)
                asyncio.ensure_future(handler.launch_echo())
            else:
                handler = self._handlers[event.stream_id]
                handler.quic_event_received(event)
            self._broadcast_to_clients(event.data)

    def quic_event_received(self, event):
        if self._is_client:
            self._quic_client_event_dispatch(event)
        else:
            self._quic_server_event_dispatch(event)

class SessionTicketStore:
    """
    Simple in-memory store for session tickets.
    """

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)

async def run_server(server, server_port, configuration):  
    print("[svr] Server starting...")  
    await serve(server, server_port, configuration=configuration, 
            create_protocol=AsyncQuicServer,
            session_ticket_fetcher=SessionTicketStore().pop,
            session_ticket_handler=SessionTicketStore().add)
    await asyncio.Future()
              
async def run_client(server, server_port, configuration, username):    
    async with connect(server, server_port, configuration=configuration, 
            create_protocol=AsyncQuicServer) as client:
        client.set_username(username)
        await asyncio.ensure_future(client._client_handler.launch_echo())

class EchoServerRequestHandler:
    def __init__(
        self,
        *,
        authority: bytes,
        connection: AsyncQuicServer,
        protocol: QuicConnectionProtocol,
        scope: Dict,
        stream_ended: bool,
        stream_id: int,
        transmit: Callable[[], None],
    ) -> None:
        self.authority = authority
        self.connection = connection
        self.protocol = protocol
        self.queue: asyncio.Queue[QuicStreamEvent] = asyncio.Queue()
        self.scope = scope
        self.stream_id = stream_id
        self.transmit = transmit

        if stream_ended:
            self.queue.put_nowait({"type": "quic.stream_end"})
        
    def quic_event_received(self, event: StreamDataReceived) -> None:
        self.queue.put_nowait(
            QuicStreamEvent(event.stream_id, event.data, 
                            event.end_stream)
        )

    async def receive(self) -> QuicStreamEvent:
        queue_item = await self.queue.get()
        return queue_item
    
    async def send(self, message: QuicStreamEvent) -> None:
        self.connection.send_stream_data(
                stream_id=message.stream_id,
                data=message.data,
                end_stream=message.end_stream
        )
        
        self.transmit()
        
    def close(self) -> None:
        self.protocol.remove_handler(self.stream_id)
        self.connection.close()
        
    async def launch_echo(self):
        qc = EchoQuicConnection(self.send, 
                self.receive, self.close, None)
        await echo_server.echo_server_proto(self.scope, 
            qc)
    
    async def send_data_to_client(self, data: bytes) -> None:
        new_stream_id = self.protocol._quic.get_next_available_stream_id()
        message = QuicStreamEvent(new_stream_id, data, False)
        await self.send(message)
        
class EchoClientRequestHandler(EchoServerRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = 'Unknown'
        
    def set_username(self, username):
        self.username = username
        
    def get_next_stream_id(self) -> int:
        return self.connection.get_next_available_stream_id()
    
    async def launch_echo(self):
        qc = EchoQuicConnection(self.send, 
                self.receive, self.close, 
                self.get_next_stream_id)
        await echo_client.echo_client_proto(self.scope, 
            qc, self.username)
