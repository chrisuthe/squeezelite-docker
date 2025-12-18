#!/usr/bin/env python3
"""
Container Health Check Script

Validates that the Multi Output Player container is properly configured
and ready to run. Executed during container startup by entrypoint.sh.

Tests Performed:
    1. Python Imports: Verifies Flask, SocketIO, PyYAML are available
    2. Directory Access: Checks /app/config, /app/logs, /app/data are writable
    3. Flask App: Tests basic Flask initialization and routing
    4. Audio Commands: Verifies audio player binaries exist
       - Full image: squeezelite and sendspin
       - Slim image (SENDSPIN_CONTAINER=1): sendspin only
    5. Port Availability: Checks if port 8080 is available

Exit Codes:
    0: All tests passed - container is healthy
    1: One or more tests failed - check output for details

Usage:
    python3 health_check.py
"""

import os
import sys
import traceback


def test_imports() -> bool:
    """
    Test that all required Python packages are importable.

    Verifies that Flask, Flask-SocketIO, and PyYAML can be imported.
    These are critical dependencies for the main application.

    Returns:
        True if all imports succeed, False if any import fails.

    Side Effects:
        - Prints import status for each package to stdout
    """
    print("Testing Python imports...")

    try:
        import flask

        print(f"✓ Flask {flask.__version__}")
    except ImportError as e:
        print(f"✗ Flask import failed: {e}")
        return False

    try:
        import flask_socketio

        try:
            version = flask_socketio.__version__
        except AttributeError:
            version = "(version not available)"
        print(f"✓ Flask-SocketIO {version}")
    except ImportError as e:
        print(f"✗ Flask-SocketIO import failed: {e}")
        return False

    try:
        import yaml  # noqa: F401 - intentionally testing import availability

        print("✓ PyYAML")
    except ImportError as e:
        print(f"✗ PyYAML import failed: {e}")
        return False

    return True


def test_directories() -> bool:
    """
    Test that required directories exist and are writable.

    Creates directories if they don't exist, then verifies write permissions
    by creating and removing a test file in each directory.

    Directories tested:
        - /app/config: Player configuration storage
        - /app/logs: Application and player logs
        - /app/data: Persistent data storage

    Returns:
        True if all directories are accessible and writable, False otherwise.

    Side Effects:
        - Creates directories if they don't exist
        - Creates and removes temporary test files
        - Prints directory status to stdout
    """
    print("\nTesting directories...")

    dirs = ["/app/config", "/app/logs", "/app/data"]
    for directory in dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            # Test write permission
            test_file = os.path.join(directory, "test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            print(f"✓ {directory} (writable)")
        except Exception as e:
            print(f"✗ {directory}: {e}")
            return False

    return True


def test_flask_app() -> bool:
    """
    Test basic Flask application initialization and routing.

    Creates a minimal Flask application, adds a test route, and verifies
    the routing system works by making a test request.

    Returns:
        True if Flask app initializes and routes correctly, False otherwise.

    Side Effects:
        - Prints test results to stdout
        - Prints stack trace on error

    Note:
        This test creates a temporary Flask app separate from the main
        application to isolate initialization testing.
    """
    print("\nTesting Flask app initialization...")

    try:
        from flask import Flask

        app = Flask(__name__)
        print("✓ Flask app creation")

        @app.route("/test")
        def test():
            return "OK"

        # Test the app context
        with app.test_client() as client:
            response = client.get("/test")
            if response.status_code == 200:
                print("✓ Flask app routing")
            else:
                print(f"✗ Flask app routing failed: {response.status_code}")
                return False

    except Exception as e:
        print(f"✗ Flask app initialization failed: {e}")
        traceback.print_exc()
        return False

    return True


def test_audio_commands() -> bool:
    """
    Test that audio-related commands are available.

    Checks for audio player binaries based on container type:
        - Full image: Both squeezelite and sendspin should be available
        - Slim image (SENDSPIN_CONTAINER=1): Only sendspin required

    Returns:
        True if required audio binaries are found, False otherwise.

    Side Effects:
        - Prints test results to stdout
        - Executes external commands (which, binary --help)
    """
    print("\nTesting audio commands...")

    import shutil
    import subprocess

    is_slim = os.environ.get("SENDSPIN_CONTAINER") == "1"

    if is_slim:
        print("  (Slim image - checking sendspin only)")
    else:
        print("  (Full image - checking squeezelite and sendspin)")

    all_passed = True

    # Check sendspin (required for both full and slim)
    sendspin_path = shutil.which("sendspin")
    if sendspin_path:
        print(f"✓ sendspin binary found at: {sendspin_path}")
        try:
            subprocess.run(["sendspin", "--help"], capture_output=True, text=True, timeout=5)
            print("✓ sendspin binary responds to commands")
        except subprocess.TimeoutExpired:
            print("✗ sendspin command timed out")
            all_passed = False
        except Exception as e:
            print(f"⚠ sendspin help check failed: {e}")
    else:
        print("✗ sendspin binary not found")
        all_passed = False

    # Check squeezelite (only required for full image)
    if not is_slim:
        squeezelite_path = shutil.which("squeezelite")
        if squeezelite_path:
            print(f"✓ squeezelite binary found at: {squeezelite_path}")
            try:
                # squeezelite -? exits non-zero but should not crash
                subprocess.run(["squeezelite", "-?"], capture_output=True, text=True, timeout=5)
                print("✓ squeezelite binary responds to commands")
            except subprocess.TimeoutExpired:
                print("✗ squeezelite command timed out")
                all_passed = False
            except Exception as e:
                print(f"⚠ squeezelite help check failed: {e}")
        else:
            print("✗ squeezelite binary not found")
            all_passed = False

    return all_passed


def test_port_availability() -> bool:
    """
    Test if port 8080 is available for the web server.

    Attempts to connect to localhost:8080 to check if another process
    is already using the port. The Flask application needs this port.

    Returns:
        True if port 8080 is available, False if already in use.

    Side Effects:
        - Prints port status to stdout
        - Creates and closes a TCP socket connection attempt
    """
    print("\nTesting port availability...")

    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", 8080))
        sock.close()

        if result == 0:
            print("⚠ Port 8080 is already in use")
            return False
        else:
            print("✓ Port 8080 is available")
            return True

    except Exception as e:
        print(f"✗ Port test failed: {e}")
        return False


def main() -> None:
    """
    Run all health check tests and report results.

    Executes each test function in sequence, tracks pass/fail counts,
    and exits with appropriate code for container orchestration.

    Exit Codes:
        0: All tests passed - container is healthy
        1: One or more tests failed - container needs attention

    Side Effects:
        - Prints test progress and results to stdout
        - Calls sys.exit() with appropriate exit code
    """
    print("Multi Output Player Container Health Check")
    print("=" * 50)

    tests = [
        ("Python Imports", test_imports),
        ("Directory Access", test_directories),
        ("Flask App", test_flask_app),
        ("Audio Commands", test_audio_commands),
        ("Port Availability", test_port_availability),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"\n❌ {test_name} test failed")
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {e}")
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"Health Check Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ Container is healthy and ready to start")
        sys.exit(0)
    else:
        print("❌ Container has issues that need to be resolved")
        sys.exit(1)


if __name__ == "__main__":
    main()
