#!/usr/bin/env python3
"""
Clarifai Multimodal Chatbot

A Streamlit-based web application that allows users to:
- Upload images and ask questions about them
- Select different multimodal AI models from a dropdown menu
- Have interactive conversations with AI models
- View conversation history

Features:
- Image upload with preview
- Model selection sidebar
- Real-time chat interface
- Conversation history
- Error handling and user feedback

Author: Clarifai
Last Updated: 2025
Requirements: streamlit, clarifai>=11.6.0, pillow
"""

import streamlit as st
import os
from clarifai.client.model import Model
from clarifai.client.input import Inputs
from PIL import Image
import io
import base64
import tempfile
import asyncio
import threading

def create_raw_input(image_path, final_prompt):
    """Create input using raw Clarifai protos to avoid MergeFrom issues"""
    try:
        from clarifai_grpc.grpc.api import resources_pb2
        from clarifai_grpc.grpc.api.resources_pb2 import Input
        
        # Create input using protobuf directly
        input_proto = Input()
        input_proto.id = ""  # Empty ID
        
        # Set text data
        input_proto.data.text.raw = final_prompt
        
        if image_path.startswith('http'):
            # For URLs
            input_proto.data.image.url = image_path
        else:
            # For local files, read as bytes
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            input_proto.data.image.base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        return input_proto
        
    except Exception as proto_error:
        # Fallback to the SDK method
        return create_alternative_input(image_path, final_prompt)

def create_alternative_input(image_path, final_prompt):
    """Alternative input creation method to avoid MergeFrom errors"""
    try:
        if image_path.startswith('http'):
            # For URLs, use the standard method
            return Inputs.get_multimodal_input(
                input_id="",  # Try empty input_id
                image_url=image_path,
                raw_text=final_prompt
            )
        else:
            # For local files, read as bytes and use the bytes method
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            # Try using image_bytes parameter (documented method)
            return Inputs.get_multimodal_input(
                input_id="",  # Try empty input_id
                image_bytes=image_bytes,
                raw_text=final_prompt
            )
    except Exception as e:
        # Final fallback - try without input_id at all
        try:
            if image_path.startswith('http'):
                return Inputs.get_multimodal_input(
                    image_url=image_path,
                    raw_text=final_prompt
                )
            else:
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
                return Inputs.get_multimodal_input(
                    image_bytes=image_bytes,
                    raw_text=final_prompt
                )
        except Exception as e2:
            # Last resort - use the file path method
            return Inputs.get_multimodal_input(
                image_file=image_path,
                raw_text=final_prompt
            )

def get_config(section, key, default=None):
    """Get configuration from app_config.toml or fallback to secrets.toml"""
    try:
        import toml
        try:
            with open('app_config.toml', 'r') as f:
                config = toml.load(f)
                if section in config and key in config[section]:
                    return config[section][key]
        except (FileNotFoundError, KeyError):
            pass
        
        # Fallback to secrets
        try:
            return st.secrets[section][key]
        except (KeyError, FileNotFoundError):
            pass
    except Exception:
        pass
    
    return default

def get_config_section(section):
    """Get entire configuration section from app_config.toml or fallback to secrets.toml"""
    try:
        import toml
        try:
            with open('app_config.toml', 'r') as f:
                config = toml.load(f)
                if section in config:
                    return config[section]
        except (FileNotFoundError, KeyError):
            pass
        
        # Fallback to secrets
        try:
            return st.secrets[section]
        except (KeyError, FileNotFoundError):
            pass
    except Exception:
        pass
    
    return {}

# Page configuration using helper function
app_config = get_config_section("app")
page_title = app_config.get("title", "IKEA DAM Chatbot")
page_icon = app_config.get("page_icon", "🏠")
layout = app_config.get("layout", "wide")

st.set_page_config(
    page_title=page_title,
    page_icon=page_icon,
    layout=layout,
    initial_sidebar_state="expanded"
)

# Custom CSS for IKEA-inspired styling
theme_config = get_config_section("theme")
ikea_blue = "#003078"  # IKEA's signature blue
ikea_yellow = "#FFDB00"  # IKEA's signature yellow
ikea_light_gray = "#F5F5F5"  # IKEA's light background
ikea_white = "#FFFFFF"  # IKEA's clean white
ikea_dark_gray = "#484848"  # IKEA's text color

