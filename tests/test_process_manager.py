"""
Unit tests for ProcessManager class.

Tests subprocess lifecycle management including starting, stopping,
and monitoring processes with mocked subprocess calls.
"""

import os
import signal
import subprocess
from unittest.mock import Mock, call, patch

from managers.process_manager import (
    PROCESS_KILL_TIMEOUT_SECS,
    PROCESS_STARTUP_DELAY_SECS,
    PROCESS_STOP_TIMEOUT_SECS,
    ProcessManager,
)

# =============================================================================
# TESTS - Initialization
# =============================================================================


class TestProcessManagerInit:
    """Tests for ProcessManager initialization."""

    def test_init_default_log_dir(self):
        """Test initialization with default log directory."""
        with patch("os.makedirs") as mock_makedirs:
            manager = ProcessManager()
            assert manager.log_dir == "/app/logs"
            mock_makedirs.assert_called_once_with("/app/logs", exist_ok=True)

    def test_init_custom_log_dir(self, temp_log_dir):
        """Test initialization with custom log directory."""
        manager = ProcessManager(log_dir=temp_log_dir)
        assert manager.log_dir == temp_log_dir

    def test_init_creates_log_directory(self, tmp_path):
        """Test initialization creates log directory."""
        log_dir = tmp_path / "logs"
        ProcessManager(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_init_empty_processes_dict(self, temp_log_dir):
        """Test initialization starts with empty processes dict."""
        manager = ProcessManager(log_dir=temp_log_dir)
        assert len(manager.processes) == 0


# =============================================================================
# TESTS - Start Process
# =============================================================================


class TestProcessManagerStart:
    """Tests for ProcessManager.start() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_success(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test starting a process successfully."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start("test-player", ["squeezelite", "-n", "test"])

        assert success is True
        assert "started successfully" in message.lower()
        assert "test-player" in manager.processes
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_creates_process_group(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test start creates process in its own process group."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        # Check that preexec_fn was set to os.setsid
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["preexec_fn"] == os.setsid

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_already_running(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test starting a process that's already running."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        # Try to start again
        success, message = manager.start("test-player", ["squeezelite", "-n", "test"])

        assert success is False
        assert "already running" in message.lower()
        # Should only have been called once
        assert mock_popen.call_count == 1

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_process_fails_immediately(self, mock_sleep, mock_popen, temp_log_dir, mock_failed_process):
        """Test starting a process that fails immediately."""
        mock_popen.return_value = mock_failed_process

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start("test-player", ["squeezelite", "-n", "test"])

        assert success is False
        assert "failed to start" in message.lower()
        assert "Device not found" in message

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_with_fallback_command(self, mock_sleep, mock_popen, temp_log_dir):
        """Test starting with fallback when primary fails."""
        # First process fails, second succeeds
        failed_process = Mock()
        failed_process.poll.return_value = 1
        failed_process.communicate.return_value = (b"", b"Device error")

        success_process = Mock()
        success_process.poll.return_value = None
        success_process.pid = 12345

        mock_popen.side_effect = [failed_process, success_process]

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start(
            "test-player",
            ["squeezelite", "-n", "test", "-o", "hw:0,0"],
            fallback_command=["squeezelite", "-n", "test", "-o", "null"],
        )

        assert success is True
        assert "fallback" in message.lower()
        assert mock_popen.call_count == 2

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_fallback_also_fails(self, mock_sleep, mock_popen, temp_log_dir, mock_failed_process):
        """Test when both primary and fallback commands fail."""
        mock_popen.return_value = mock_failed_process

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start(
            "test-player",
            ["squeezelite", "-n", "test", "-o", "hw:0,0"],
            fallback_command=["squeezelite", "-n", "test", "-o", "null"],
        )

        assert success is False
        assert "fallback also failed" in message.lower()

    @patch("subprocess.Popen")
    def test_start_binary_not_found(self, mock_popen, temp_log_dir):
        """Test starting when binary is not found."""
        mock_popen.side_effect = FileNotFoundError()

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start("test-player", ["nonexistent", "-n", "test"])

        assert success is False
        assert "not found" in message.lower()

    @patch("subprocess.Popen")
    def test_start_unexpected_error(self, mock_popen, temp_log_dir):
        """Test starting with unexpected error."""
        mock_popen.side_effect = RuntimeError("Unexpected error")

        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.start("test-player", ["squeezelite", "-n", "test"])

        assert success is False
        assert "error" in message.lower()

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_start_waits_for_startup(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test start waits for process startup delay."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        mock_sleep.assert_called_with(PROCESS_STARTUP_DELAY_SECS)


# =============================================================================
# TESTS - Stop Process
# =============================================================================


class TestProcessManagerStop:
    """Tests for ProcessManager.stop() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    @patch("os.killpg")
    @patch("os.getpgid")
    def test_stop_success(self, mock_getpgid, mock_killpg, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test stopping a running process successfully."""
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        success, message = manager.stop("test-player")

        assert success is True
        assert "stopped successfully" in message.lower()
        assert "test-player" not in manager.processes
        mock_killpg.assert_called_once_with(12345, signal.SIGTERM)

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_stop_nonexistent_process(self, mock_sleep, mock_popen, temp_log_dir):
        """Test stopping a process that doesn't exist."""
        manager = ProcessManager(log_dir=temp_log_dir)
        success, message = manager.stop("nonexistent")

        assert success is False
        assert "not found" in message.lower()

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_stop_already_terminated(self, mock_sleep, mock_popen, temp_log_dir):
        """Test stopping a process that already terminated."""
        terminated_process = Mock()
        terminated_process.poll.return_value = 0  # Already terminated
        mock_popen.return_value = terminated_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        success, message = manager.stop("test-player")

        assert success is False
        assert "not running" in message.lower()

    @patch("subprocess.Popen")
    @patch("time.sleep")
    @patch("os.killpg")
    @patch("os.getpgid")
    def test_stop_force_kill_on_timeout(self, mock_getpgid, mock_killpg, mock_sleep, mock_popen, temp_log_dir):
        """Test force kill when process doesn't respond to SIGTERM."""
        process = Mock()
        process.poll.return_value = None
        process.pid = 12345
        process.wait.side_effect = [subprocess.TimeoutExpired("cmd", PROCESS_STOP_TIMEOUT_SECS), None]

        mock_popen.return_value = process
        mock_getpgid.return_value = 12345

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        success, message = manager.stop("test-player")

        assert success is True
        assert "force stopped" in message.lower()
        # Should have called killpg twice: SIGTERM then SIGKILL
        assert mock_killpg.call_count == 2
        calls = mock_killpg.call_args_list
        assert calls[0] == call(12345, signal.SIGTERM)
        assert calls[1] == call(12345, signal.SIGKILL)

    @patch("subprocess.Popen")
    @patch("time.sleep")
    @patch("os.killpg")
    @patch("os.getpgid")
    def test_stop_error_handling(self, mock_getpgid, mock_killpg, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test stop handles errors during kill."""
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345
        mock_killpg.side_effect = OSError("Process error")

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        success, message = manager.stop("test-player")

        assert success is False
        assert "error" in message.lower()


# =============================================================================
# TESTS - Is Running
# =============================================================================


class TestProcessManagerIsRunning:
    """Tests for ProcessManager.is_running() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_is_running_true(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test is_running returns True for running process."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        assert manager.is_running("test-player") is True

    def test_is_running_false_nonexistent(self, temp_log_dir):
        """Test is_running returns False for non-existent process."""
        manager = ProcessManager(log_dir=temp_log_dir)
        assert manager.is_running("nonexistent") is False

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_is_running_false_terminated(self, mock_sleep, mock_popen, temp_log_dir):
        """Test is_running returns False for terminated process."""
        process = Mock()
        process.poll.side_effect = [None, 0]  # First running, then terminated
        process.pid = 12345

        mock_popen.return_value = process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        assert manager.is_running("test-player") is False


# =============================================================================
# TESTS - Get All Statuses
# =============================================================================


class TestProcessManagerGetAllStatuses:
    """Tests for ProcessManager.get_all_statuses() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_get_all_statuses(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test getting status of all players."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("player1", ["squeezelite", "-n", "player1"])

        statuses = manager.get_all_statuses(["player1", "player2", "player3"])

        assert statuses["player1"] is True
        assert statuses["player2"] is False
        assert statuses["player3"] is False

    def test_get_all_statuses_empty(self, temp_log_dir):
        """Test get_all_statuses with empty list."""
        manager = ProcessManager(log_dir=temp_log_dir)
        statuses = manager.get_all_statuses([])

        assert len(statuses) == 0


# =============================================================================
# TESTS - Get Process
# =============================================================================


class TestProcessManagerGetProcess:
    """Tests for ProcessManager.get_process() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_get_process_running(self, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test getting a running process."""
        mock_popen.return_value = mock_process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        process = manager.get_process("test-player")

        assert process is not None
        assert process == mock_process

    def test_get_process_nonexistent(self, temp_log_dir):
        """Test getting a non-existent process."""
        manager = ProcessManager(log_dir=temp_log_dir)
        process = manager.get_process("nonexistent")

        assert process is None

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_get_process_terminated(self, mock_sleep, mock_popen, temp_log_dir):
        """Test getting a terminated process returns None."""
        process = Mock()
        process.poll.return_value = 0  # Terminated
        mock_popen.return_value = process

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("test-player", ["squeezelite", "-n", "test"])

        result = manager.get_process("test-player")

        assert result is None


# =============================================================================
# TESTS - Cleanup Dead Processes
# =============================================================================


class TestProcessManagerCleanupDeadProcesses:
    """Tests for ProcessManager.cleanup_dead_processes() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_cleanup_dead_processes(self, mock_sleep, mock_popen, temp_log_dir):
        """Test cleaning up terminated processes."""
        # Create two processes: one running, one terminated
        running_process = Mock()
        running_process.poll.return_value = None
        running_process.pid = 12345

        dead_process = Mock()
        dead_process.poll.return_value = 1
        dead_process.pid = 12346

        mock_popen.side_effect = [running_process, dead_process]

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("running", ["squeezelite", "-n", "running"])
        manager.start("dead", ["squeezelite", "-n", "dead"])

        cleaned = manager.cleanup_dead_processes()

        assert len(cleaned) == 1
        assert "dead" in cleaned
        assert "running" in manager.processes
        assert "dead" not in manager.processes

    def test_cleanup_no_dead_processes(self, temp_log_dir):
        """Test cleanup when no processes are dead."""
        manager = ProcessManager(log_dir=temp_log_dir)
        cleaned = manager.cleanup_dead_processes()

        assert len(cleaned) == 0


# =============================================================================
# TESTS - Stop All
# =============================================================================


class TestProcessManagerStopAll:
    """Tests for ProcessManager.stop_all() method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    @patch("os.killpg")
    @patch("os.getpgid")
    def test_stop_all(self, mock_getpgid, mock_killpg, mock_sleep, mock_popen, temp_log_dir, mock_process):
        """Test stopping all processes."""
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345

        manager = ProcessManager(log_dir=temp_log_dir)
        manager.start("player1", ["squeezelite", "-n", "player1"])
        manager.start("player2", ["squeezelite", "-n", "player2"])

        stopped = manager.stop_all()

        assert stopped == 2
        assert len(manager.processes) == 0

    def test_stop_all_empty(self, temp_log_dir):
        """Test stop_all with no processes."""
        manager = ProcessManager(log_dir=temp_log_dir)
        stopped = manager.stop_all()

        assert stopped == 0


# =============================================================================
# TESTS - Get Log Path
# =============================================================================


class TestProcessManagerGetLogPath:
    """Tests for ProcessManager.get_log_path() method."""

    def test_get_log_path(self, temp_log_dir):
        """Test getting log path for a process."""
        manager = ProcessManager(log_dir=temp_log_dir)
        log_path = manager.get_log_path("test-player")

        assert log_path == os.path.join(temp_log_dir, "test-player.log")

    def test_get_log_path_with_spaces(self, temp_log_dir):
        """Test log path handles names with spaces."""
        manager = ProcessManager(log_dir=temp_log_dir)
        log_path = manager.get_log_path("test player")

        assert log_path == os.path.join(temp_log_dir, "test player.log")


# =============================================================================
# TESTS - Constants
# =============================================================================


class TestProcessManagerConstants:
    """Tests for ProcessManager constants."""

    def test_startup_delay_reasonable(self):
        """Test startup delay is reasonable."""
        assert PROCESS_STARTUP_DELAY_SECS > 0
        assert PROCESS_STARTUP_DELAY_SECS < 5  # Should be quick

    def test_stop_timeout_reasonable(self):
        """Test stop timeout is reasonable."""
        assert PROCESS_STOP_TIMEOUT_SECS > 0
        assert PROCESS_STOP_TIMEOUT_SECS < 30  # Should not wait too long

    def test_kill_timeout_reasonable(self):
        """Test kill timeout is reasonable."""
        assert PROCESS_KILL_TIMEOUT_SECS > 0
        assert PROCESS_KILL_TIMEOUT_SECS < 10

    def test_kill_timeout_less_than_stop_timeout(self):
        """Test kill timeout is less than stop timeout."""
        assert PROCESS_KILL_TIMEOUT_SECS < PROCESS_STOP_TIMEOUT_SECS
