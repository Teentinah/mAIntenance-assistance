Write-Host "Installation des dépendances..."
python -m pip install -r requirements.txt

Write-Host "Lancement de l'interface de démonstration (Streamlit)..."
python -m streamlit run ui/streamlit_app.py
