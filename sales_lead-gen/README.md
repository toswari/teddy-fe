# Automated Sales Outreach System

A Python application that automatically generates personalized sales outreach messages based on news from RSS feeds. The system uses AI (Clarifai) to analyze articles and create tailored LinkedIn messages.

## Features

- **RSS Feed Monitoring**: Fetch news from Google Alerts and custom RSS feeds
- **AI-Powered Analysis**: Extract company info and event details using Clarifai
- **Message Generation**: Create personalized LinkedIn outreach messages
- **Docker Support**: Fully containerized for easy deployment
- **Automated Scheduling**: Daily execution via GitHub Actions
- **Multiple Output Formats**: JSON, CSV, or TXT
- **Slack Integration**: Automatic notifications with clickable article links
- **AI Priority Assessment**: High/Standard priority classification for prospects

## Quick Start (Local Development)

### 1. Prerequisites

- Python 3.12+
- Clarifai API token (get one at [clarifai.com](https://clarifai.com))

### 2. Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd pipelinegen/sales_lead-gen

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env
```

### 3. Configure

**a) Set up environment variables:**

Edit `.env` and add your Clarifai PAT token:
```env
CLARIFAI_PAT=your_token_here
LOCAL_DEV=true
```

**b) Add your company background info:**

```bash
# Copy template and edit with your company details
cp background_info.txt.example background_info.txt
# Edit background_info.txt with your company/product information
```

The AI will use this information to generate more relevant, personalized outreach messages.

**c) Customize RSS feeds (optional):**

Edit `config.yaml` to add more RSS feeds or adjust settings.

**d) Configure Slack notifications (optional):**

Add Slack credentials to `.env` for automatic notifications:
```env
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_CHANNEL=#your-channel-name
```

### 4. Run

```bash
python main.py
```

Check the `output/` directory for generated messages.

## Configuration

### config.yaml

```yaml
rss_feeds:
  - name: "Primary Google Alert"
    url: "https://www.google.com/alerts/feeds/YOUR_FEED_ID"
    type: "google_alerts"

clarifai:
  pat: ""  # Set via environment variable
  url: "https://clarifai.com/openai/chat-completion/models/gpt-oss-120b"
  background_info_file: "background_info.txt"  # Your company/product info

output:
  format: "json"  # Options: json, csv, txt
  filename: "generated_messages_{date}.json"
  include_metadata: true

search_limit: 10
message_limit: 20
```

### Background Info File

The `background_info.txt` file contains information about your company/product that the AI uses to generate relevant outreach messages.

**Why use it?**
- Enables the AI to make specific connections between news events and your solutions
- Generates more personalized, targeted messages
- You can include as much detail as needed (no character limits)

**What to include:**
- Company overview and mission
- Products/services and key features
- Target industries and use cases
- Performance metrics and benchmarks
- Customer success stories
- Unique selling points
- Technical capabilities

**Example:**
```
Our company provides AI-powered data analytics for healthcare.

Key Features:
- Real-time patient data processing
- HIPAA-compliant infrastructure
- 99.9% uptime SLA
- Integration with major EHR systems

Recent Results:
- Reduced analysis time by 80% for Hospital X
- Processing 10M+ records daily
- Recognized as Gartner Cool Vendor 2025
```

The more detailed and specific your background info, the better the AI can tailor messages to each prospect.

## Docker Usage

### Build and Run

```bash
# Build Docker image
docker build -t outreach-app .

# Run with environment file
docker run --env-file .env outreach-app

# Or with direct environment variable
docker run --env CLARIFAI_PAT=your_token outreach-app
```

## GitHub Actions Setup

### 1. Create Repository Secrets

Go to your GitHub repository → Settings → Secrets and add:
- `SALES_LEAD_GEN_CLARIFAI_PAT`: Your Clarifai API token
- `SALES_LEAD_GEN_SLACK_BOT_TOKEN`: Your Slack bot token (optional)
- `SALES_LEAD_GEN_SLACK_CHANNEL`: Your Slack channel name (optional)

### 2. Setup Self-Hosted Runner

Follow [GitHub's documentation](https://docs.github.com/en/actions/hosting-your-own-runners) to set up a self-hosted runner with Docker installed.

### 3. Workflow

The workflow (`.github/workflows/daily-outreach.yaml`) runs daily at midnight UTC and:
- Builds the Docker image
- Runs the outreach generation
- Uploads generated messages and logs as artifacts

You can also trigger it manually from the Actions tab.

## Project Structure

```
pipelinegen/
├── .github/
│   └── workflows/
│       └── daily-outreach.yaml # GitHub Actions workflow
└── sales_lead-gen/            # Main project directory
    ├── src/
    │   ├── __init__.py
    │   ├── news_scraper.py         # RSS feed fetching
    │   ├── article_processor.py    # Clarifai integration
    │   ├── slack_notifier.py       # Slack notifications
    │   └── message_handler.py      # Output formatting
    ├── output/                     # Generated messages
    ├── logs/                       # Application logs
    ├── main.py                     # Entry point
    ├── config.yaml                 # Configuration
    ├── requirements.txt            # Python dependencies
    ├── Dockerfile                  # Docker configuration
    ├── .env.example               # Environment template
    └── README.md                  # This file
```

## Output Format

### JSON Example

```json
{
  "metadata": {
    "generated_at": "2025-10-06T12:00:00",
    "total_messages": 5
  },
  "messages": [
    {
      "company_name": "TechCorp",
      "event_type": "funding",
      "event_details": "Raised $50M Series B",
      "linkedin_message": "Congratulations on your Series B...",
      "article_url": "https://...",
      "article_title": "TechCorp Raises $50M...",
      "published": "2025-10-06T10:00:00",
      "source": "TechCrunch"
    }
  ]
}
```

## Development Workflow

1. **Start Small**: Begin with `search_limit: 5` in config.yaml
2. **Test RSS Parsing**: Run main.py and verify articles are fetched
3. **Add Clarifai Token**: Test message generation
4. **Refine Prompts**: Adjust prompts in `article_processor.py` if needed
5. **Scale Up**: Increase limits as needed

## Troubleshooting

### No articles found
- Check your RSS feed URL is accessible
- Verify articles are from the last 24 hours
- Try increasing `search_limit` in config.yaml

### Clarifai errors
- Verify your PAT token is valid and not expired
- Check you haven't exceeded API rate limits
- Ensure internet connectivity

### Docker issues
- Make sure Docker is installed and running
- Check file permissions for mounted volumes
- Review logs with: `docker logs <container_id>`

## Monitoring & Maintenance

- **Logs**: Check `logs/` directory for execution logs
- **Artifacts**: GitHub Actions uploads messages and logs as artifacts
- **Free Tier**: Monitor Clarifai usage to stay within limits

## Adding More RSS Feeds

Edit `config.yaml` and add feeds:

```yaml
rss_feeds:
  - name: "TechCrunch AI"
    url: "https://techcrunch.com/category/artificial-intelligence/feed/"
    type: "custom_rss"
  - name: "VentureBeat"
    url: "https://venturebeat.com/feed/"
    type: "custom_rss"
```

## License

Private use only.

## Support

For issues or questions, refer to the Plan.md document for detailed specifications.
