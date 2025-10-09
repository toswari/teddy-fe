#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subclass GrpcUser when load testing via Clarifai gRPC client.
Set your desired host and key as class attributes of your user!

Either define the host attribute when subclassing GrpcUser or set it in the UI.
Leaving host as None will use the Clarifai production environment.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import Callable

import grpc.experimental.gevent as grpc_gevent
from clarifai.client import BaseClient, Model
from clarifai_grpc.grpc.api import service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from locust import User, events, stats

grpc_gevent.init_gevent()


def _ensure_event_loop():
    """Ensure event loop exists for the current thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        # No event loop in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

# Control which latency bands to track.
stats.PERCENTILES_TO_REPORT = [0.5, 0.95, 0.99, 0.99999]
stats.PERCENTILES_TO_CHART = [0.5, 0.95, 0.99, 0.99999]

log = logging.getLogger("console")
log.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh = logging.FileHandler(f'locust_{datetime.now().strftime("%S")}.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
log.addHandler(fh)


class GrpcUser(User):
    abstract = True
    # host = None
    stub_class = service_pb2_grpc.V2Stub
    client = BaseClient

    total_failures = 0
    request_count = 0
    total_tokens = 0
    response_times = []
    test_start_time = None
    first_token_times = []

    # key = None

    def __init__(self, environment):
        super().__init__(environment)
        # Setup event loop for this thread to avoid async issues
        _ensure_event_loop()

        self.client = BaseClient.from_env()
        self.stub = self.client.STUB

        # Build Model kwargs with optional base_url
        model_kwargs = {
            "url": os.environ['CLARIFAI_MODEL_URL'],
            "deployment_id": os.environ.get("CLARIFAI_DEPLOYMENT_ID"),
            "deployment_user_id": os.environ.get("CLARIFAI_DEPLOYMENT_USER_ID"),
        }

        # Add base_url if specified (for dev environment)
        if os.environ.get("CLARIFAI_API_BASE"):
            model_kwargs["base_url"] = os.environ["CLARIFAI_API_BASE"]

        self.model = Model(**model_kwargs)

    def predict(self, name: str, func: Callable, *args, **kwargs):
        """call allows locust to record statistics for Clarifai's gRPC client.

        Args:
                func (callable): the function to call
                name (string): identifier for the call to record on locust stats
                *args (any): args to pass to callable
                **kwargs (any): kwargs to pass to callable

        Returns:
            response from calling Callable
        """
        # Ensure event loop exists for this thread
        _ensure_event_loop()

        start_time = time.time()
        response_length = 0
        resp = None
        response_time = 0
        exception = None
        try:
            if GrpcUser.test_start_time is None:
                GrpcUser.test_start_time = time.time()
            GrpcUser.request_count += 1
            log.debug(f"Request {GrpcUser.request_count} started at {datetime.now()}")
            resp = func(*args, **kwargs)
            log.debug(
                f"Request {GrpcUser.request_count} ended at {datetime.now()} duration {time.time() - start_time}"
            )
            response_length = sys.getsizeof(resp)
        except Exception as e:
            GrpcUser.total_failures += 1
            exception = e
            log.exception(
                f"Request {GrpcUser.request_count} ended at {datetime.now()} with exception '{e}'"
            )
            log.error(f"Request raised exception '{e}'", stack_info=True)
        else:
            duration = int((time.time() - start_time) * 1000)
            if duration > 1000:
                log.warning(f"Request took {duration}ms to complete. resp: {resp}")
            GrpcUser.first_token_times.append(duration)

            if isinstance(resp, str):
                GrpcUser.total_tokens += len(resp.split(" "))
            else:
                GrpcUser.total_tokens += len(resp)
            print(f"Total tokens output: {GrpcUser.total_tokens}", end="\r", flush=True)

        response_time = int((time.time() - start_time) * 1000)
        GrpcUser.response_times.append(response_time)
        events.request.fire(
            request_type="client",
            name=name,
            response_time=response_time,
            response_length=response_length,
            exception=exception,
            response=resp,
        )
        if resp is not None:
            return resp

    def _validate_host(self, host_url: str):
        if host_url in [None, ""]:
            log.warning(
                "No host URL provided, gRPC stub will be created for the production environment"
            )
            self.host = None
        elif not host_url.startswith("https://"):
            log.warning("Provided host URL does not have https:// prefix, adding...")
            self.host = "https://" + host_url

    def generate(self, name: str, func: Callable, *args, **kwargs):
        """call allows locust to record statistics for Clarifai's gRPC client.

        Args:
                func (callable): the function to call which should yield responses
                name (string): identifier for the call to record on locust stats
                *args (any): args to pass to callable
                **kwargs (any): kwargs to pass to callable

        Returns:
            response from calling Callable
        """
        # Ensure event loop exists for this thread
        _ensure_event_loop()

        start_time = time.time()
        response_length = 0
        resp = None
        response_time = 0
        exception = None

        responses = []
        try:
            if GrpcUser.test_start_time is None:
                GrpcUser.test_start_time = time.time()
            GrpcUser.request_count += 1
            for i, resp in enumerate(func(*args, **kwargs)):
                if resp.status.code != status_code_pb2.SUCCESS:
                    GrpcUser.total_failures += 1
                    msg = f"Request returned but had response status code '{resp.status.code}' with body '{resp}'"
                    log.warning(msg)
                    exception = Exception(msg)
                else:
                    if i == 0:
                        GrpcUser.first_token_times.append(int((time.time() - start_time) * 1000))
                    GrpcUser.total_tokens += 1
                    print(f"Total tokens output: {GrpcUser.total_tokens}", end="\r", flush=True)
                    responses.append(resp)
                    response_length = sys.getsizeof(responses)
            response_length = sys.getsizeof(responses)
        except Exception as e:
            GrpcUser.total_failures += 1
            exception = e
            log.error(f"Request raised exception '{e}'", stack_info=True)
        # else:
        #   if resp.status.code != status_code_pb2.SUCCESS:
        #     GrpcUser.total_failures += 1
        #     msg = f"Request returned but had response status code '{resp.status.code}' with body '{resp}'"
        #     log.warning(msg)
        #     exception = Exception(msg)

        response_time = int((time.time() - start_time) * 1000)
        GrpcUser.response_times.append(response_time)
        events.request.fire(
            request_type="client",
            name=name,
            response_time=response_time,
            response_length=response_length,
            exception=exception,
            response=resp,
        )
        return responses
