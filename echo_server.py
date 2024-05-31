import asyncio
from typing import Dict
from echo_quic import EchoQuicConnection, QuicStreamEvent
import pdu

async def echo_server_proto(scope: Dict, conn: EchoQuicConnection):
    while True:
        message: QuicStreamEvent = await conn.receive()
        dgram_in = pdu.Datagram.from_bytes(message.data)
        print("[svr] received message: ", dgram_in.msg)
        
        # Broadcast the message to all connected clients
        dgram_out = dgram_in
        dgram_out.mtype |= pdu.MSG_TYPE_DATA_ACK
        rsp_msg = dgram_out.to_bytes()
        await conn.broadcast(rsp_msg)