st.markdown(f"""
<style>
    /* IKEA-inspired color scheme and styling */
    .main-header {{
        text-align: center;
        padding: 2rem 1rem;
        background: linear-gradient(135deg, {ikea_blue} 0%, #004c9e 100%);
        color: {ikea_white};
        border-radius: 0;
        margin-bottom: 2rem;
        box-shadow: 0 2px 8px rgba(0,48,120,0.15);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    .main-header h1 {{
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        text-shadow: none;
    }}
    
    .main-header p {{
        font-size: 1.1rem;
        opacity: 0.95;
        font-weight: 400;
    }}
    
    .chat-message {{
        padding: 1.25rem;
        border-radius: 8px;
        margin: 0.75rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    .user-message {{
        background-color: {ikea_white};
        border: 1px solid {ikea_light_gray};
        border-left: 4px solid {ikea_blue};
        color: {ikea_dark_gray};
    }}
    
    .ai-message {{
        background-color: {ikea_light_gray};
        border: 1px solid #E8E8E8;
        border-left: 4px solid {ikea_yellow};
        color: {ikea_dark_gray};
    }}
    
    .error-message {{
        background-color: #FFF5F5;
        border: 1px solid #FED7D7;
        border-left: 4px solid #E53E3E;
        color: #C53030;
    }}
    
    /* IKEA-style sample cards */
    .sample-card {{
        background-color: {ikea_white};
        padding: 1rem;
        border-radius: 8px;
        margin: 0.75rem 0;
        border: 1px solid #E8E8E8;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    
    .sample-card:hover {{
        border-color: {ikea_blue};
        box-shadow: 0 4px 12px rgba(0,48,120,0.1);
        transform: translateY(-1px);
    }}
    
    /* IKEA-style buttons */
    .stButton > button {{
        background-color: {ikea_blue};
        color: {ikea_white};
        border: none;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.9rem;
        padding: 0.6rem 1.2rem;
        transition: all 0.2s ease;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    .stButton > button:hover {{
        background-color: #002c6b;
        box-shadow: 0 2px 8px rgba(0,48,120,0.2);
        transform: translateY(-1px);
    }}
    
    /* Secondary button style for "Use" buttons */
    .stButton > button[kind="secondary"] {{
        background-color: {ikea_white};
        color: {ikea_blue};
        border: 2px solid {ikea_blue};
    }}
    
    .stButton > button[kind="secondary"]:hover {{
        background-color: {ikea_light_gray};
        color: {ikea_blue};
        border-color: #002c6b;
    }}
    
    /* IKEA-style sidebar */
    .css-1d391kg {{
        background-color: {ikea_white};
        border-right: 1px solid #E8E8E8;
    }}
    
    /* IKEA-style headings */
    h1, h2, h3 {{
        color: {ikea_dark_gray};
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-weight: 700;
    }}
    
    /* IKEA-style success/info messages */
    .stSuccess {{
        background-color: #F0FFF4;
        border: 1px solid #9AE6B4;
        border-left: 4px solid #38A169;
        color: #22543D;
    }}
    
    .stInfo {{
        background-color: #EBF8FF;
        border: 1px solid #90CDF4;
        border-left: 4px solid {ikea_blue};
        color: #1A365D;
    }}
    
    /* IKEA-style input fields */
    .stTextInput > div > div > input {{
        border: 2px solid #E8E8E8;
        border-radius: 4px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        transition: border-color 0.2s ease;
    }}
    
    .stTextInput > div > div > input:focus {{
        border-color: {ikea_blue};
        box-shadow: 0 0 0 1px {ikea_blue};
    }}
    
    /* IKEA-style selectbox */
    .stSelectbox > div > div {{
        border: 2px solid #E8E8E8;
        border-radius: 4px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    .stSelectbox > div > div:focus-within {{
        border-color: {ikea_blue};
        box-shadow: 0 0 0 1px {ikea_blue};
    }}
    
    /* IKEA-style file uploader */
    .uploadedFile {{
        border: 2px dashed #E8E8E8;
        border-radius: 8px;
        background-color: {ikea_light_gray};
        transition: all 0.2s ease;
    }}
    
    .uploadedFile:hover {{
        border-color: {ikea_blue};
        background-color: {ikea_white};
    }}
    
    /* IKEA yellow accent for important elements */
    .ikea-accent {{
        background-color: {ikea_yellow};
        color: {ikea_dark_gray};
        padding: 0.5rem 1rem;
        border-radius: 4px;
        font-weight: 600;
    }}
    
    /* IKEA-style metrics */
    .stMetric {{
        background-color: {ikea_white};
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1rem;
    }}
    
    /* Clean IKEA typography */
    .stMarkdown {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: {ikea_dark_gray};
        line-height: 1.6;
    }}
    
    /* IKEA-style spinner */
    .stSpinner > div {{
        border-top-color: {ikea_blue} !important;
    }}
    
    /* Consistent sample image sizing */
    .sample-image {{
        width: 100%;
        height: 200px;
        object-fit: cover;
        border-radius: 8px;
        border: 1px solid #E8E8E8;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }}
    
    /* Highlighted sample card styling */
    .sample-card-highlighted {{
        background-color: {ikea_white};
        padding: 1rem;
        border-radius: 8px;
        margin: 0.75rem 0;
        border: 5px solid {ikea_blue} !important;
        box-shadow: 0 8px 25px rgba(0,48,120,0.2) !important;
        transform: translateY(-3px);
        transition: all 0.3s ease;
    }}
    
    .sample-image-highlighted {{
        width: 100%;
        height: 200px;
        object-fit: cover;
        border-radius: 8px;
        border: 4px solid {ikea_blue};
        margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(0,48,120,0.25);
        transition: all 0.3s ease;
    }}
</style>
""", unsafe_allow_html=True)

