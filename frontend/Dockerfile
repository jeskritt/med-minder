FROM node:24-slim

WORKDIR /app

# Install pnpm (pinned to match frontend/pnpm-lock.yaml and Dockerfile)
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

# Install dependencies
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source
COPY . .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
