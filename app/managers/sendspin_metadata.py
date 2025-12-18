"""
Sendspin Metadata Client for retrieving now-playing information.

Implements a WebSocket client that connects to a Sendspin server using the
metadata role to receive real-time track information and artwork URLs.

Protocol Reference:
    https://www.sendspin-audio.com/spec/

The client sends a client/hello message requesting the metadata@v1 role,
then listens for server/state messages containing track metadata.
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Protocol version for metadata role
METADATA_ROLE_VERSION = "metadata@v1"

# Reconnection delay after connection failure (seconds)
RECONNECT_DELAY_SECS = 5

# Maximum age of metadata before considered stale (seconds)
METADATA_STALE_THRESHOLD_SECS = 30

# WebSocket ping interval to keep connection alive (seconds)
PING_INTERVAL_SECS = 30


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class TrackMetadata:
    """
    Now-playing track metadata from Sendspin server.

    Attributes:
        title: Track title.
        artist: Artist name.
        album: Album name.
        artwork_url: URL to album artwork image.
        year: Release year (optional).
        track_number: Track number on album (optional).
        track_progress_ms: Current playback position in milliseconds.
        track_duration_ms: Total track duration in milliseconds.
        is_playing: Whether playback is active.
        updated_at: Unix timestamp when metadata was last updated.
    """

    title: str = ""
    artist: str = ""
    album: str = ""
    artwork_url: str = ""
    year: int | None = None
    track_number: int | None = None
    track_progress_ms: int = 0
    track_duration_ms: int = 0
    is_playing: bool = False
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "artwork_url": self.artwork_url,
            "year": self.year,
            "track_number": self.track_number,
            "track_progress_ms": self.track_progress_ms,
            "track_duration_ms": self.track_duration_ms,
            "is_playing": self.is_playing,
            "updated_at": self.updated_at,
        }

    def is_stale(self) -> bool:
        """Check if metadata is older than threshold."""
        return (time.time() - self.updated_at) > METADATA_STALE_THRESHOLD_SECS

    @property
    def progress_percent(self) -> int:
        """Calculate playback progress as percentage (0-100)."""
        if self.track_duration_ms <= 0:
            return 0
        return min(100, int((self.track_progress_ms / self.track_duration_ms) * 100))


class SendspinMetadataClient:
    """
    WebSocket client for Sendspin metadata role.

    Connects to a Sendspin server and subscribes to metadata updates.
    Maintains the latest track metadata for retrieval.

    Usage:
        client = SendspinMetadataClient("ws://192.168.1.100:8080/sendspin")
        client.start()
        ...
        metadata = client.get_metadata()
        ...
        client.stop()
    """

    def __init__(self, server_url: str, client_id: str = "metadata-client") -> None:
        """
        Initialize the metadata client.

        Args:
            server_url: WebSocket URL of the Sendspin server.
            client_id: Unique identifier for this client.
        """
        self.server_url = server_url
        self.client_id = client_id
        self._metadata = TrackMetadata()
        self._connected = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the metadata client in a background thread."""
        if self._running:
            logger.warning(f"Metadata client for {self.server_url} already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_event_loop,
            name=f"sendspin-metadata-{self.client_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"Started metadata client for {self.server_url}")

    def stop(self) -> None:
        """Stop the metadata client."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"Stopped metadata client for {self.server_url}")

    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected

    def get_metadata(self) -> TrackMetadata:
        """
        Get the current track metadata.

        Returns:
            TrackMetadata object with latest now-playing info.
        """
        with self._lock:
            return self._metadata

    def _run_event_loop(self) -> None:
        """Run the asyncio event loop in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connection_loop())
        except Exception as e:
            logger.error(f"Metadata client event loop error: {e}")
        finally:
            self._loop.close()

    async def _connection_loop(self) -> None:
        """Main connection loop with automatic reconnection."""
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.warning(f"Metadata connection failed: {e}")
                self._connected = False

            if self._running:
                logger.info(f"Reconnecting in {RECONNECT_DELAY_SECS}s...")
                await asyncio.sleep(RECONNECT_DELAY_SECS)

    async def _connect_and_listen(self) -> None:
        """Connect to server and listen for metadata updates."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets")
            self._running = False
            return

        logger.info(f"Connecting to {self.server_url}...")

        async with websockets.connect(
            self.server_url,
            ping_interval=PING_INTERVAL_SECS,
        ) as ws:
            self._connected = True
            logger.info(f"Connected to {self.server_url}")

            # Send client/hello to request metadata role
            hello_msg = {
                "type": "client/hello",
                "payload": {
                    "client_id": self.client_id,
                    "supported_roles": [METADATA_ROLE_VERSION],
                },
            }
            await ws.send(json.dumps(hello_msg))
            logger.debug(f"Sent client/hello: {hello_msg}")

            # Listen for messages
            async for message in ws:
                if not self._running:
                    break

                if isinstance(message, str):
                    await self._handle_text_message(message)
                # Binary messages (artwork) could be handled here if needed

    async def _handle_text_message(self, message: str) -> None:
        """
        Handle incoming text (JSON) message from server.

        Args:
            message: Raw JSON message string.
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "server/hello":
                logger.info(f"Server hello received: {data.get('payload', {})}")

            elif msg_type == "server/state":
                self._update_metadata(data.get("payload", {}))

            elif msg_type == "stream/start":
                logger.debug("Stream started")

            elif msg_type == "stream/end":
                logger.debug("Stream ended")
                # Clear metadata when stream ends
                with self._lock:
                    self._metadata = TrackMetadata(is_playing=False)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _update_metadata(self, payload: dict[str, Any]) -> None:
        """
        Update stored metadata from server/state payload.

        Args:
            payload: The payload from a server/state message.
        """
        metadata_data = payload.get("metadata", {})
        if not metadata_data:
            return

        progress = metadata_data.get("progress", {})

        with self._lock:
            self._metadata = TrackMetadata(
                title=metadata_data.get("title", ""),
                artist=metadata_data.get("artist", ""),
                album=metadata_data.get("album", ""),
                artwork_url=metadata_data.get("artwork_url", ""),
                year=metadata_data.get("year"),
                track_number=metadata_data.get("track"),
                track_progress_ms=progress.get("track_progress", 0),
                track_duration_ms=progress.get("track_duration", 0),
                is_playing=True,
                updated_at=time.time(),
            )

        logger.debug(f"Metadata updated: {self._metadata.artist} - {self._metadata.title}")


