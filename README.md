# YouTube MP3 Worker

A small authenticated HTTP service intended to run separately from the Telegram bot.

## Deploy on Railway

1. Create a Railway project from this repository.
2. In the service's **Variables** settings, add `API_TOKEN` with a long random secret. Keep it private.
3. Railway should detect the Dockerfile and build the service.
4. In service settings, generate a public domain.
5. Test `https://YOUR-DOMAIN/health`; it should return `{"ok":true,"service":"youtube-mp3-worker"}`.

## API

`POST /convert`

Headers:
- `Authorization: Bearer YOUR_API_TOKEN`
- `Content-Type: application/json`

Body:
```json
{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}
```

Success returns an MP3 file as `audio/mpeg`. Errors return a JSON detail message.

Configuration:
- `API_TOKEN` (required; service returns 503 if missing)
- `MAX_DURATION_SECONDS` (default 900 seconds)
- `MAX_FILE_SIZE_BYTES` (default 52428800 bytes)

Only YouTube URLs are accepted. Use this service only for content you own or are authorized to download, and comply with applicable law and platform terms. Conversion is limited to 15 minutes and approximately 50 MB by default. The hosting provider may impose its own CPU, memory, and usage limits.
