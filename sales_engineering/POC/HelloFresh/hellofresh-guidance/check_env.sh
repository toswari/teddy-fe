#!/bin/bash
# Quick environment status check for AI Brand Compliance Specialist

ENV_NAME="brand-logo-312"
CONDA_PATH="/home/toswari/anaconda3/bin/conda"

echo "🐍 AI Brand Compliance Specialist - Environment Status"
echo "======================================================"

# Check current environment
if [ "$CONDA_DEFAULT_ENV" = "$ENV_NAME" ]; then
    echo "✅ Currently in correct conda environment: $ENV_NAME"
else
    echo "⚠️  Current environment: ${CONDA_DEFAULT_ENV:-base}"
    echo "📝 To activate: conda activate $ENV_NAME"
fi

# Check if environment exists
if $CONDA_PATH env list | grep -q "$ENV_NAME" 2>/dev/null; then
    echo "✅ Environment '$ENV_NAME' exists"
else
    echo "❌ Environment '$ENV_NAME' not found"
    echo "📦 Create with: conda create -n $ENV_NAME python=3.12"
fi

# Check key dependencies
echo ""
echo "🔍 Checking key dependencies..."
if [ "$CONDA_DEFAULT_ENV" = "$ENV_NAME" ]; then
    # We're in the right environment, check directly
    python -c "import streamlit; print('✅ streamlit')" 2>/dev/null || echo "❌ streamlit"
    python -c "import clarifai; print('✅ clarifai')" 2>/dev/null || echo "❌ clarifai"
    python -c "import pandas; print('✅ pandas')" 2>/dev/null || echo "❌ pandas"
else
    # Use conda run to check
    $CONDA_PATH run -n $ENV_NAME python -c "import streamlit; print('✅ streamlit')" 2>/dev/null || echo "❌ streamlit"
    $CONDA_PATH run -n $ENV_NAME python -c "import clarifai; print('✅ clarifai')" 2>/dev/null || echo "❌ clarifai"
    $CONDA_PATH run -n $ENV_NAME python -c "import pandas; print('✅ pandas')" 2>/dev/null || echo "❌ pandas"
fi

echo ""
echo "🚀 Quick commands:"
echo "   conda activate $ENV_NAME    # Activate environment"
echo "   ./conda_run.sh app          # Start application"
echo "   ./conda_run.sh test         # Run tests"
echo "   ./start.sh                  # Start with script"
