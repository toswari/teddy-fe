import time
import streamlit as st

import os
import traceback
import json
from pathlib import Path
from getpass import getpass
from google.protobuf.struct_pb2 import Struct

from clarifai.client.model import Model, Inputs
from clarifai.client.search import Search
from clarifai.client.input import Inputs
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import service_pb2_grpc, service_pb2, resources_pb2
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up Clarifai credentials
CLARIFAI_PAT = st.secrets["CLARIFAI_PAT"]  # Store in Streamlit secrets
USER_ID = st.secrets["CLARIFAI_USER_ID"]  # Store in Streamlit secrets
prompt2= "What is the future of AI?"
MODEL_URL = "https://clarifai.com/meta/Llama-3/models/Llama-3_2-3B-Instruct"
#MODEL_URL= "https://clarifai.com/meta/Llama-4/models/Llama-4-Scout-17B-16E-Instruct"



#odel = Model(url=MODEL_URL, pat=CLARIFAI_PAT)
#print("CLARIFAI_PAT:", CLARIFAI_PAT)  # Debugging line to check if the PAT is loaded correctly

# Predefined model list (can be expanded)
MODEL_MAP = {
    "Qwen2_5-VL-7B-Instruct": "https://clarifai.com/qwen/qwen-VL/models/Qwen2_5-VL-7B-Instruct",
    "Qwen2_5-Coder-7B-Instruct-vllm": "https://clarifai.com/qwen/qwenCoder/models/Qwen2_5-Coder-7B-Instruct-vllm",
    "Llama 3.2 (3B)": "https://clarifai.com/meta/Llama-3/models/Llama-3_2-3B-Instruct",
    "gemma-3n-4b-it-text": "https://clarifai.com/gcp/generate/models/gemma-3n-E4B-it-text",
    "Claude 3.5_sonet": "https://clarifai.com/anthropic/completion/models/claude-3-haiku"
}


@st.cache_resource
def get_model(model_url):
    return Model(url=model_url, pat=CLARIFAI_PAT)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
def stream_prediction(prompt):
    """Enhanced streaming generator with error handling"""
    if not CLARIFAI_PAT:
        yield "🔑 Error: Missing Clarifai PAT in secrets"
        return

    try:
        # Initialize the model
        #model = Model(url=MODEL_URL, pat=CLARIFAI_PAT)
        MODEL_URL = st.session_state.model_url
        print(f"MODEL_URL: {MODEL_URL}")  # Debugging line to check the model URL
        model=get_model(MODEL_URL)
        
        
        print(f"temp: {st.session_state.temperature}")
        print(f"max_tokens: {st.session_state.max_tokens}")
        print(f"top_p: {st.session_state.top_p}")
        
        stream = model.generate_by_bytes(
            input_bytes=prompt.encode(),
            input_type="text",
            inference_params={
                "temperature": st.session_state.temperature,
                "max_tokens": st.session_state.max_tokens,
                "top_p": st.session_state.top_p
            }
        )

        buffer = ""
        for chunk in stream:
            #print(chunk)  # Debugging line to check the chunk content
            status_code = chunk.status.code
            #print(status_code)  # Debugging line to check the status code
            if status_code == 10000:
                text_chunk = chunk.outputs[0].data.text.raw
                buffer += text_chunk
                
                # Flush buffer on sentence boundaries
                if len(buffer) > 30 or any(punct in buffer for punct in ".!?\n"):
                    yield buffer
                    buffer = ""
                    time.sleep(0.02)  # Simulate natural typing speed
            else:
                yield f"⚠️ Error: {chunk.status.description}"
        
        if buffer:  # Final flush
            yield buffer

    except Exception as e:
        yield f"🚨 Critical Error: {str(e)}"


# UI Setup
st.set_page_config(page_title="ClarifAI Chat", layout="wide")
st.title("Clarifai Streaming Chat")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new input
if prompt := st.chat_input("Message ClarifAI"):
    # Add user message to history and display immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Stream response with typing indicator
        for chunk in stream_prediction(prompt):
            full_response += chunk
            message_placeholder.markdown(f"{full_response}▌")
        
        # Final render without cursor
        message_placeholder.markdown(full_response)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": full_response})


      
# Sidebar Configuration
with st.sidebar:
    st.title("Model Settings")
    
    # Model selection
    selected_model = st.selectbox(
        "Choose LLM",
        list(MODEL_MAP.keys()),
        index=3
    )
    
    
    st.session_state.model_url = MODEL_MAP[selected_model]
    print(f"model_url: {st.session_state.model_url}")  # Debugging line to check the model URL
    
    # Inference parameters
    st.session_state.temperature = st.slider(
        "Creativity (Temperature)",
        0.0, 2.0, 0.7
    )
    st.session_state.max_tokens = st.slider(
        "Max Response Length",
        100, 5000, 2000
    )
    st.session_state.top_p = st.slider(
        "Focus (Top-P)",
        0.1, 1.0, 0.9
    )
    
    st.subheader("Debug Info")
    st.write(f"Message count: {len(st.session_state.messages)}")
    if st.session_state.messages:
        st.write("Last message:", st.session_state.messages[-1]["content"][:50] + "...")