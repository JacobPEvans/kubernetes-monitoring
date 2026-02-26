FROM node:24-alpine

RUN npm install -g @google/gemini-cli

RUN mkdir -p /workspace /logs && chown -R node:node /workspace /logs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER node
WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
