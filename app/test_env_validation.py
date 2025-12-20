#!/usr/bin/env python3
"""
Test script for environment variable validation.

This script tests the env_validation module with various valid and invalid
environment variable configurations to ensure proper error messages and
graceful degradation.
"""

import os
import sys

# Test cases: (env_var, value, should_be_valid)
TEST_CASES = [
    # SQUEEZELITE_BUFFER_TIME tests
    ("SQUEEZELITE_BUFFER_TIME", "80", True, "valid default"),
    ("SQUEEZELITE_BUFFER_TIME", "100", True, "valid custom value"),
    ("SQUEEZELITE_BUFFER_TIME", "invalid", False, "non-numeric value"),
    ("SQUEEZELITE_BUFFER_TIME", "-5", False, "negative value"),
    ("SQUEEZELITE_BUFFER_TIME", "2000", False, "exceeds maximum"),
    # SQUEEZELITE_BUFFER_PARAMS tests
    ("SQUEEZELITE_BUFFER_PARAMS", "500:2000", True, "valid default"),
    ("SQUEEZELITE_BUFFER_PARAMS", "1000:3000", True, "valid custom value"),
    ("SQUEEZELITE_BUFFER_PARAMS", "invalid", False, "invalid format"),
    ("SQUEEZELITE_BUFFER_PARAMS", "500", False, "missing colon"),
    ("SQUEEZELITE_BUFFER_PARAMS", "500:abc", False, "non-numeric output buffer"),
    ("SQUEEZELITE_BUFFER_PARAMS", "-100:2000", False, "negative stream buffer"),
    ("SQUEEZELITE_BUFFER_PARAMS", "500:200000", False, "exceeds maximum"),
    # SQUEEZELITE_CLOSE_TIMEOUT tests
    ("SQUEEZELITE_CLOSE_TIMEOUT", "5", True, "valid default"),
    ("SQUEEZELITE_CLOSE_TIMEOUT", "0", True, "zero timeout (always open)"),
    ("SQUEEZELITE_CLOSE_TIMEOUT", "abc", False, "non-numeric value"),
    ("SQUEEZELITE_CLOSE_TIMEOUT", "-1", False, "negative timeout"),
    # SQUEEZELITE_SAMPLE_RATE tests
    ("SQUEEZELITE_SAMPLE_RATE", "44100", True, "valid CD quality"),
    ("SQUEEZELITE_SAMPLE_RATE", "48000", True, "valid DVD quality"),
    ("SQUEEZELITE_SAMPLE_RATE", "96000", True, "valid high quality"),
    ("SQUEEZELITE_SAMPLE_RATE", "invalid", False, "non-numeric value"),
    ("SQUEEZELITE_SAMPLE_RATE", "1000", False, "below minimum"),
    ("SQUEEZELITE_SAMPLE_RATE", "500000", False, "exceeds maximum"),
    # SQUEEZELITE_WINDOWS_MODE tests
    ("SQUEEZELITE_WINDOWS_MODE", "0", True, "disabled"),
    ("SQUEEZELITE_WINDOWS_MODE", "1", True, "enabled"),
    ("SQUEEZELITE_WINDOWS_MODE", "true", True, "boolean true"),
    ("SQUEEZELITE_WINDOWS_MODE", "false", True, "boolean false"),
    ("SQUEEZELITE_WINDOWS_MODE", "yes", True, "yes value"),
    ("SQUEEZELITE_WINDOWS_MODE", "no", True, "no value"),
    ("SQUEEZELITE_WINDOWS_MODE", "invalid", False, "invalid boolean"),
    # AUDIO_BACKEND tests
    ("AUDIO_BACKEND", "alsa", True, "ALSA backend"),
    ("AUDIO_BACKEND", "pulse", True, "PulseAudio backend"),
    ("AUDIO_BACKEND", "PULSE", True, "case insensitive"),
    ("AUDIO_BACKEND", "pipewire", True, "PipeWire backend"),
    ("AUDIO_BACKEND", "invalid", False, "unknown backend"),
]


def run_tests():
    """Run all validation test cases."""
    print("=" * 70)
    print("Environment Variable Validation Tests")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    # Save original environment
    original_env = os.environ.copy()

    for env_var, value, expected_valid, description in TEST_CASES:
        # Clear all test-related env vars
        for key in list(os.environ.keys()):
            if key.startswith("SQUEEZELITE_") or key in ("AUDIO_BACKEND", "SECRET_KEY"):
                del os.environ[key]

        # Set the test variable
        os.environ[env_var] = value

        # Import fresh copy of validation module
        if "env_validation" in sys.modules:
            del sys.modules["env_validation"]
        from env_validation import validate_environment_variables

        # Run validation
        result = validate_environment_variables()

        # For specific variable tests, check if there's a warning about that variable
        has_warning_for_var = any(env_var in warning for warning in result["warnings"])

        # Determine if test passed
        if expected_valid:
            # Should be valid - no warning for this variable
            test_passed = not has_warning_for_var
        else:
            # Should be invalid - should have warning for this variable
            test_passed = has_warning_for_var

        # Record results
        if test_passed:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1
            errors.append(
                f"{env_var}={value} ({description}): Expected valid={expected_valid}, got warnings={result['warnings']}"
            )

        print(f"[{status}] {env_var}={value:20s} ({description})")

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

    # Print summary
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
    print("=" * 70)

    if errors:
        print("\nFailures:")
        for error in errors:
            print(f"  - {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_tests())
