FROM node:20-slim AS deps

WORKDIR /repo
ENV NPM_CONFIG_LOGLEVEL=error
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_PROGRESS=false

COPY package.json package-lock.json /repo/
COPY apps/web/package.json /repo/apps/web/package.json
COPY packages/shared/package.json /repo/packages/shared/package.json

RUN npm ci --no-audit --no-fund --loglevel=error

FROM deps AS builder

ENV NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_APP_VERSION=v2026-02-26+r3-hardening

COPY apps/web /repo/apps/web
COPY packages/shared /repo/packages/shared

RUN npm -w @neonlanes/web run build

FROM node:20-slim AS runner

WORKDIR /repo
ENV NODE_ENV=production

COPY --from=deps /repo/node_modules /repo/node_modules
COPY --from=builder /repo/package.json /repo/package.json
COPY --from=builder /repo/apps/web /repo/apps/web
COPY --from=builder /repo/packages/shared /repo/packages/shared

EXPOSE 3000

CMD ["npm","-w","@neonlanes/web","run","start","--","--hostname","0.0.0.0","--port","3000"]
