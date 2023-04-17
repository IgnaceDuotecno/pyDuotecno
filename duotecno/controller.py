"""Main interface to the duotecno bus."""

import asyncio
import logging
import sys
from duotecno.protocol import (
    Packet,
    EV_CLIENTCONNECTSET_3,
    EV_NODEDATABASEINFO_0,
    EV_NODEDATABASEINFO_1,
    EV_NODEDATABASEINFO_2,
)
from duotecno.node import Node


class PyDuotecno:
    """Class that will will do the bus management.

    - send packets
    - receive packets
    - open and close the connection
    """

    writer: asyncio.StreamWriter = None
    reader: asyncio.StreamReader = None
    readerTask: asyncio.Task
    loginOK: asyncio.Event
    nodes: dict

    async def connect(self, host, port, password) -> None:
        """Initialize the connection."""
        self._log = logging.getLogger("pyduotecno")
        self.reader, self.writer = await asyncio.open_connection(host, port)
        self.readerTask = asyncio.Task(self.readTask())
        self.loginOK = asyncio.Event()
        self.nodes = {}
        # TODO encode password
        await self.write("[214,3,8,100,117,111,116,101,99,110,111]")
        await self.loginOK.wait()
        await self.write("[209,0]")

    async def write(self, msg) -> None:
        """Send a message."""
        self._log.debug(f"Send: {msg}")
        msg = f"{msg}{chr(10)}"
        self.writer.write(msg.encode())
        await self.writer.drain()

    async def readTask(self):
        """Reader task."""
        while True:
            tmp = await self.reader.readline()
            tmp = tmp.decode().rstrip()
            if not tmp.startswith("["):
                tmp = tmp.lstrip("[")
            tmp = tmp.replace("\x00", "")
            # log.debug(f"Receive: {tmp}")
            tmp = tmp[1:-1]
            p = tmp.split(",")
            try:
                pc = Packet(int(p[0]), int(p[1]), [int(_i) for _i in p[2:]])
                self._log.debug(f"Receive: {pc}")
            except Exception as e:
                self._log.error(e)
                self._log.error(tmp)
            await self._handlePacket(pc)

    async def _handlePacket(self, packet):
        if isinstance(packet.cls, EV_CLIENTCONNECTSET_3):
            if packet.cls.loginOK == 1:
                self.loginOK.set()
                return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_0):
            for i in range(packet.cls.numNode - 1):
                await self.write(f"[209,1,{i}]")
            return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_1):
            if packet.cls.address not in self.nodes:
                self.nodes[packet.cls.address] = Node(
                    name=packet.cls.nodeName,
                    address=packet.cls.address,
                    index=packet.cls.index,
                    nodeType=packet.cls.nodeType,
                    numUnits=packet.cls.numUnits,
                    writer=self.write,
                )
                await self.nodes[packet.cls.address].requestUnits()
            return
        if hasattr(packet.cls, "address") and packet.cls.address in self.nodes:
            await self.nodes[packet.cls.address].handlePacket(packet.cls)
            return
        print("TODO handle")
