#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting nginx...${NC}"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo -e "${RED}Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

# Function to run privileged commands
run_privileged() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Test nginx configuration first
echo "Testing nginx configuration..."
if run_privileged nginx -t; then
    echo -e "${GREEN}✓ Configuration valid${NC}"
else
    echo -e "${RED}✗ Configuration test failed${NC}"
    exit 1
fi

# Check if nginx is already running
if pgrep -x nginx > /dev/null; then
    echo -e "${YELLOW}nginx is already running, reloading...${NC}"
    RELOAD=true
else
    echo "nginx is not running, starting..."
    RELOAD=false
fi

# Start or reload nginx based on OS
if [[ "$OS" == "macos" ]]; then
    # macOS with homebrew
    if command -v brew &> /dev/null; then
        if $RELOAD; then
            # Prefer an in-place reload over a full restart
            if run_privileged nginx -s reload; then
                echo -e "${GREEN}✓ nginx reloaded${NC}"
            else
                echo -e "${YELLOW}Direct reload failed, trying brew services restart...${NC}"
                brew services restart nginx && echo -e "${GREEN}✓ nginx reloaded via brew services${NC}"
            fi
        else
            if brew services start nginx; then
                echo -e "${GREEN}✓ nginx started via brew services${NC}"
            else
                echo -e "${YELLOW}brew services failed, trying direct start...${NC}"
                run_privileged nginx && echo -e "${GREEN}✓ nginx started${NC}"
            fi
        fi
    else
        # Direct nginx command on macOS without brew
        if $RELOAD; then
            run_privileged nginx -s reload && echo -e "${GREEN}✓ nginx reloaded${NC}"
        else
            run_privileged nginx && echo -e "${GREEN}✓ nginx started${NC}"
        fi
    fi
elif [[ "$OS" == "linux" ]]; then
    # Linux (including WSL2 Ubuntu)
    if command -v systemctl &> /dev/null; then
        # systemd-based
        if $RELOAD; then
            run_privileged systemctl reload nginx && echo -e "${GREEN}✓ nginx reloaded via systemctl${NC}"
        else
            run_privileged systemctl start nginx && echo -e "${GREEN}✓ nginx started via systemctl${NC}"
        fi
        run_privileged systemctl enable nginx &> /dev/null || true
    elif command -v service &> /dev/null; then
        # SysV init
        if $RELOAD; then
            run_privileged service nginx reload && echo -e "${GREEN}✓ nginx reloaded via service${NC}"
        else
            run_privileged service nginx start && echo -e "${GREEN}✓ nginx started via service${NC}"
        fi
    else
        # Direct nginx command
        if $RELOAD; then
            run_privileged nginx -s reload && echo -e "${GREEN}✓ nginx reloaded${NC}"
        else
            run_privileged nginx && echo -e "${GREEN}✓ nginx started${NC}"
        fi
    fi
fi

# Verify nginx is running
sleep 2
NGINX_RUNNING=false
for i in {1..5}; do
    if pgrep -x nginx > /dev/null || pgrep nginx > /dev/null; then
        NGINX_RUNNING=true
        break
    fi
    sleep 1
done

if $NGINX_RUNNING; then
    echo -e "${GREEN}✓ nginx is running${NC}"
    
    # Show listening ports
    echo -e "\n${GREEN}Listening ports:${NC}"
    if [[ "$OS" == "macos" ]]; then
        run_privileged lsof -nP -iTCP -sTCP:LISTEN | grep nginx || echo "Could not determine ports"
    else
        run_privileged netstat -tlnp 2>/dev/null | grep nginx || run_privileged ss -tlnp | grep nginx || echo "Could not determine ports"
    fi
else
    echo -e "${RED}✗ nginx failed to start${NC}"
    echo "Check logs for errors:"
    if [[ "$OS" == "macos" ]]; then
        echo "  tail -f /opt/homebrew/var/log/nginx/error.log"
    else
        echo "  tail -f /var/log/nginx/error.log"
    fi
    exit 1
fi
