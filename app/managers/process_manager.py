"""
Process Manager for subprocess lifecycle management.

Handles starting, stopping, and monitoring subprocesses for audio players.
Provider-agnostic - just manages processes given commands to run.
"""

import logging
import os
import signal
import subprocess
import time

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Delay after starting a process to check if it failed immediately
PROCESS_STARTUP_DELAY_SECS = 0.5

# Timeout when waiting for process to stop gracefully (SIGTERM)
PROCESS_STOP_TIMEOUT_SECS = 5

# Timeout when waiting for process to be killed forcefully (SIGKILL)
PROCESS_KILL_TIMEOUT_SECS = 2


class ProcessManager:
    """
    Manages subprocess lifecycle for audio players.

    Provider-agnostic process management - handles starting, stopping,
    and monitoring subprocesses given commands to run. Does not know
    about specific player implementations.

    Attributes:
        processes: Dictionary mapping player names to their Popen instances.
        log_dir: Directory for process log files.
    """

    def __init__(self, log_dir: str = "/app/logs") -> None:
        """
        Initialize the ProcessManager.

        Args:
            log_dir: Directory for process log files.
        """
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.log_dir = log_dir

        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)

    def start(
        self,
        name: str,
        command: list[str],
        fallback_command: list[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Start a subprocess for a player.

        Launches a new subprocess with the given command. If the process
        fails immediately and a fallback command is provided, tries the
        fallback.

        Args:
            name: Unique name for this process (used as key).
            command: Command and arguments to run.
            fallback_command: Optional fallback command if primary fails.

        Returns:
            Tuple of (success: bool, message: str).

        Side Effects:
            - Adds process to self.processes dict
            - Creates process group for signal handling
        """
        if name in self.processes and self.processes[name].poll() is None:
            return False, f"Process '{name}' is already running"

        logger.info(f"Starting process '{name}' with command: {' '.join(command)}")

        try:
            # Start the process in its own process group
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )

            self.processes[name] = process

            # Give the process a moment to start and check if it fails immediately
            time.sleep(PROCESS_STARTUP_DELAY_SECS)

            if process.poll() is not None:
                # Process terminated immediately, check error
                stdout, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Process '{name}' failed to start: {error_msg}")

                # Try fallback if provided
                if fallback_command:
                    logger.info(f"Trying fallback command for '{name}'")
                    return self._start_fallback(name, fallback_command)

                return False, f"Process failed to start: {error_msg}"

            logger.info(f"Started process '{name}' with PID {process.pid}")
            return True, f"Process '{name}' started successfully"

        except FileNotFoundError:
            binary = command[0] if command else "unknown"
            logger.error(f"Binary '{binary}' not found")
            return False, f"Binary '{binary}' not found"
        except Exception as e:
            logger.error(f"Error starting process '{name}': {e}")
            return False, f"Error starting process: {e}"

    def _start_fallback(self, name: str, command: list[str]) -> tuple[bool, str]:
        """
        Start a fallback process after primary failed.

        Args:
            name: Process name.
            command: Fallback command to run.

        Returns:
            Tuple of (success: bool, message: str).
        """
        logger.info(f"Fallback command for '{name}': {' '.join(command)}")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )

            self.processes[name] = process
            time.sleep(PROCESS_STARTUP_DELAY_SECS)

            if process.poll() is not None:
                stdout, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                return False, f"Fallback also failed: {error_msg}"

            logger.info(f"Started process '{name}' with fallback (PID {process.pid})")
            return True, f"Process '{name}' started with fallback configuration"

        except Exception as e:
            logger.error(f"Error starting fallback for '{name}': {e}")
            return False, f"Error starting fallback: {e}"

    def stop(self, name: str) -> tuple[bool, str]:
        """
        Stop a subprocess.

        Sends SIGTERM to gracefully stop the process. If the process doesn't
        terminate within PROCESS_STOP_TIMEOUT_SECS, sends SIGKILL.

        Args:
            name: Name of the process to stop.

        Returns:
            Tuple of (success: bool, message: str).

        Side Effects:
            - Removes process from self.processes dict
        """
        if name not in self.processes:
            return False, f"Process '{name}' not found"

        process = self.processes[name]
        if process.poll() is not None:
            # Process already terminated
            del self.processes[name]
            return False, f"Process '{name}' was not running"

        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)

            # Wait for process to terminate
            process.wait(timeout=PROCESS_STOP_TIMEOUT_SECS)
            del self.processes[name]
            logger.info(f"Stopped process '{name}'")
            return True, f"Process '{name}' stopped successfully"

        except subprocess.TimeoutExpired:
            # Force kill if it doesn't respond to SIGTERM
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=PROCESS_KILL_TIMEOUT_SECS)
            except Exception:
                pass
            del self.processes[name]
            logger.info(f"Force stopped process '{name}'")
            return True, f"Process '{name}' force stopped"
        except Exception as e:
            logger.error(f"Error stopping process '{name}': {e}")
            return False, f"Error stopping process: {e}"

    def is_running(self, name: str) -> bool:
        """
        Check if a process is running.

        Args:
            name: Name of the process.

        Returns:
            True if the process is running, False otherwise.
        """
        if name not in self.processes:
            return False

        process = self.processes[name]
        return process.poll() is None

    def get_all_statuses(self, player_names: list[str]) -> dict[str, bool]:
        """
        Get running status of all specified players.

        Args:
            player_names: List of player names to check.

        Returns:
            Dictionary mapping player names to their running status.
        """
        statuses = {}
        for name in player_names:
            statuses[name] = self.is_running(name)
        return statuses

    def get_process(self, name: str) -> subprocess.Popen | None:
        """
        Get the Popen object for a process.

        Args:
            name: Name of the process.

        Returns:
            Popen object if found and running, None otherwise.
        """
        if name in self.processes and self.processes[name].poll() is None:
            return self.processes[name]
        return None

    def cleanup_dead_processes(self) -> list[str]:
        """
        Remove terminated processes from tracking.

        Checks all tracked processes and removes any that have terminated.

        Returns:
            List of names of processes that were cleaned up.
        """
        cleaned = []
        for name in list(self.processes.keys()):
            if self.processes[name].poll() is not None:
                del self.processes[name]
                cleaned.append(name)
                logger.debug(f"Cleaned up terminated process '{name}'")
        return cleaned

    def stop_all(self) -> int:
        """
        Stop all running processes.

        Returns:
            Number of processes that were stopped.
        """
        stopped = 0
        for name in list(self.processes.keys()):
            success, _ = self.stop(name)
            if success:
                stopped += 1
        return stopped

    def get_log_path(self, name: str) -> str:
        """
        Get the log file path for a process.

        Args:
            name: Name of the process.

        Returns:
            Path to the log file.
        """
        return os.path.join(self.log_dir, f"{name}.log")
