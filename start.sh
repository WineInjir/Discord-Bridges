python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
for ((i=0; i<COLUMNS; i++)); do printf '-'; done; echo
python main.py
exit