#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time

import grpc.experimental.gevent as grpc_gevent
from locust import events, task

from locust_v2.utils.grpc_user import GrpcUser

grpc_gevent.init_gevent()


class ApiUser(GrpcUser):
    # wait_time = 0 # in seconds

    req = None

    def _setup_req(self, batch_size=1):
        if self.req is None:
            TEXT = """Testing"""

            kwargs = {
                "prompt": TEXT,
            }
            self.req = kwargs

        return self.req

    @task
    def call_predict(self):
        kwargs = self._setup_req(1)
        # Add timeout to prevent hanging
        kwargs['inference_params'] = {'max_tokens': 500, 'temperature': 0.7}

        # print(req)

        # res = self.model.predict(**kwargs)
        # print(res)
        resp = self.predict(
            "predict on %s" % os.environ['CLARIFAI_MODEL_URL'], self.model.predict, **kwargs
        )

        # if resp.status.code != status_code_pb2.SUCCESS:
        #     raise Exception("Failed to predict: %s" % resp)

    # @task
    # def call_batch_predict(self):

    #   req = self._setup_req(128)
    #   # print(req)
    #   resp = self.predict("predict on %s" % os.environ['CLARIFAI_MODEL_ID'],
    #                       self.stub.PostModelOutputs, req)

    #   if resp.status.code != status_code_pb2.SUCCESS:
    #     raise Exception("Failed to predict: %s" % resp)

    # @task
    # def call_generate(self):
    #   req = self._setup_req()

    #   responses = self.generate("generate on %s" % os.environ['CLARIFAI_MODEL_ID'],
    #                             self.stub.GenerateModelOutputs, req)

    #   if len(responses) == 0:
    #     raise Exception("Failed to get responses, length 0")
    #   if responses[-1].status.code != status_code_pb2.SUCCESS:
    #     raise Exception("Failed to predict: %s" % responses[-1].status.description)

    # This should be customized based on the model you're using.
    # generated_text=""
    # for r in responses:
    # generated_text += r.outputs[0].data.text.raw

    # generated_text = ''.join([r.outputs[0].data.text.raw for r in responses])


# Hook to calculate final metrics after all users stop
@events.quitting.add_listener
def on_quitting(environment, **_kwargs):
    end_time = time.time()
    total_duration = end_time - GrpcUser.test_start_time
    if total_duration > 0:
        rps = GrpcUser.request_count / total_duration
        throughput = GrpcUser.total_tokens / total_duration
        average_response_time = (
            sum(GrpcUser.response_times) / len(GrpcUser.response_times)
            if GrpcUser.response_times
            else 0
        )
        first_token_time = (
            sum(GrpcUser.first_token_times) / len(GrpcUser.first_token_times)
            if len(GrpcUser.first_token_times) > 0
            else -1
        )
        print(f"Total Requests: {GrpcUser.request_count}")
        print(f"Total Failures: {GrpcUser.total_failures}")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Requests per Second (RPS): {rps:.2f}")
        print(f"Throughput (Tokens per Second): {throughput:.2f}")
        print(f"Average Response Time: {average_response_time:.2f} ms")
        print(f'Avg First Token Time: {first_token_time:.2f} ms')
        print(f"Total Tokens: {GrpcUser.total_tokens}")
