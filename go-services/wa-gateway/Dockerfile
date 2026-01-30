# ============================================================================
# Stage 1: Build
# ============================================================================
FROM golang:1.24-alpine AS builder

# Install build dependencies (gcc for CGO to build sqlite3)
RUN apk add --no-cache git ca-certificates tzdata gcc musl-dev

WORKDIR /build

# Copy go.mod and download base dependencies
COPY go.mod ./
RUN go mod download

# Copy ALL source code
COPY . .

# Generate go.sum with all dependencies and update go.mod
RUN go mod tidy

# Build the application with CGO_ENABLED for SQLite support
RUN CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build \
    -ldflags='-w -s' \
    -o wa-gateway \
    ./cmd/wa-gateway/main.go

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM alpine:latest

# Install runtime dependencies
RUN apk --no-cache add ca-certificates sqlite-libs

WORKDIR /app

# Create data directory for SQLite database
RUN mkdir -p data

# Copy binary from builder
COPY --from=builder /build/wa-gateway .

# Expose port
EXPOSE 7000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/app/wa-gateway", "--healthcheck"] || exit 1

# Run the application
ENTRYPOINT ["/app/wa-gateway"]
