FROM node:24-alpine

RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p /workspace /logs && chown -R node:node /workspace /logs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER node
WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
