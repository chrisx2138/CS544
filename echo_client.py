from typing import Dict
import json
from echo_quic import EchoQuicConnection, QuicStreamEvent
import pdu

async def echo_client_proto(scope: Dict, conn: EchoQuicConnection, username: str):
    print(f'[cli-{username}] starting client')
    
    while True:
        msg = input(f"[cli-{username}] Enter message: ")
        datagram = pdu.Datagram(pdu.MSG_TYPE_DATA, f"{username}: {msg}")
        
        new_stream_id = conn.new_stream()
        qs = QuicStreamEvent(new_stream_id, datagram.to_bytes(), False)
        await conn.send(qs)
        message: QuicStreamEvent = await conn.receive()
        dgram_resp = pdu.Datagram.from_bytes(message.data)
        print(f'[cli-{username}] From {dgram_resp.msg.split(": ")[0]}:', dgram_resp.msg.split(": ")[1])
        
