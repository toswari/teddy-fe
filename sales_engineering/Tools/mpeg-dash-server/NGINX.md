# NGINX Configuration Guide

Complete guide for setting up and managing nginx as a reverse proxy for the MP4 Streaming Service on macOS (Homebrew) and WSL2 Ubuntu.

## Table of Contents
- [Installation](#installation)
- [Configuration Structure](#configuration-structure)
- [SSL/TLS Setup](#ssltls-setup)
- [HTTP Basic Authentication](#http-basic-authentication)
- [Location Blocks Reference](#location-blocks-reference)
- [Management Commands](#management-commands)
- [Troubleshooting](#troubleshooting)
- [Platform Differences](#platform-differences)

---

## Installation

### macOS (Homebrew)

```bash
# Install nginx
brew install nginx

# Check installation
nginx -v

# Find nginx directories
brew --prefix nginx
# Typical: /opt/homebrew/opt/nginx

# Config location
ls /opt/homebrew/etc/nginx/
# servers/ or conf.d/ directory for custom configs
```

**Default Paths (macOS/Homebrew):**
- Main config: `/opt/homebrew/etc/nginx/nginx.conf`
- Server configs: `/opt/homebrew/etc/nginx/servers/` or `/opt/homebrew/etc/nginx/conf.d/`
- Logs: `/opt/homebrew/var/log/nginx/`
- Binary: `/opt/homebrew/bin/nginx`

### WSL2 Ubuntu

```bash
# Update package index
sudo apt-get update

# Install nginx
sudo apt-get install -y nginx

# Check installation
nginx -v

# Check status
sudo systemctl status nginx
```

**Default Paths (Ubuntu):**
- Main config: `/etc/nginx/nginx.conf`
- Server configs: `/etc/nginx/sites-available/` (with symlinks in `/etc/nginx/sites-enabled/`)
- Logs: `/var/log/nginx/`
- Binary: `/usr/sbin/nginx`

---

## Configuration Structure

### Main Configuration File

The main `nginx.conf` typically includes custom server blocks from subdirectories:

```nginx
# macOS
include /opt/homebrew/etc/nginx/servers/*;

# Ubuntu
include /etc/nginx/sites-enabled/*;
```

### Server Block Template

Our application uses a single server block listening on HTTPS (port 5443 by default):

```nginx
server {
    listen 5443 ssl;
    server_name your-domain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    client_max_body_size 2g;

    # Optional: Enable basic auth for entire server
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd-mpeg-dash;

    # Location blocks for routing...
}
```

---

## SSL/TLS Setup

### Using Let's Encrypt (Certbot)

#### Installation

**macOS:**
```bash
brew install certbot
```

**Ubuntu:**
```bash
sudo apt-get install -y certbot
```

#### Certificate Issuance

Use the included `letsenscript.sh` helper or run certbot directly:

```bash
# Using the helper (recommended)
./letsenscript.sh your-domain.com your-email@example.com

# Manual certbot (standalone mode, nginx must be stopped)
sudo certbot certonly --standalone \
  --http-01-port 80 \
  -d your-domain.com \
  --email your-email@example.com \
  --agree-tos --non-interactive
```

**Requirements:**
- Port 80 must be open and accessible from the internet
- DNS A record pointing to your server's public IP
- Stop nginx temporarily if port 80 is in use: `sudo nginx -s stop`

#### Certificate Renewal

Certificates expire after 90 days. Renew manually:

```bash
sudo certbot renew --cert-name your-domain.com --standalone --force-renewal
```

Or automate via cron:

```bash
# Add to crontab (run at 3 AM daily, renews only if needed)
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet --deploy-hook 'sudo nginx -s reload'") | crontab -
```

**Ubuntu with systemd:**
```bash
# Enable certbot timer (automatic renewal)
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## HTTP Basic Authentication

### Creating Password Files

Use `htpasswd` (from Apache utils):

**macOS:**
```bash
# Install if needed
brew install httpd

# Create password file (first user, use -c flag)
sudo htpasswd -c /etc/nginx/.htpasswd-mpeg-dash username

# Add additional users (omit -c)
sudo htpasswd /etc/nginx/.htpasswd-mpeg-dash another_user
```

**Ubuntu:**
```bash
# Install apache2-utils
sudo apt-get install -y apache2-utils

# Create password file
sudo htpasswd -c /etc/nginx/.htpasswd-mpeg-dash username
```

### Configuring Basic Auth

**Server-level (all locations protected):**
```nginx
server {
    # ... ssl config ...
    
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd-mpeg-dash;
    
    # All locations inherit auth requirement
    location / { ... }
}
```

**Selective protection (exempt specific locations):**
```nginx
server {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd-mpeg-dash;

    # Public endpoints - no auth required
    location /dash/ {
        auth_basic off;  # Disable auth for DASH content
        # ... rest of config ...
    }

    location /api/media {
        auth_basic off;  # Allow anonymous API access
        # ... rest of config ...
    }

    # Protected endpoints inherit server-level auth
    location / {
        # Requires authentication
        proxy_pass http://127.0.0.1:8501/;
    }
}
```

### Logout Endpoint

HTTP Basic Auth doesn't have a true logout. This workaround forces the browser to clear credentials:

```nginx
location /logout {
    auth_basic "Logged out - close browser to complete";
    auth_basic_user_file /etc/nginx/.htpasswd-invalid;  # Non-existent file
    return 401;
}
```

---

## Location Blocks Reference

### Static DASH Content

Serves DASH manifests and segments directly from filesystem:

```nginx
location /dash/ {
    auth_basic off;  # Public access for playback
    alias /path/to/media/dash/;
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods 'GET, HEAD, OPTIONS';
    add_header Access-Control-Allow-Headers '*';
    expires 1m;  # Cache for 1 minute
}
```

### Backend API Proxy

Forwards API requests to FastAPI backend:

```nginx
# Specific endpoint exemption
location /api/media {
    auth_basic off;
    proxy_pass http://127.0.0.1:8000/api/media;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}

# General API proxy (protected)
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}
```

### Video Streaming Endpoint

Proxies to FastAPI with buffering disabled for efficient streaming:

```nginx
location /video {
    proxy_pass http://127.0.0.1:8000/video;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_request_buffering off;  # Important for Range requests
}
```

### Streamlit UI (WebSocket Support)

Proxies to Streamlit with WebSocket upgrade headers:

```nginx
location / {
    proxy_pass http://127.0.0.1:8501/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 86400;  # 24 hours for long-lived connections
}
```

---

## Management Commands

### Configuration Testing

Always test before reloading:

```bash
sudo nginx -t
```

Output on success:
```
nginx: the configuration file /path/to/nginx.conf syntax is ok
nginx: configuration file /path/to/nginx.conf test is successful
```

### View Active Configuration

See the complete merged config nginx is actually using:

```bash
sudo nginx -T
```

This resolves all `include` directives and shows the final configuration.

### Starting/Stopping/Reloading

**macOS (Homebrew):**
```bash
# Start
brew services start nginx
# or: sudo nginx

# Stop
brew services stop nginx
# or: sudo nginx -s stop

# Reload (graceful, no downtime)
sudo nginx -s reload

# Check status
brew services list | grep nginx
```

**Ubuntu (systemd):**
```bash
# Start
sudo systemctl start nginx

# Stop
sudo systemctl stop nginx

# Restart (brief downtime)
sudo systemctl restart nginx

# Reload (graceful, no downtime)
sudo systemctl reload nginx
# or: sudo nginx -s reload

# Enable on boot
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

### Using the Helper Script

This repo includes `update-nginx-config.sh`:

```bash
./update-nginx-config.sh
```

It will:
1. Copy `nginx-config-reference.conf` to the active location
2. Test the configuration
3. Reload nginx

---

## Troubleshooting

### Check Logs

**macOS:**
```bash
# Error log
tail -f /opt/homebrew/var/log/nginx/error.log

# Access log
tail -f /opt/homebrew/var/log/nginx/access.log
```

**Ubuntu:**
```bash
# Error log
sudo tail -f /var/log/nginx/error.log

# Access log
sudo tail -f /var/log/nginx/access.log
```

### Common Issues

#### Port Already in Use

```bash
# Find what's using a port
sudo lsof -i :5443
# or on Linux:
sudo netstat -tlnp | grep 5443
```

Kill the process or change nginx's listen port.

#### Permission Denied

nginx typically needs sudo/root to bind to privileged ports (<1024) and read SSL certificates.

**Solution:**
- Use sudo for nginx commands
- Ensure certificate files have correct permissions:
  ```bash
  sudo chmod 644 /etc/letsencrypt/live/your-domain/fullchain.pem
  sudo chmod 600 /etc/letsencrypt/live/your-domain/privkey.pem
  ```

#### 502 Bad Gateway

Backend service (FastAPI/Streamlit) is not running or unreachable.

**Check:**
```bash
# Is FastAPI running on port 8000?
curl http://localhost:8000/healthz

# Is Streamlit running on port 8501?
curl http://localhost:8501
```

Start the backend services if needed:
```bash
./start-servers.sh
```

#### Authentication Not Working

**Symptoms:** No password prompt, or always returns 200 without credentials.

**Debug:**
1. Check if `auth_basic` directives are in the loaded config:
   ```bash
   sudo nginx -T | grep auth_basic
   ```

2. Verify htpasswd file exists and is readable:
   ```bash
   sudo cat /etc/nginx/.htpasswd-mpeg-dash
   ```

3. Test with curl:
   ```bash
   # Should return 401
   curl -vk https://your-domain:5443/
   
   # Should return 200
   curl -vk -u username:password https://your-domain:5443/
   ```

4. Check that auth is not disabled in a more-specific location block

#### Config File Not Loading

nginx may be looking in the wrong directory.

**macOS:** Check if nginx uses `servers/` or `conf.d/`:
```bash
cat $(brew --prefix)/etc/nginx/nginx.conf | grep include
```

**Ubuntu:** Ensure symlink exists:
```bash
ls -la /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/mpeg_dash.conf /etc/nginx/sites-enabled/
```

---

## Platform Differences

### File Paths

| Item | macOS (Homebrew) | Ubuntu |
|------|------------------|--------|
| Main config | `/opt/homebrew/etc/nginx/nginx.conf` | `/etc/nginx/nginx.conf` |
| Server blocks | `/opt/homebrew/etc/nginx/servers/` or `conf.d/` | `/etc/nginx/sites-available/` + `sites-enabled/` |
| Logs | `/opt/homebrew/var/log/nginx/` | `/var/log/nginx/` |
| Binary | `/opt/homebrew/bin/nginx` | `/usr/sbin/nginx` |

### Service Management

| Task | macOS | Ubuntu |
|------|-------|--------|
| Start | `brew services start nginx` | `sudo systemctl start nginx` |
| Stop | `brew services stop nginx` | `sudo systemctl stop nginx` |
| Reload | `sudo nginx -s reload` | `sudo systemctl reload nginx` |
| Status | `brew services list \| grep nginx` | `sudo systemctl status nginx` |
| Enable on boot | Automatic with brew services | `sudo systemctl enable nginx` |

### User/Permissions

- **macOS:** nginx runs as the user who started it (typically your user account via `brew services`)
- **Ubuntu:** nginx runs as user `www-data` by default (defined in `nginx.conf`)

This affects file permissions - ensure nginx can read static files and SSL certificates.

---

## Quick Reference

### Update Configuration Workflow

```bash
# 1. Edit nginx-config-reference.conf
vim nginx-config-reference.conf

# 2. Apply changes
./update-nginx-config.sh

# 3. Verify
curl -vk https://your-domain:5443/healthz
```

### Create New User

```bash
sudo htpasswd /etc/nginx/.htpasswd-mpeg-dash newuser
./update-nginx-config.sh  # Reload to apply
```

### Check What's Running

```bash
# nginx
ps aux | grep nginx

# Backend
ps aux | grep uvicorn

# UI
ps aux | grep streamlit

# All listening ports
sudo lsof -iTCP -sTCP:LISTEN -P
```

---

## Security Best Practices

1. **Always use HTTPS in production** - Never expose passwords over HTTP
2. **Keep certificates up to date** - Set up automatic renewal
3. **Use strong passwords** - `htpasswd` uses bcrypt by default (good)
4. **Restrict sensitive endpoints** - Keep `/api/dash/package` auth-protected if needed
5. **Rate limiting** - Add nginx rate limiting for public endpoints:
   ```nginx
   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
   
   location /api/ {
       limit_req zone=api burst=20 nodelay;
       # ... rest of config
   }
   ```
6. **Monitor logs** - Watch for suspicious activity in access/error logs
7. **Firewall** - Only expose necessary ports (443 or custom HTTPS port, and 80 for cert renewal)

---

## Additional Resources

- [nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot User Guide](https://eff-certbot.readthedocs.io/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)

For this project specifically:
- See `nginx-config-reference.conf` for the complete working configuration
- See `setup-env.sh` for automated nginx setup
- See `agent-lesson-learn.md` for troubleshooting notes from development