# Available multimodal models - Tested and working
MULTIMODAL_MODELS = {
    "MiniCPM-o-2.6 (Recommended)": "https://clarifai.com/openbmb/miniCPM/models/MiniCPM-o-2_6-language",
    "GPT-5": "https://clarifai.com/openai/chat-completion/models/gpt-5",
    "GPT-4o": "https://clarifai.com/openai/chat-completion/models/gpt-4o",
    "GPT-4o Mini": "https://clarifai.com/openai/chat-completion/models/gpt-4o-mini",
    "Claude-3.5 Sonnet": "https://clarifai.com/anthropic/completion/models/claude-3_5-sonnet",
    "MM-Poly-8B": "https://clarifai.com/clarifai/main/models/mm-poly-8b",
}

def initialize_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'image_url' not in st.session_state:
        st.session_state.image_url = None
    if 'selected_sample_card' not in st.session_state:
        st.session_state.selected_sample_card = None
    if 'pending_analysis' not in st.session_state:
        st.session_state.pending_analysis = None
    
    # Load configuration from config.toml
    models_config = get_config_section("models")
    st.session_state.max_conversation_length = models_config.get("max_conversation_length", 50)
    st.session_state.default_model = "MM-Poly-8B"
    
    ui_config = get_config_section("ui")
    st.session_state.show_sample_images = ui_config.get("show_sample_images", True)
    st.session_state.show_conversation_stats = ui_config.get("show_conversation_stats", True)
    st.session_state.enable_image_preview = ui_config.get("enable_image_preview", True)
    st.session_state.max_image_size_mb = ui_config.get("max_image_size_mb", 10)

def check_api_key():
    """Check if Clarifai API key is set using Streamlit secrets"""
    try:
        pat = st.secrets["clarifai"]["PAT"]
        if not pat or pat == "your_clarifai_api_key_here":
            raise ValueError("API key not configured")
        return pat
    except (KeyError, FileNotFoundError):
        st.error("""
        ❌ **Clarifai API Key Missing**
        
        Please configure your Clarifai API key in Streamlit secrets:
        
        **Method 1: Local Development**
        1. Create `.streamlit/secrets.toml` file
        2. Copy from `.streamlit/secrets.toml.example`
        3. Replace `your_clarifai_api_key_here` with your actual API key
        
        **Method 2: Streamlit Cloud**
        1. Go to your app settings in Streamlit Cloud
        2. Add secrets in the "Secrets" tab
        3. Use the same format as in `secrets.toml.example`
        
        **Get your API key from:** https://clarifai.com/settings/security
        """)
        st.stop()
    except ValueError:
        st.error("""
        ❌ **Clarifai API Key Not Configured**
        
        Please edit `.streamlit/secrets.toml` and replace `your_clarifai_api_key_here` 
        with your actual Clarifai API key.
        
        **Get your API key from:** https://clarifai.com/settings/security
        """)
        st.stop()

