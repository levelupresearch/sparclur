#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
python -m streamlit run "$project_dir/sparclur/lit_sparclur/lit_sparclur.py"
