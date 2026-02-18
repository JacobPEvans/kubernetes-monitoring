FROM node:22-alpine

RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p /workspace /logs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
