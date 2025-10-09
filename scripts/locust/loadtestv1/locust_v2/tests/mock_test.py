#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock test file for simulating Clarifai load tests without hitting real APIs.
This is useful for testing the workflow setup and ensuring everything works.
"""

import time
import random
from locust import User, task, events


class MockUser(User):
    """Mock user that simulates API calls without actually making them."""

    wait_time_min = 1
    wait_time_max = 3

    total_failures = 0
    request_count = 0
    total_tokens = 0
    response_times = []
    test_start_time = None
    first_token_times = []

    def __init__(self, environment):
        super().__init__(environment)
        if MockUser.test_start_time is None:
            MockUser.test_start_time = time.time()

    @task
    def mock_predict(self):
        """Simulate a prediction call with realistic timing."""
        start_time = time.time()

        MockUser.request_count += 1

        # Simulate processing time (50-500ms)
        processing_time = random.uniform(0.05, 0.5)
        time.sleep(processing_time)

        # Simulate token generation (10-100 tokens)
        tokens_generated = random.randint(10, 100)
        MockUser.total_tokens += tokens_generated

        # Record metrics
        response_time = int((time.time() - start_time) * 1000)
        MockUser.response_times.append(response_time)
        MockUser.first_token_times.append(response_time)

        # Fire success event
        # Note: We don't simulate failures to avoid exit code 1
        events.request.fire(
            request_type="mock",
            name="mock_predict",
            response_time=response_time,
            response_length=tokens_generated,
            exception=None,
            response="Mock response"
        )


# Hook to calculate final metrics after all users stop
@events.quitting.add_listener
def on_quitting(environment, **_kwargs):
    """Print summary statistics when test completes."""
    end_time = time.time()
    total_duration = end_time - MockUser.test_start_time

    if total_duration > 0:
        rps = MockUser.request_count / total_duration
        throughput = MockUser.total_tokens / total_duration
        average_response_time = (
            sum(MockUser.response_times) / len(MockUser.response_times)
            if MockUser.response_times
            else 0
        )
        first_token_time = (
            sum(MockUser.first_token_times) / len(MockUser.first_token_times)
            if len(MockUser.first_token_times) > 0
            else -1
        )

        print("\n" + "=" * 60)
        print("MOCK TEST SUMMARY")
        print("=" * 60)
        print(f"Total Requests: {MockUser.request_count}")
        print(f"Total Failures: {MockUser.total_failures}")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Requests per Second (RPS): {rps:.2f}")
        print(f"Throughput (Tokens per Second): {throughput:.2f}")
        print(f"Average Response Time: {average_response_time:.2f} ms")
        print(f"Avg First Token Time: {first_token_time:.2f} ms")
        print(f"Total Tokens: {MockUser.total_tokens}")
        print("=" * 60)
        print("NOTE: This was a MOCK test - no real API calls were made")
        print("=" * 60 + "\n")
