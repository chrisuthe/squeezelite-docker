#!/usr/bin/env python3

import sys
import os
import traceback

def test_imports():
    """Test all required Python imports"""
    print("Testing Python imports...")
    
    try:
        import flask
        print(f"✓ Flask {flask.__version__}")
    except ImportError as e:
        print(f"✗ Flask import failed: {e}")
        return False
    
    try:
        import flask_socketio
        print(f"✓ Flask-SocketIO {flask_socketio.__version__}")
    except ImportError as e:
        print(f"✗ Flask-SocketIO import failed: {e}")
        return False
    
    try:
        import yaml
        print("✓ PyYAML")
    except ImportError as e:
        print(f"✗ PyYAML import failed: {e}")
        return False
    
    try:
        import psutil
        print(f"✓ psutil {psutil.__version__}")
    except ImportError as e:
        print(f"✗ psutil import failed: {e}")
        return False
    
    return True

def test_directories():
    """Test that required directories exist and are writable"""
    print("\nTesting directories...")
    
    dirs = ['/app/config', '/app/logs', '/app/data']
    for directory in dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            # Test write permission
            test_file = os.path.join(directory, 'test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✓ {directory} (writable)")
        except Exception as e:
            print(f"✗ {directory}: {e}")
            return False
    
    return True

def test_flask_app():
    """Test basic Flask app initialization"""
    print("\nTesting Flask app initialization...")
    
    try:
        from flask import Flask
        app = Flask(__name__)
        print("✓ Flask app creation")
        
        @app.route('/test')
        def test():
            return 'OK'
        
        # Test the app context
        with app.test_client() as client:
            response = client.get('/test')
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

def test_audio_commands():
    """Test audio-related commands"""
    print("\nTesting audio commands...")
    
    try:
        import subprocess
        
        # Test if squeezelite binary exists
        result = subprocess.run(['which', 'squeezelite'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ squeezelite binary found at: {result.stdout.strip()}")
        else:
            print("✗ squeezelite binary not found")
            return False
        
        # Test squeezelite help (should exit with non-zero but not crash)
        result = subprocess.run(['squeezelite', '-?'], 
                              capture_output=True, text=True, timeout=5)
        print("✓ squeezelite binary responds to commands")
        
    except subprocess.TimeoutExpired:
        print("✗ squeezelite command timed out")
        return False
    except Exception as e:
        print(f"✗ Audio command test failed: {e}")
        return False
    
    return True

def test_port_availability():
    """Test if port 8080 is available"""
    print("\nTesting port availability...")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8080))
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

def main():
    """Run all tests"""
    print("Squeezelite Multi-Room Container Health Check")
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

if __name__ == '__main__':
    main()
