#!/usr/bin/env bash
set -e
echo "Installation des dépendances..."
python -m pip install -r requirements.txt

echo "Lancement de l'interface de démonstration (Streamlit)..."
python -m streamlit run ui/streamlit_app.py
