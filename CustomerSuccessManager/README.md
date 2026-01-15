# Enterprise Account Manager

A comprehensive web-based dashboard for Customer Success teams to monitor and manage enterprise customer accounts, track engineering efforts, document links, Slack channels, and generate professional reports.

## Features

### Dashboard
- **Real-time Statistics** - Six clickable stat cards showing:
  - Total Accounts
  - Active Contracts
  - Expiring in 60 Days
  - Active Engineering
  - Needs Review
  - Expired/Closed
- **Contracts Expiring Soon** - Quick view of upcoming contract expirations
- **Accounts by Rep** - Clickable breakdown by sales representative

### Account Management
- **Full CRUD Operations** - Create, read, update, and delete accounts
- **Link Management** - Track multiple link types per account:
  - Contract documents
  - Billing information
  - Slack channels (internal & external)
  - Google Drive folders
  - Field Engineering docs
  - Sales documents
  - Clarifai organization links
  - Jira project links
  - Additional custom documents
- **Status History** - Track dated status updates with full history
- **Engineering Status** - Toggle active engineering work with visual badges
- **Customer Sentiment** - Track sentiment with color-coded indicators (positive/neutral/negative)
- **Review Flags** - Flag accounts that need accuracy review
- **CSE Notes** - Free-form notes field for Customer Success Engineers

### Views
- **Dashboard** - Overview with stats and quick access
- **All Accounts** - Searchable, filterable grid of all accounts
- **Expiring Soon** - Accounts with contracts expiring within 60 days
- **Active Engineering** - Accounts with ongoing engineering work
- **Needs Review** - Accounts flagged for review

### Reports & Export
- **Professional Reports** - Generate print-ready HTML/MD reports with:
  - Cover page with generation date
  - Executive summary statistics
  - Detailed account information
  - Status history with dates
  - All links and documentation
- **JSON Export** - Download all account data as JSON
- **Database Backup** - Full database backup with timestamped filename
- **Database Restore** - Restore from backup file
- **Database Clear** - Clear all data (with confirmation)

---

## Quick Start with Docker

### Prerequisites
- Docker
- Docker Compose

### Run the Application

```bash
# Clone or navigate to the project directory
cd customersuccess_agent

# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The application will be available at: **http://localhost:3000**

### Rebuild After Changes

If you modify the source code, rebuild the container:

```bash
docker-compose up -d --build
```

### Data Persistence

The SQLite database is stored in a Docker volume (`account-data`). Your data persists across container restarts.

---

## Database Management

### In-App Backup & Restore

Click the **database icon** in the header to access:

1. **Export Backup** - Downloads a complete JSON backup file:
   - Filename format: `account-manager-backup-YYYY-MM-DDTHH-MM-SS.json`
   - Includes all accounts, links, and status history

2. **Restore from Backup** - Upload a previously exported backup:
   - Shows confirmation with counts before restoring
   - Replaces all existing data

3. **Clear Database** - Remove all data:
   - Requires typing "DELETE ALL" to confirm
   - Cannot be undone

### Manual Database Backup

```bash
# Create a backup of the SQLite database file
docker cp enterprise-account-manager:/app/data/accounts.db ./backup-accounts.db

# Restore from backup
docker cp ./backup-accounts.db enterprise-account-manager:/app/data/accounts.db
docker-compose restart
```

---

## Local Development

### Prerequisites
- Node.js 18+ (20 recommended)
- npm

### Setup

```bash
# Install dependencies
npm install

# Start the development server
npm start
```

The application will be available at: **http://localhost:3000**

### Initialize with Sample Data (Optional)

```bash
npm run init-db
```

---

## Project Structure

```
├── Dockerfile              # Multi-stage Docker build configuration
├── docker-compose.yml      # Docker Compose with volume persistence
├── package.json            # Node.js dependencies and scripts
├── server.js               # Express.js backend (API routes, SQLite)
├── report-generator.js     # HTML report generation
├── init-db.js              # Database initialization with sample data
├── .dockerignore           # Docker build exclusions
├── README.md               # This file
├── public/                 # Frontend static files
│   ├── index.html          # Main HTML (dashboard, modals)
│   ├── styles.css          # Complete CSS styling
│   └── app.js              # Frontend JavaScript (AccountManager class)
└── data/                   # SQLite database (created at runtime)
    └── accounts.db
