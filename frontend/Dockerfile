FROM node:20-alpine
WORKDIR /app

# Copy package.json to install dependencies
COPY package.json ./

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