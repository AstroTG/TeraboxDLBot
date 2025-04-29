import asyncio
import hashlib
import inspect
import os
from typing import BinaryIO, Optional, Tuple
from collections import defaultdict

from pyrogram import Client
from pyrogram.raw.types import InputFileBig, InputFile
from pyrogram.types import InputMediaUploadedDocument
from pyrogram.utils import get_appropriated_part_size



import asyncio
import hashlib
import inspect
import logging
import math
import os
from collections import defaultdict
from fileinput import filename
from typing import (
    AsyncGenerator,
    Awaitable,
    BinaryIO,
    DefaultDict,
    List,
    Optional,
    Tuple,
    Union,
)

import asyncio
import hashlib
import inspect
import logging
import math
import os
from collections import defaultdict
from fileinput import filename
from typing import (
    AsyncGenerator,
    Awaitable,
    BinaryIO,
    DefaultDict,
    List,
    Optional,
    Tuple,
    Union,
)

from pyrogram import Client, errors, raw
from pyrogram.session import Session

from pyrogram.types import (
    InputMediaUploadedDocument,
    InputMediaUploadedPhoto,
    InputDocument,
    InputFile,
    InputPeerPhotoFileLocation,
    InputPhotoFileLocation,
)

log: logging.Logger = logging.getLogger("pyrogram")

TypeLocation = Union[
    InputDocument,
    InputPeerPhotoFileLocation,
    InputPhotoFileLocation,
]


