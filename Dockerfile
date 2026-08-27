FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the SQLite DB once at image build time (network required).
# Downloads latest SEC 13F raw filings for the governed manager universe,
# then normalizes + analyzes into data/thirteenf.db (preserved in the image).
RUN python scripts/update_data.py --rate-limit 0.6

EXPOSE 8501
CMD ["sh", "-c", "python -m streamlit run app/app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true"]