def run_prediction_in_thread(model_url, multi_inputs, pat):
    """Run prediction in a separate thread to avoid asyncio conflicts"""
    def _predict():
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Make prediction
            model = Model(url=model_url, pat=pat)
            prediction = model.predict(inputs=[multi_inputs])
            
            # Extract response
            if prediction.outputs and prediction.outputs[0].data.text:
                return prediction.outputs[0].data.text.raw
            else:
                return "I couldn't generate a response. Please try again with a different question or image."
                
        except Exception as e:
            return f"Thread Error: {str(e)}"
        finally:
            # Clean up the event loop
            try:
                loop.close()
            except:
                pass
    
    # Use a simple container to get the result
    result = [None]
    exception = [None]
    
    def thread_target():
        try:
            result[0] = _predict()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join(timeout=60)  # 60 second timeout
    
    if thread.is_alive():
        return "Request timed out. Please try again."
    
    if exception[0]:
        return f"Threading Error: {str(exception[0])}"
        
    return result[0] or "No response received."

def ensure_event_loop():
    """Ensure there's an event loop in the current thread"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def upload_image_to_temp(uploaded_file):
    """Save uploaded image to temporary file and return URL"""
    try:
        # Get file extension from uploaded file
        file_ext = uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else 'jpg'
        if file_ext not in ['jpg', 'jpeg', 'png', 'webp']:
            file_ext = 'jpg'
        
        # Create a temporary file with proper extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

def get_multimodal_response(model_url, image_path, user_question, pat):
    """Get response from multimodal model using configured prompts"""
    try:
        # Validate API key
        if not pat or pat == "your_clarifai_api_key_here":
            return "❌ API Error: Invalid or missing Clarifai API key. Please check your configuration."
        
        # Ensure we have an event loop (fixes asyncio errors)
        ensure_event_loop()
        
        # Load prompt configuration from config.toml
        prompts_config = get_config_section("prompts")
        system_prompt = prompts_config.get("system_prompt", """You are an IKEA specialist AI assistant analyzing home interior images. 
        Focus on room types, furniture, design styles, and home activities.""")
        user_prompt_template = prompts_config.get("user_prompt_template", "{user_question}")
        
        # Load IKEA Taxonomy requirement from config
        taxonomy_prompt = prompts_config.get("taxonomy_prompt", """
        
        IMPORTANT: In addition to answering the user's question, you MUST also identify and return the relevant IKEA taxonomy categories from this image:

        **Room Types:** Bedroom, Living room, Outdoor, Dining room, Kitchen, Bathroom, Home office, Gaming room, Laundry, Hallway, Children's room, Garage

        **Interior Design Styles:** Japandi, Mid-century modern, Farmhouse, Modern cottage, Boho

        **Life at Home Activities:** Sleep, Store & organise, Cook

        **Other Categories:** Moods, Pets, Food

        Please format your response as:
        1. Answer to the user's question
        2. **IKEA Taxonomy Detected:**
           - Room Type: [identified room type(s)]
           - Design Style: [identified style(s)]
           - Activities: [identified activities]
           - Other: [any other relevant categories like moods, pets, food]
        """)
        
        # Load IKEA Collection Classification prompt from config
        ikea_collection_prompt = prompts_config.get("ikea_collection_prompt", """
        Analyze the uploaded image of a product or room setting. Based on its design, style, materials, colors, and overall aesthetic, classify the image into one of the following IKEA collections:
        BRÄNNBOLL, HÖSTAGILLE, Tyg collection, SÖTRÖNN, Nytillverkad, TESAMMANS, BRÖGGAN, DAKSJUS, VINTERFINT, AFTONSPARV, Design by Ilse Crawford, MÄVINN, BLÅVINGAD, HÄSTHAGE, STOCKHOLM, SKOGSDUVA, FRÖJDA, TJÄRLEK, OMMJÄNGE, KÖSSEBÄR, KUSTFYR.
        Return the name of the most fitting IKEA collection for the image. If the image does not match any collection confidently, return 'No Match.'
        """)

        # Format the complete prompt
        if "{user_question}" in user_prompt_template:
            complete_prompt = user_prompt_template.format(user_question=user_question)
        else:
            complete_prompt = user_question

        # Combine system prompt with user prompt and appropriate classification
        if "ikea collection" in user_question.lower() or "collection" in user_question.lower():
            final_prompt = f"{system_prompt}\n\n{complete_prompt}\n\n{ikea_collection_prompt}"
        else:
            final_prompt = f"{system_prompt}\n\n{complete_prompt}\n\n{taxonomy_prompt}" if system_prompt else f"{complete_prompt}\n\n{taxonomy_prompt}"

        # Optional debug: show the exact prompt being sent and verify the design styles guide is included
        debug_prompts = prompts_config.get("debug_prompts", False)
        if debug_prompts:
            try:
                with st.expander("Prompt (debug view)"):
                    st.code(final_prompt)
                    if "DESIGN STYLES CLASSIFICATION GUIDE" in taxonomy_prompt:
                        st.info("Using enhanced design styles classification guide in taxonomy prompt.")
                    else:
                        st.warning("Design styles guide not detected in taxonomy prompt.")
                    
                    # Debug API key (show only first/last 4 chars)
                    masked_pat = f"{pat[:4]}...{pat[-4:]}" if len(pat) > 8 else "***"
                    st.info(f"Using API key: {masked_pat}")
            except Exception:
                # Do not fail the app if UI debug rendering isn't possible in this context
                pass
        
        # Create multimodal input using multiple fallback approaches
        is_proto_input = False  # Initialize the variable
        try:
            # Try the raw protobuf approach first
            multi_inputs = create_raw_input(image_path, final_prompt)
            
            # If we got a protobuf object, we'll use it directly in the prediction
            is_proto_input = hasattr(multi_inputs, 'data')
            
        except Exception as input_error:
            # Fallback to SDK method
            try:
                multi_inputs = create_alternative_input(image_path, final_prompt)
                is_proto_input = False
            except Exception as fallback_error:
                return f"Input Error: Both input methods failed. Proto error: {str(input_error)}. SDK error: {str(fallback_error)}. Please try a different image format."
        
        # Try normal prediction first
        try:
            model = Model(url=model_url, pat=pat)
            
            # Debug: Check input type and structure
            debug_prompts = prompts_config.get("debug_prompts", False)
            if debug_prompts:
                st.write(f"Debug: Input type: {type(multi_inputs)}")
                st.write(f"Debug: Is proto input: {is_proto_input}")
                st.write(f"Debug: Model URL: {model_url}")
                st.write(f"Debug: Image path type: {type(image_path)}")
            
            # Use different prediction methods based on input type
            if is_proto_input:
                # Use protobuf input directly
                prediction = model.predict(inputs=[multi_inputs])
            else:
                # Use SDK input
                prediction = model.predict(inputs=[multi_inputs])
            
            # Extract response
            if prediction.outputs and len(prediction.outputs) > 0 and prediction.outputs[0].data.text:
                return prediction.outputs[0].data.text.raw
            else:
                return "I couldn't generate a response. The model returned no output. Please try again with a different question or image."
        
        except Exception as pred_error:
            error_msg = str(pred_error)
            # Handle specific Clarifai errors
            if "MergeFrom" in error_msg:
                return f"API Error: Invalid input format - {error_msg}. Please try uploading a different image or check the image format."
            elif "event loop" in error_msg.lower() or "asyncio" in error_msg.lower():
                st.warning("🔄 Retrying with alternative method...")
                return run_prediction_in_thread(model_url, multi_inputs, pat)
            else:
                return f"Prediction Error: {error_msg}. Please try again or contact support if the problem persists."
            
    except Exception as e:
        error_msg = str(e)
        # Final fallback: try threaded approach for asyncio issues
        if "event loop" in error_msg.lower() or "asyncio" in error_msg.lower():
            try:
                return run_prediction_in_thread(model_url, multi_inputs, pat)
            except Exception as thread_e:
                return f"AsyncIO Error: {str(thread_e)}. Try refreshing the page or restarting the application."
        elif "MergeFrom" in error_msg:
            return f"API Configuration Error: {error_msg}. This may be due to an incompatible image format or API version issue."
        else:
            return f"Unexpected Error: {error_msg}. Please try again or use a different image/question."

def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Check API key
    pat = check_api_key()
    
    # Header with configurable title
    app_config = get_config_section("app")
    app_title = app_config.get("title", "IKEA DAM Chatbot")
    
    st.markdown(f"""
    <div class="main-header">
        <h1>🏠 {app_title}</h1>
        <p>Professional interior analysis with comprehensive taxonomy classification</p>
        <div style="margin-top: 1rem; opacity: 0.9; font-size: 0.9rem;">
            Powered by Clarifai AI • Upload images • Get instant insights
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for model selection and image upload
    with st.sidebar:
        st.header("⚙️ Settings")
        st.markdown('<div style="margin-bottom: 1.5rem; color: #666; font-size: 0.9rem;">Configure your analysis preferences</div>', unsafe_allow_html=True)
        
        # Model selection
        st.subheader("🧠 Select AI Model")
        
        # Get default model index
        default_index = 0
        model_keys = list(MULTIMODAL_MODELS.keys())
        if st.session_state.default_model in model_keys:
            default_index = model_keys.index(st.session_state.default_model)
        
        selected_model_name = st.selectbox(
            "Choose a multimodal model:",
            model_keys,
            index=default_index,
            help="Different models have different strengths. MiniCPM-o-2.6 is recommended for general use."
        )
        selected_model_url = MULTIMODAL_MODELS[selected_model_name]
        
        # Clear conversation when model changes
        if 'previous_model' not in st.session_state:
            st.session_state.previous_model = selected_model_name
        elif st.session_state.previous_model != selected_model_name:
            st.session_state.messages = []
            st.session_state.previous_model = selected_model_name
            st.success(f"🔄 Conversation cleared - switched to {selected_model_name}")
        
        st.info(f"**Selected:** {selected_model_name}")
        
        # Image upload section
        st.subheader("📷 Image Input")
        
        # Option 1: Upload image
        max_size_mb = st.session_state.max_image_size_mb
        uploaded_file = st.file_uploader(
            "Upload an image:",
            type=['png', 'jpg', 'jpeg', 'webp'],
            help=f"Upload an image file to analyze (max {max_size_mb}MB)"
        )
        
        # Check file size
        if uploaded_file is not None:
            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            if file_size_mb > max_size_mb:
                st.error(f"❌ File too large! Maximum size is {max_size_mb}MB. Your file is {file_size_mb:.1f}MB.")
                uploaded_file = None
        
        # Option 2: Image URL
        image_url_input = st.text_input(
            "Or enter image URL:",
            placeholder="https://www.ikea.com/ext/ingkadam/m/26ec93d9bb2482e/original/PH204378.jpg",
            help="Enter a direct URL to an image"
        )
        
        # Process image input
        current_image = None
        image_source = None
        
        if uploaded_file is not None:
            # Clear selected sample card and pending analysis when user uploads their own image
            st.session_state.selected_sample_card = None
            st.session_state.pending_analysis = None
            
            current_image = upload_image_to_temp(uploaded_file)
            image_source = "uploaded"
            
            # Clear conversation when new image is uploaded
            if 'previous_uploaded_file' not in st.session_state:
                st.session_state.previous_uploaded_file = uploaded_file.name
            elif st.session_state.previous_uploaded_file != uploaded_file.name:
                st.session_state.messages = []
                st.session_state.previous_uploaded_file = uploaded_file.name
                st.success("🔄 Conversation cleared - new image uploaded!")
            else:
                st.success("✅ Image uploaded successfully!")
            
            # Display uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_column_width=True)
            
        elif image_url_input:
            # Clear selected sample card and pending analysis when user enters their own URL
            st.session_state.selected_sample_card = None
            st.session_state.pending_analysis = None
            
            current_image = image_url_input
            image_source = "url"
            
            # Clear conversation when new URL is entered
            if 'previous_image_url' not in st.session_state:
                st.session_state.previous_image_url = image_url_input
            elif st.session_state.previous_image_url != image_url_input:
                st.session_state.messages = []
                st.session_state.previous_image_url = image_url_input
                st.success("🔄 Conversation cleared - new image URL set!")
            else:
                st.success("✅ Image URL set!")
            
            # Try to display URL image
            try:
                st.image(image_url_input, caption="Image from URL", use_column_width=True)
            except:
                st.warning("⚠️ Cannot preview image from URL, but it will be processed.")
        

        
        # Clear conversation
        if st.button("🗑️ Clear Conversation"):
            st.session_state.messages = []
            st.rerun()
        
        # Models information section
        st.subheader("🔧 Models Info")
        st.markdown("""
        **MiniCPM-o-2.6**: Best for general vision tasks
        
        **GPT-4o**: Excellent for detailed analysis
        
        **Claude-3.5 Sonnet**: Great for creative descriptions
        
        **MM-Poly-8B**: Good for visual reasoning
        """)
        
        # Conversation statistics (moved to sidebar)
        if st.session_state.messages and st.session_state.show_conversation_stats:
            st.subheader("📊 Conversation Stats")
            st.metric("Messages", len(st.session_state.messages))
            user_messages = len([m for m in st.session_state.messages if m["role"] == "user"])
            st.metric("Questions Asked", user_messages)
            
            # Show warning if approaching max conversation length
            if len(st.session_state.messages) > st.session_state.max_conversation_length * 0.8:
                st.warning(f"⚠️ Approaching max conversation length ({st.session_state.max_conversation_length} messages)")
        
        # Add conversation management
        if len(st.session_state.messages) >= st.session_state.max_conversation_length:
            st.info("💡 Conversation history is full. Consider clearing to start fresh.")
            if st.button("🗑️ Auto-clear old messages", key="sidebar_auto_clear"):
                # Keep only the last 10 messages
                st.session_state.messages = st.session_state.messages[-10:]
                st.rerun()
    
    # Sample images section (moved to main area)
    if st.session_state.show_sample_images:
        st.subheader("🏠 Explore Sample Rooms")
        st.markdown('<div style="margin-bottom: 1.5rem; color: #666; font-size: 1rem;">Quick-start with IKEA sample rooms - Click to analyze instantly</div>', unsafe_allow_html=True)
        
        # Load sample images from configuration
        prompts_config = get_config_section("prompts")
        configured_samples = prompts_config.get("sample_images", [])
        if configured_samples:
            sample_images = {name: url for name, url in configured_samples}
        else:
            # Fallback sample images
            sample_images = {
                "Modern Living Room": "https://samples.clarifai.com/metro-north.jpg",
                "Scandinavian Bedroom": "https://samples.clarifai.com/wedding.jpg",
                "Kitchen": "https://samples.clarifai.com/travel.jpg"
            }
        
        # Create responsive columns for sample cards
        sample_cols = st.columns(len(sample_images))
        
        for idx, (name, url) in enumerate(sample_images.items()):
            with sample_cols[idx]:
                # Use Streamlit's built-in popover for image preview (Best Practice)
                with st.popover(f"🖼️ {name}", use_container_width=True):
                    st.image(url, caption=f"{name} - Full Size Preview", use_column_width=True)
                    st.markdown(f"**Room Type:** {name}")
                    st.markdown("**Features:** AI taxonomy classification ready")
                
                # Display thumbnail with consistent sizing using custom CSS
                # Use highlighted styling if this card is selected
                image_class = "sample-image-highlighted" if st.session_state.selected_sample_card == name else "sample-image"
                st.markdown(f'''
                <div style="text-align: center;">
                    <img src="{url}" class="{image_class}" alt="{name}" title="{name}">
                </div>
                ''', unsafe_allow_html=True)
                
                st.markdown(f"**{name}**")
                st.caption("Click the popover above for full-size preview")
                
                # Create action buttons with IKEA styling
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    # Analyze button that runs prediction automatically
                    if st.button(f"🔍 Analyze", key=f"main_analyze_{name}", help=f"Analyze {name} with AI and get taxonomy", use_container_width=True):
                        # First, set this card as selected for highlighting
                        st.session_state.selected_sample_card = name
                        
                        # Clear conversation when switching to new sample image
                        if 'previous_sample_image' not in st.session_state:
                            st.session_state.previous_sample_image = url
                        elif st.session_state.previous_sample_image != url:
                            st.session_state.messages = []
                            st.session_state.previous_sample_image = url
                        
                        # Set the image
                        st.session_state.image_url = url
                        
                        # Set flag to trigger analysis after rerun
                        st.session_state.pending_analysis = {
                            'name': name,
                            'url': url,
                            'model_url': selected_model_url,
                            'model_name': selected_model_name
                        }
                        
                        # Rerun to show the highlighted card first
                        st.rerun()
                    
                with btn_col2:
                    # Use button for just setting the image without analysis
                    if st.button(f"📎 Use", key=f"main_use_{name}", help=f"Set {name} as current image for questions", use_container_width=True):
                        # Set this card as selected for highlighting
                        st.session_state.selected_sample_card = name
                        
                        # Clear conversation when switching to new sample image
                        if 'previous_sample_image' not in st.session_state:
                            st.session_state.previous_sample_image = url
                        elif st.session_state.previous_sample_image != url:
                            st.session_state.messages = []
                            st.session_state.previous_sample_image = url
                            st.success(f"🔄 Conversation cleared - {name} set!")
                        else:
                            st.success(f"✅ {name} set!")
                        
                        st.session_state.image_url = url
                        st.rerun()
        
        # Handle pending analysis after card highlighting
        if 'pending_analysis' in st.session_state and st.session_state.pending_analysis:
            analysis_data = st.session_state.pending_analysis
            
            # Clear the pending analysis flag
            st.session_state.pending_analysis = None
            
            # Add a default analysis question to messages
            default_question = "Analyze this image and identify all IKEA taxonomy categories"
            st.session_state.messages.append({"role": "user", "content": default_question})
            
            # Get AI response with spinner
            with st.spinner(f"🤔 {analysis_data['model_name']} is analyzing {analysis_data['name']}..."):
                ai_response = get_multimodal_response(
                    analysis_data['model_url'], 
                    analysis_data['url'], 
                    default_question, 
                    pat
                )
            
            # Add AI response to history
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()
        
        # Add Suggested Questions section under sample images
        prompts_config = get_config_section("prompts")
        default_questions = prompts_config.get("default_questions", [
            "What do you see in this image?",
            "What time of day is it?",
            "Describe the colors and mood"
        ])
        
        if default_questions:
            st.subheader("💡 Suggested Questions")
            st.markdown('<div style="margin-bottom: 1rem; color: #666; font-size: 1rem;">Quick questions to get started with your analysis</div>', unsafe_allow_html=True)
            
            # Create responsive columns for suggested questions
            question_cols = st.columns(min(3, len(default_questions)))
            
            for i, question in enumerate(default_questions):
                with question_cols[i % 3]:  # Cycle through columns
                    if st.button(f"📝 {question}", key=f"suggested_{i}", use_container_width=True):
                        # Add the question to chat if there's an image
                        if st.session_state.image_url or current_image:
                            st.session_state.messages.append({"role": "user", "content": question})
                            
                            # Get AI response
                            image_to_use = current_image or st.session_state.image_url
                            with st.spinner("🤔 Analyzing..."):
                                ai_response = get_multimodal_response(
                                    selected_model_url, 
                                    image_to_use, 
                                    question, 
                                    pat
                                )
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})
                            st.rerun()
                        else:
                            st.error("❌ Please upload an image first!")
        
        st.markdown("---")  # Visual separator
    
    # Main chat interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("💬 Chat Interface")
        
        # Display conversation history
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-message user-message"><strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message ai-message"><strong>AI:</strong> {message["content"]}</div>', unsafe_allow_html=True)
        
        # Chat input with configurable placeholder
        prompts_config = get_config_section("prompts")
        chat_placeholder = prompts_config.get("chat_placeholder", "Ask a question about the image...")
        
        user_input = st.chat_input(chat_placeholder)
        
        if user_input:
            if not current_image and not st.session_state.image_url:
                st.error("❌ Please upload an image or enter an image URL first!")
            else:
                # Use current image or session state image
                image_to_use = current_image or st.session_state.image_url
                
                # Add user message to history
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                # Show processing message
                with st.spinner(f"🤔 {selected_model_name} is analyzing the image..."):
                    # Get AI response
                    ai_response = get_multimodal_response(
                        selected_model_url, 
                        image_to_use, 
                        user_input, 
                        pat
                    )
                
                # Add AI response to history
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # Update session state image
                st.session_state.image_url = image_to_use
                
                # Rerun to update the interface
                st.rerun()
    
    with col2:
        st.subheader("ℹ️ How to Use")
        st.markdown("""
        1. **Select a Model**: Choose from various AI models in the sidebar
        2. **Add an Image**: Upload a file, enter a URL, or use a sample
        3. **Ask Questions**: Type questions about the image in the chat
        4. **Get Responses**: The AI will analyze and respond
        """)
        
        st.subheader("🎯 IKEA Taxonomy Features")
        st.markdown("""
        **Room Types**: Bedroom, Living room, Kitchen, Dining room, Bathroom, Home office, and more
        
        **Design Styles**: Scandinavian, Japandi, Mid-century modern, Minimalist, and others
        
        **Activities**: Sleep, Cook, Work from home, Store & organise, Relax, and more
        
        **Other Elements**: Moods, Pet-friendly features, Food-related items
        """)
        
        st.subheader("� Professional Analysis")
        st.markdown("""
        - **Detailed Classification**: Complete IKEA taxonomy breakdown
        - **Visual Recognition**: Furniture, decor, and layout analysis  
        - **Lifestyle Context**: Activities and mood identification
        - **DAM Integration**: Ready for digital asset management
        """)

if __name__ == "__main__":
    main()
