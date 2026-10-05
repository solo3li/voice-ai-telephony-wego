@echo off
echo ========================================================
echo Starting Voice AI Stack (Django + LiveKit + Pipecat + Centrifugo + Traefik)
echo ========================================================

REM Check if certs exist
if not exist "traefik\certs\local.crt" (
    echo Generating SSL certificates...
    python generate_certs.py
)

echo Starting Docker containers...
docker compose up -d --build

echo ========================================================
echo Stack is running!
echo Access the Voice Assistant at: https://app.localhost
echo LiveKit SFU at:               https://livekit.localhost
echo Centrifugo at:                https://centrifugo.localhost
echo ========================================================
