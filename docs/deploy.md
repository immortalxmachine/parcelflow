# Deploying ParcelFlow (free tiers)

> The README does **not** claim a live deployment. Deploy it yourself with the
> steps below, then paste the live URL into the README.

## Option A — Streamlit Community Cloud (easiest, free)

The dashboard reads the warehouse via `DATABASE_URL`. For a public demo the
simplest path is to ship a prebuilt SQLite warehouse with the repo (or generate
on first run) and point Streamlit at it.

1. Push the repo to GitHub (see the main README).
2. Go to <https://share.streamlit.io>, sign in with GitHub.
3. New app → pick this repo → main file `dashboard/app.py`.
4. Under *Advanced settings → Secrets*, set any env vars (for a SQLite demo you
   can leave defaults; for Postgres set `DATABASE_URL`).
5. Deploy. Copy the `*.streamlit.app` URL into the README badge/line.

Note: Community Cloud containers are ephemeral; for a persistent warehouse use a
hosted Postgres (e.g. Neon/Supabase free tier) and set `DATABASE_URL`.

## Option B — Azure (App Service + Blob + Postgres), student credit

Everything here fits **Azure for Students** free credit (~₹0 expected). Do not
create any paid-tier resource.

1. `az login` (install the Azure CLI first).
2. Create a resource group:
   `az group create -n parcelflow-rg -l centralindia`
3. **Blob Storage** (replaces Azurite):
   `az storage account create -n parcelflowsa -g parcelflow-rg --sku Standard_LRS`
   then copy the connection string into the app's `AZURE_STORAGE_CONNECTION_STRING`.
4. **Postgres Flexible Server (Burstable B1ms, free-eligible)**:
   `az postgres flexible-server create -g parcelflow-rg -n parcelflow-pg ...`
   and set `DATABASE_URL=postgresql+psycopg://USER:PASS@parcelflow-pg...:5432/parcelflow`.
5. Run the pipeline once to populate the warehouse (locally pointing at the
   cloud `DATABASE_URL`, or as an Azure Container Instance using this repo's
   image): `python pipeline.py initdb && python pipeline.py backfill --years 2`.
6. **App Service** (Linux, free F1) from the Docker image, with the env vars
   above. Browse to the app URL.

## Cost

Local (SQLite + Azurite via Docker) is **₹0**. The Azure path above uses only
free-tier / student-credit resources; verify in the Azure portal before
creating anything, and delete the resource group when done:
`az group delete -n parcelflow-rg`.