class UploadSender:
    client: Client
    file_id: int  # Unique file identifier
    part_count: int
    stride: int
    previous: Optional[asyncio.Task]
    loop: asyncio.AbstractEventLoop
    is_big: bool

    def __init__(
        self,
        client: Client,
        file_id: int,
        part_count: int,
        big: bool,
        index: int,
        stride: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.client = client
        self.file_id = file_id
        self.part_count = part_count
        self.stride = stride
        self.previous = None
        self.loop = loop
        self.index = index
        self.is_big = big # Store if file is big
        self.current_part = index

    async def next(self, data: bytes) -> None:
        if self.previous:
            await self.previous
        self.previous = self.loop.create_task(self._next(data))

    async def _next(self, data: bytes) -> None:
        log.debug(
            f"Sending file part {self.current_part}/{self.part_count}"
            f" with {len(data)} bytes"
        )
        try:
            if self.is_big:
                await self.client.invoke(
                    raw.functions.upload.SaveBigFilePart(
                        file_id=self.file_id,
                        file_part=self.current_part,
                        file_total_parts=self.part_count,
                        bytes=data,
                    )
                )

            else:

                await self.client.invoke(
                    raw.functions.upload.SaveFilePart(
                        file_id=self.file_id,
                        file_part=self.current_part,
                        bytes=data,
                    )
                )
        except errors.FloodWait as e:
            log.warning(f"FloodWait encountered, sleeping for {e.value} seconds")
            await asyncio.sleep(e.value)
            # Retry the upload after waiting
            await self._next(data)
            return

        self.current_part += self.stride


    async def disconnect(self) -> None:
        if self.previous:
            await self.previous
        # Pyrogram's Client handles connection management automatically
        # No explicit disconnect is needed here.
        pass # No need to disconnect

class ParallelTransferrer:
    client: Client
    loop: asyncio.AbstractEventLoop
    dc_id: int
    senders: Optional[List[Union["UploadSender"]]]  # Forward declaration
    upload_ticker: int
    auth_key: str  # Changed from AuthKey to str

    def __init__(self, client: Client, dc_id: Optional[int] = None) -> None:
        self.client = client
        self.loop = asyncio.get_event_loop()
        self.dc_id = dc_id or self.client.session.dc_id
        self.auth_key = client.session.auth_key_data.hex()
        # self.auth_key = (  # Pyrogram handles auth key internally
        #     None
        #     if dc_id and self.client.session.dc_id != dc_id
        #     else self.client.session.auth_key
        # )
        self.senders = None
        self.upload_ticker = 0

    async def _cleanup(self) -> None:
        if self.senders: # Check if senders exist
            await asyncio.gather(*[sender.disconnect() for sender in self.senders])
            self.senders = None

    @staticmethod
    def _get_connection_count(
        file_size: int, max_count: int = 20, full_size: int = 100 × 1024 × 1024
    ) -> int:
        if file_size > full_size:
            return max_count
        return math.ceil((file_size / full_size) * max_count)

    async def _init_upload(
        self, connections: int, file_id: int, part_count: int, big: bool
    ) -> None:
        self.senders = [
            await self._create_upload_sender(file_id, part_count, big, 0, connections),
            *await asyncio.gather(
                *[
                    self._create_upload_sender(file_id, part_count, big, i, connections)
                    for i in range(1, connections)
                ]
            ),
        ]

    async def _create_upload_sender(
        self, file_id: int, part_count: int, big: bool, index: int, stride: int
    ) -> "UploadSender":  # Use forward reference for UploadSender

        from .upload_sender import UploadSender #Local import to prevent circular dependency

        return UploadSender(
            self.client,
            file_id,
            part_count,
            big,
            index,
            stride,
            loop=self.loop,
        )

    async def _create_sender(self) -> None: # Removed return type
        # dc = await self.client._get_dc(self.dc_id) # Removed as this can't be called like telethon
        # sender = MTProtoSender(self.auth_key, loggers=self.client._log)  # Not needed in Pyrogram
        # await sender.connect(  # Pyrogram manages connection
        #     self.client._connection(
        #         dc.ip_address,
        #         dc.port,
        #         dc.id,
        #         loggers=self.client._log,
        #         proxy=self.client._proxy,
        #     )
        # )
        # if not self.auth_key:
        #     log.debug(f"Exporting auth to DC {self.dc_id}")
        #     auth = await self.client(ExportAuthorizationRequest(self.dc_id))
        #     self.client._init_request.query = ImportAuthorizationRequest(
        #         id=auth.id, bytes=auth.bytes
        #     )
        #     req = InvokeWithLayerRequest(LAYER, self.client._init_request)
        #     await sender.send(req)
        #     self.auth_key = sender.auth_key
        # return sender
        pass
    parallel_transfer_locks: defaultdict[int, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())

def stream_file(file_to_stream: BinaryIO, chunk_size=1024):
    while True:
        data_read = file_to_stream.read(chunk_size)
        if not data_read:
            break
        yield data_read


async def _internal_transfer_to_telegram(
    client: Client,
    response: BinaryIO,
    progress_callback: callable,
    file_name: str = None,
) -> Tuple[InputFile, int]:
    file_id = int(hashlib.sha256(os.urandom(32)).hexdigest(), 16) % 10**8 #generate a random file ID
    file_size = os.path.getsize(response.name)
    part_size = get_appropriated_part_size(file_size)

    is_large = file_size > 10 × 1024 × 1024 #10MB

    parts = []
    part_num = 0

    hash_md5 = hashlib.md5()

    async with parallel_transfer_locks[client.me.id]:
        for data in stream_file(response, chunk_size=part_size):
            if progress_callback:
                r = progress_callback(response.tell(), file_size)
                if inspect.isawaitable(r):
                    await r
            if not is_large:
                hash_md5.update(data)

            parts.append((part_num, data))
            part_num += 1

        if is_large:
            file = InputFileBig(id=file_id, parts=part_num, name=file_name if file_name else "upload")
        else:
            file = InputFile(id=file_id, parts=part_num, name=file_name if file_name else "upload", md5_checksum=hash_md5.hexdigest())

        for part_num, data in parts:
            await client.upload_part(file_id, part_num, data)


    return file, file_size


async def upload_file(
    client: Client,
    file: BinaryIO,
    progress_callback: callable = None,
    file_name: str = None,
) -> InputFile:
    res = (
        await _internal_transfer_to_telegram(client, file, progress_callback, file_name)
    )[0]
    return res