# =============================================================================
# METADATA CLIENT MANAGER
# =============================================================================


class MetadataClientManager:
    """
    Manages metadata clients for multiple Sendspin players.

    Creates and maintains WebSocket connections for each Sendspin player
    that has a server_url configured.
    """

    def __init__(self) -> None:
        """Initialize the metadata client manager."""
        self._clients: dict[str, SendspinMetadataClient] = {}
        self._lock = threading.Lock()

    def get_or_create_client(self, player_name: str, server_url: str) -> SendspinMetadataClient | None:
        """
        Get existing client or create new one for a player.

        Args:
            player_name: Name of the player.
            server_url: WebSocket URL of the Sendspin server.

        Returns:
            SendspinMetadataClient instance, or None if no server_url.
        """
        if not server_url:
            return None

        with self._lock:
            # Check if we have an existing client for this player
            if player_name in self._clients:
                client = self._clients[player_name]
                # If URL changed, stop old client and create new one
                if client.server_url != server_url:
                    client.stop()
                    del self._clients[player_name]
                else:
                    return client

            # Create new client
            client_id = f"mop-metadata-{player_name}"
            client = SendspinMetadataClient(server_url, client_id)
            client.start()
            self._clients[player_name] = client
            return client

    def get_client(self, player_name: str) -> SendspinMetadataClient | None:
        """
        Get existing client for a player.

        Args:
            player_name: Name of the player.

        Returns:
            SendspinMetadataClient if exists, None otherwise.
        """
        with self._lock:
            return self._clients.get(player_name)

    def remove_client(self, player_name: str) -> None:
        """
        Stop and remove client for a player.

        Args:
            player_name: Name of the player.
        """
        with self._lock:
            if player_name in self._clients:
                self._clients[player_name].stop()
                del self._clients[player_name]

    def stop_all(self) -> None:
        """Stop all metadata clients."""
        with self._lock:
            for client in self._clients.values():
                client.stop()
            self._clients.clear()

    def get_metadata(self, player_name: str) -> TrackMetadata | None:
        """
        Get metadata for a player.

        Args:
            player_name: Name of the player.

        Returns:
            TrackMetadata if client exists, None otherwise.
        """
        client = self.get_client(player_name)
        if client:
            return client.get_metadata()
        return None


# Global manager instance
_metadata_manager: MetadataClientManager | None = None


def get_metadata_manager() -> MetadataClientManager:
    """Get the global metadata client manager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataClientManager()
    return _metadata_manager
