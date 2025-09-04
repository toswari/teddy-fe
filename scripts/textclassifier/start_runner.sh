#!/bin/bash

# Load environment variables from .env file (skip comments)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found"
fi

# Check if CLARIFAI_PAT is set
if [ -z "$CLARIFAI_PAT" ]; then
    echo "Error: CLARIFAI_PAT environment variable is not set"
    exit 1
fi

# Check if CLARIFAI_USER_ID is set
if [ -z "$CLARIFAI_USER_ID" ]; then
    echo "Error: CLARIFAI_USER_ID environment variable is not set"
    exit 1
fi

echo "CLARIFAI_PAT: ${CLARIFAI_PAT:0:10}..."
echo "CLARIFAI_USER_ID: ${CLARIFAI_USER_ID}"

# Require all model deployment identifiers to come from environment (no implicit defaults)
REQUIRED_VARS=(CLARIFAI_APP_ID CLARIFAI_MODEL_ID CLARIFAI_MODEL_TYPE_ID CLARIFAI_DEPLOYMENT_ID CLARIFAI_COMPUTE_CLUSTER_ID CLARIFAI_NODEPOOL_ID)
MISSING=()
for v in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!v}" ]; then
        MISSING+=("$v")
    fi
done
if [ ${#MISSING[@]} -ne 0 ]; then
    echo "Error: Missing required environment variables: ${MISSING[*]}" >&2
    echo "Please set them in your .env file. See .env.example for reference." >&2
    exit 1
fi

echo "Deployment IDs: app=${CLARIFAI_APP_ID} model=${CLARIFAI_MODEL_ID} deployment=${CLARIFAI_DEPLOYMENT_ID}" 

# If user id not provided via env, attempt to read from repo config.yaml (model.user_id)
if [ -z "$CLARIFAI_USER_ID" ] && [ -f config.yaml ]; then
    CONFIG_USER_ID=$(grep -E '^\s*user_id:' config.yaml | head -1 | sed 's/.*user_id:[[:space:]]*"\?//; s/"\?$//')
    if [ -n "$CONFIG_USER_ID" ]; then
        export CLARIFAI_USER_ID="$CONFIG_USER_ID"
        echo "CLARIFAI_USER_ID (from config.yaml): ${CLARIFAI_USER_ID}"
    fi
fi

# Set up non-interactive authentication for the container environment
echo "Setting up Clarifai authentication for containerized environment..."

# Create the config directory if it doesn't exist
mkdir -p ~/.clarifai

# Ensure contexts auth file exists / is updated without clobbering blindly
CONTEXT_FILE="$HOME/.clarifai/config.yaml"
if [ -f "$CONTEXT_FILE" ]; then
    echo "Found existing Clarifai auth context at $CONTEXT_FILE"
    # Update PAT or user_id if changed
    if ! grep -q "$CLARIFAI_PAT" "$CONTEXT_FILE" || ! grep -q "user_id: ${CLARIFAI_USER_ID}" "$CONTEXT_FILE"; then
        cp "$CONTEXT_FILE" "${CONTEXT_FILE}.bak" 2>/dev/null || true
        awk -v pat="$CLARIFAI_PAT" -v uid="$CLARIFAI_USER_ID" ' \
            /^contexts:/ {print; next} \
            /^  default:/ {print; next} \
            /api_url:/ {print; next} \
            /pat:/ {next} \
            /user_id:/ {next} \
            /current_context:/ {next} \
            {print} \
            END { \
              print "contexts:"; \
              print "  default:"; \
              print "    api_url: https://api.clarifai.com"; \
              print "    pat: " pat; \
              print "    user_id: " uid; \
              print "current_context: default"; \
            }' "$CONTEXT_FILE" > "${CONTEXT_FILE}.tmp" && mv "${CONTEXT_FILE}.tmp" "$CONTEXT_FILE"
        echo "Updated existing context file with current PAT/user." 
    fi
else
    cat > "$CONTEXT_FILE" << EOF
contexts:
  default:
    api_url: https://api.clarifai.com
    pat: ${CLARIFAI_PAT}
    user_id: ${CLARIFAI_USER_ID}
current_context: default
EOF
    echo "Authentication context file created at $CONTEXT_FILE"
fi

# Sync repo config.yaml model section with env (hard override) for transparency
if [ -f config.yaml ]; then
    sed -i \
        -e "s/^  id:.*/  id: \"$CLARIFAI_MODEL_ID\"/" \
        -e "s/^  user_id:.*/  user_id: \"$CLARIFAI_USER_ID\"/" \
        -e "s/^  app_id:.*/  app_id: \"$CLARIFAI_APP_ID\"/" \
        -e "s/^  model_type_id:.*/  model_type_id: \"$CLARIFAI_MODEL_TYPE_ID\"/" config.yaml 2>/dev/null || true
fi

# Start the local runner with automatic yes response to all prompts
echo "Starting Clarifai local runner (using repository config.yaml for model metadata)..."
echo "This may create any missing compute resources automatically."
# Export resolved IDs so the clarifai CLI can pick them up (if it honors env vars)
export CLARIFAI_APP_ID CLARIFAI_MODEL_ID CLARIFAI_MODEL_TYPE_ID CLARIFAI_DEPLOYMENT_ID CLARIFAI_COMPUTE_CLUSTER_ID CLARIFAI_NODEPOOL_ID

# Run local runner; the CLI will still prompt for compute/nodepool/model if it cannot resolve.
yes | clarifai model local-runner .