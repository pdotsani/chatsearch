# Redis Queue System for Chat Application

This application uses Redis as a simple queue to prevent requests from being cut off and to handle high load scenarios.

## Architecture

- **Flask App**: Handles HTTP requests, queues chat messages, and processes them synchronously
- **Redis**: Simple message queue and job storage
- **Frontend**: Displays results immediately after processing

## Setup

1. **Install Redis** (if not already installed):
   ```bash
   # macOS
   brew install redis
   
   # Ubuntu/Debian
   sudo apt-get install redis-server
   
   # Start Redis
   redis-server
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Flask application**:
   ```bash
   python app.py
   ```

## How It Works

1. User sends a chat message through the web interface
2. Flask app adds the message to Redis queue
3. Flask app immediately processes the queue synchronously
4. Ollama processes the message and returns the result
5. Result is immediately displayed to the user

## API Endpoints

- `POST /chat` - Submit a chat message (returns HTML response)
- `GET /queue/stats` - Get queue statistics

## Environment Variables

- `REDIS_HOST` - Redis host (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)

## Benefits

- **No Request Timeouts**: Chat processing happens synchronously with Redis queue
- **Simplicity**: No separate worker process needed
- **Reliability**: Jobs are persisted in Redis
- **Monitoring**: Can track queue statistics
- **User Experience**: Immediate results with simple interface

## Monitoring

Visit `/queue/stats` to see:
- Number of queued jobs
- Redis connection status

## Troubleshooting

1. **Redis connection errors**: Check if Redis is running and verify host/port configuration
2. **Jobs not processing**: Check Flask logs for errors
