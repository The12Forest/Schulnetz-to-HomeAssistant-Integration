FROM node:22-bookworm-slim

# Chromium system dependencies are installed by `playwright install --with-deps`.
WORKDIR /app

COPY server/package.json server/package-lock.json ./
RUN npm ci --omit=dev

# Install the Chromium browser matching the pinned Playwright version.
RUN npx playwright install --with-deps chromium

COPY server/src ./src

ENV PORT=80
ENV DATA_DIR=/app/data

EXPOSE 80

CMD ["node", "src/index.js"]