```

---

## API Reference

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts` | List all accounts with links |
| `GET` | `/api/accounts/:id` | Get single account with links |
| `POST` | `/api/accounts` | Create new account |
| `PUT` | `/api/accounts/:id` | Update account |
| `DELETE` | `/api/accounts/:id` | Delete account and related data |

### Engineering Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PATCH` | `/api/accounts/:id/engineering-status` | Toggle engineering status (active/none) |

### Status History

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts/:id/status-history` | Get status history for account |
| `POST` | `/api/accounts/:id/status-history` | Add new status update |
| `GET` | `/api/accounts/:id/latest-status` | Get most recent status |
| `DELETE` | `/api/status-history/:id` | Delete a status update |

### Statistics & Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Get dashboard statistics |
| `GET` | `/api/search?q=term` | Search accounts by name, rep, Salesforce ID |

### Export & Import

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/export` | Export all data as JSON |
| `POST` | `/api/import` | Import accounts from JSON |
| `GET` | `/api/report` | Generate HTML report (opens in new tab) |

### Database Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/backup` | Download complete database backup |
| `POST` | `/api/restore` | Restore from backup file |
| `DELETE` | `/api/database` | Clear all data from database |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check (returns `{ status: 'healthy' }`) |

---

## Account Data Structure

### Account Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Account/company name |
| `overview` | string | Brief description |
| `salesforceId` | string | Salesforce Account ID |
| `contractStart` | date | Contract start date |
| `contractEnd` | date | Contract end date |
| `isPOC` | boolean | Proof of Concept flag |
| `salesRep` | string | Assigned sales representative |
| `engineeringStatus` | string | `none` or `active` |
| `sentiment` | string | `positive`, `neutral`, or `negative` |
| `cseNotes` | string | Customer Success Engineer notes |
| `needsReview` | boolean | Flag for accounts needing review |
| `lastContactFE` | date | Last field engineering contact |
| `lastContactSales` | date | Last sales contact |

### Link Types

| Type | Description |
|------|-------------|
| `contract` | Contract document link |
| `billing` | Billing information |
| `slack` | Internal Slack channel |
| `slackExternal` | External/shared Slack channel |
| `gdrive` | Google Drive folder |
| `fieldEng` | Field Engineering documentation |
| `sales` | Sales documentation |
| `clarifaiOrg` | Clarifai organization link |
| `jira` | Jira project/board link |
| `additionalDocs` | Array of custom document links |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3000` | Server port |
| `DATA_DIR` | `./data` | Database directory path |
| `NODE_ENV` | `development` | Environment mode |

---

## Docker Configuration

### Building Manually

```bash
# Build the image
docker build -t enterprise-account-manager .

# Run the container
docker run -d \
  --name account-manager \
  -p 3000:3000 \
  -v account-data:/app/data \
  enterprise-account-manager
```

### Health Checks

The container includes health checks that verify the API is responding:
- Interval: 30 seconds
- Timeout: 3 seconds
- Retries: 3
- Start period: 10 seconds

---

## Usage Tips

### Importing Accounts in Bulk

Use the API to bulk import accounts:

```powershell
# PowerShell example
$account = @{
    name = "Company Name"
    salesforceId = "001XXXXXXXXX"
    contractStart = "2025-01-01"
    contractEnd = "2026-01-01"
    salesRep = "Rep Name"
    links = @{
        billing = "https://..."
        slack = "https://..."
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:3000/api/accounts" -Method POST -ContentType "application/json" -Body $account
```

### Filtering Accounts

- Click stat cards to filter by status
- Click rep names in the dashboard to filter by representative
- Use the search box for text search
- Use dropdown filters for status and rep

### Generating Reports

1. Click "Generate Report" button
2. Report opens in new tab
3. Use browser's Print function (Ctrl+P)
4. Save as PDF

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Restart with rebuild
docker-compose down
docker-compose up -d --build
```

### Database Issues

```bash
# Check if volume exists
docker volume ls | grep account

# Inspect volume
docker volume inspect customersuccess_agent_account-data
```

### Browser Caching

After code changes and rebuild, hard refresh your browser:
- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

---

## License

MIT
