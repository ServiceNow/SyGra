#!/bin/bash

# Default port is 8501, override with: ./run_ui.sh 8502
PORT=${1:-8501}

# Run the Streamlit app
streamlit run apps/grasp_app.py --server.port=$PORT
