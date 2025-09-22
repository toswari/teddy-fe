# ClassifAI 🛰️

**ClassifAI** is an intelligent document classification system that uses advanced AI models to classify documents according to the Office of the Director of National Intelligence (ODNI) Classification Guide. The application provides a streamlined interface for analyzing text and determining appropriate security classifications.

## 🚀 Features

- **Multiple AI Models**: Choose from 9 different state-of-the-art language models:
  - Claude 3.5 Sonnet
  - GPT OSS 120B
  - GPT 4o
  - Grok 3
  - Llama 3.2 (3B)
  - Gemma 3 (12B)-it
  - Qwen 2.5-VL-7B-Instruct
  - Phi-4
  - Qwen QwQ-32B

- **ODNI Classification Guide Integration**: Built-in comprehensive ODNI Classification Guide (Version 2.1) covering:
  - Foreign Intelligence Surveillance Act (FISA) classifications
  - Human Resources Management classifications
  - Location and facility classifications
  - Collection system classifications
  - Organization and association classifications
  - Procurement classifications
  - Requirements management classifications

- **Interactive Sample Inputs**: Pre-built sample scenarios with contextual icons:
  - 🛰️ Secure Intelligence Dissemination Systems
  - 🔍 NCTC FISA Auditor Operations
  - 👥 ODNI Recruitment and Personnel
  - 📋 Department of Defense Contracts
  - 📊 Intelligence Aggregation and Analysis
  - 🕳️ Covert Analytical Hub Operations
  - ⚖️ FISA Minimization Approvers
  - 💬 Personal Communications

- **Real-time Streaming**: Live streaming responses with typing indicators
- **Configurable Parameters**: Adjustable temperature, token limits, and focus settings
- **Chat History**: Persistent conversation history with clear chat functionality
- **Responsive UI**: Clean, modern interface with proper column alignment

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Clarifai API credentials
- Streamlit

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/toswari-ai/ClassifAI.git
   cd ClassifAI
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Streamlit secrets:**

   Create `.streamlit/secrets.toml` with your Clarifai credentials:

   ```toml
   CLARIFAI_PAT = "your_clarifai_personal_access_token"
   CLARIFAI_USER_ID = "your_clarifai_user_id"
   ```

4. **Run the application:**

   ```bash
   streamlit run app.py
   ```

## 🎯 Usage

### Basic Classification

1. **Launch the application** using `streamlit run app.py`
2. **Select a model** from the sidebar dropdown
3. **Choose a sample input** or enter your own text
4. **Review the classification** results based on ODNI guidelines

### Model Configuration

In the sidebar, you can adjust:

- **Classification Guide**: Currently supports ODNI Classification Guide Version 2.1
- **LLM Model**: Choose from 9 available models
- **Temperature** (0.0-1.0): Controls response creativity
- **Max Tokens** (100-5000): Sets maximum response length
- **Top-P** (0.1-1.0): Controls response focus

### Sample Scenarios

The application includes 8 pre-configured sample scenarios that demonstrate different classification levels:

- **Unclassified (U)**: Personal messages, general contracts
- **Confidential (C)**: Aggregated unclassified data
- **Secret (S)**: FISA operations, personnel details, location information
- **Top Secret (TS)**: Specific collection capabilities, classified analysis

## 🏗️ Architecture

### Core Components

- **Streamlit Frontend**: Interactive web interface
- **Clarifai Integration**: Multiple LLM model access
- **Classification Engine**: ODNI guide-based classification logic
- **Session Management**: Chat history and state management

### Key Features

- **Error Handling**: Retry logic with exponential backoff
- **Streaming Responses**: Real-time text generation
- **Caching**: Model instance caching for performance
- **Responsive Design**: Mobile-friendly interface

## 📋 Requirements

See `requirements.txt` for complete dependency list. Key dependencies include:

- `streamlit==1.44.1` - Web application framework
- `clarifai==11.3.0` - AI model integration
- `streamlit_lottie` - Loading animations
- `tenacity` - Retry logic
- `requests` - HTTP client

## 🔐 Security & Compliance

This application is designed for educational and demonstration purposes. When working with classified information:

- Ensure proper security clearances
- Follow organizational data handling policies
- Use appropriate secure environments
- Validate classifications with official sources

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/enhancement`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/enhancement`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- ODNI Classification Guide for classification standards
- Clarifai for AI model infrastructure
- Streamlit for the web application framework
- The open-source community for various dependencies

## 📞 Support

For questions, issues, or contributions:

- **Repository**: [https://github.com/Clarifai/PS-Field-Engineering/blob/main/sales_engineering/Demos/ClassifAI/](https://github.com/Clarifai/PS-Field-Engineering/blob/main/sales_engineering/Demos/ClassifAI/)
- **Issues**: Report bugs and feature requests via GitHub Issues

---

**Note**: This application is for educational and demonstration purposes. Always consult official classification authorities for actual document classification requirements.
