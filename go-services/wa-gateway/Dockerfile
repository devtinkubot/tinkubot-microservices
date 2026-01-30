# ============================================================================
# Stage 1: Build
# ============================================================================
FROM golang:1.24-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata gcc musl-dev

# Create non-root user
RUN adduser -D -g '' appuser && mkdir -p /appuser && chown appuser /appuser

WORKDIR /build

# Copy go.mod and download base dependencies
COPY go.mod ./
RUN go mod download

# Copy ALL source code
COPY . .

# Generate go.sum with all dependencies and update go.mod
RUN go mod tidy

# Build the application
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags='-w -s -extldflags "-static"' \
    -o wa-gateway \
    ./cmd/wa-gateway/main.go

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM scratch

# Copy root filesystem from builder
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group
COPY --from=builder /appuser /appuser

# Copy binary
COPY --from=builder /build/wa-gateway /wa-gateway

# Use non-root user
USER appuser

# Expose port
EXPOSE 7000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/wa-gateway", "--healthcheck"] || exit 1

# Run the application
ENTRYPOINT ["/wa-gateway"]
