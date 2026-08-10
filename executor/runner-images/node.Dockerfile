FROM node:20-slim
RUN mkdir -p /app/project /app/.codesentinel && chown -R 1000:1000 /app
WORKDIR /app/project