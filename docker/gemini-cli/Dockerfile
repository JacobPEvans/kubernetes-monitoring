FROM node:24-alpine

RUN npm install -g @google/gemini-cli

RUN mkdir -p /workspace /logs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
