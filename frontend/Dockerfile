<<<<<<< HEAD
FROM node:20-alpine
WORKDIR /app

# Copy file dependencies to optimize docker layer caching
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./

# Install project dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Remove workspace file if it's not needed for the container build
RUN rm -f pnpm-workspace.yaml

# Define build-time arguments for environment variables
ARG NEXT_PUBLIC_BACKEND_HOST=http://localhost:8000
ARG NEXT_PUBLIC_LPR_HOST=http://localhost:8000
ARG NEXT_PUBLIC_SLOT_HOST=http://localhost:8000

# Set environment variables using the build arguments
ENV NEXT_PUBLIC_BACKEND_HOST=$NEXT_PUBLIC_BACKEND_HOST
ENV NEXT_PUBLIC_LPR_HOST=$NEXT_PUBLIC_LPR_HOST
ENV NEXT_PUBLIC_SLOT_HOST=$NEXT_PUBLIC_SLOT_HOST

# Document that the container listens on port 3000
EXPOSE 3000

# Start the application in development mode
CMD ["npm", "run", "dev"]
=======

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_BACKEND_HOST=localhost:8000
ENV NEXT_PUBLIC_BACKEND_HOST=$NEXT_PUBLIC_BACKEND_HOST
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
>>>>>>> origin/master
