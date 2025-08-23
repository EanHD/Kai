# Kai Server Quickstart

## Option A: Python venv
sudo apt-get update && sudo apt-get install -y python3-venv git
git clone https://github.com/EanHD/Kai.git
cd Kai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit keys
bash scripts/run_prod.sh
# smoke test (from the same host)
bash scripts/smoke.sh

## Option B: Docker
git clone https://github.com/EanHD/Kai.git
cd Kai
cp .env.example .env  # then edit keys
docker compose up --build -d
curl http://localhost:8000/health

Notes:
- ENABLE_MEMORY_INJECT=true by default; tune MEMORY_TOKENS if needed.
- MEMORY_BACKEND=sqlite works out of the box (kai_memory.db on disk).
