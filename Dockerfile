FROM ghcr.io/astral-sh/uv:python3.10-alpine AS builder

WORKDIR /TwitchDropsMiner

RUN apk add --no-cache build-base libffi-dev

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group nicegui --no-install-project

COPY . .

FROM python:3.10-alpine

ARG TDM_VERSION_TAG=16.dev

LABEL org.opencontainers.image.title="Twitch Drops Miner" \
      org.opencontainers.image.description="Twitch Drops Miner with a NiceGUI web interface and integrated notifications" \
      org.opencontainers.image.source="https://github.com/NorskNoobing/TwitchDropsMiner" \
      org.opencontainers.image.licenses="MIT"

ENV GROUP_ID=1000 \
    PATH="/TwitchDropsMiner/.venv/bin:${PATH}" \
    TDM_CONTAINER=1 \
    TDM_VERSION_TAG="${TDM_VERSION_TAG}" \
    TZ=UTC \
    UI_BACKEND=nicegui \
    USER_ID=1000 \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=5800

RUN apk add --no-cache ca-certificates curl su-exec tzdata

WORKDIR /TwitchDropsMiner
COPY --from=builder /TwitchDropsMiner /TwitchDropsMiner
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

EXPOSE 5800

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c 'protocol=http; [ "${SECURE_CONNECTION:-0}" = "1" ] && protocol=https; curl -kfs --max-time 10 -o /dev/null "${protocol}://127.0.0.1:${WEBUI_PORT:-5800}/health"'

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main_webui.py", "--stdlog"]
