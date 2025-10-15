from ollama import chat
from ollama import ChatResponse
from flask import Flask, request, render_template, jsonify
import mistune
import redis
import uuid
import time
import os
import json
import threading

# Redis connection
redis_conn = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), 
                        port=int(os.getenv('REDIS_PORT', 6379)), 
                        db=0, 
                        decode_responses=True)

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max content length

def background_worker():
    """Background worker that processes the queue"""
    while True:
        try:
            process_queue()
            time.sleep(1)  # Check every second
        except Exception as e:
            app.logger.error(f"Error in background worker: {str(e)}")
            time.sleep(5)  # Wait longer on error

# Start background worker
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

def add_to_queue(message):
    """Add message to Redis queue"""
    job_id = str(uuid.uuid4())
    job_data = {
        'id': job_id,
        'message': message,
        'status': 'queued',
        'created_at': time.time()
    }
    
    # Add to queue
    redis_conn.lpush('chat_queue', json.dumps(job_data))
    app.logger.info(f"Added job {job_id} to queue: {message}")
    
    # Store job data for status checking
    redis_conn.setex(f'job:{job_id}', 3600, json.dumps(job_data))  # Expire in 1 hour
    
    return job_id

def process_queue():
    """Process messages from Redis queue"""
    try:
        # Get message from queue (blocking with timeout)
        result = redis_conn.brpop('chat_queue', timeout=1)
        
        if result:
            _, job_json = result
            job_data = json.loads(job_json)
            job_id = job_data['id']
            message = job_data['message']
            
            app.logger.info(f"Processing message: {message}")
            
            # Update status to processing
            job_data['status'] = 'processing'
            redis_conn.setex(f'job:{job_id}', 3600, json.dumps(job_data))
            
            try:
                # Process with Ollama
                response: ChatResponse = chat(model='gemma3', messages=[
                    {
                        'role': 'user',
                        'content': message,
                    },
                ])
                
                markdown = mistune.html(response['message']['content'])
                
                html = f"""
                <div class="message bot-message markdown-body">
                    <strong>Bot:</strong> {markdown}
                </div>
                """
                
                # Update job with result
                job_data['status'] = 'completed'
                job_data['result'] = html
                job_data['completed_at'] = time.time()
                redis_conn.setex(f'job:{job_id}', 3600, json.dumps(job_data))
                
                app.logger.info(f"Completed job {job_id}")
                
            except Exception as e:
                app.logger.error(f"Error processing message: {str(e)}")
                job_data['status'] = 'failed'
                job_data['error'] = str(e)
                job_data['failed_at'] = time.time()
                redis_conn.setex(f'job:{job_id}', 3600, json.dumps(job_data))
                
    except Exception as e:
        app.logger.error(f"Error in process_queue: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.get("/test")
def test_endpoint():
    return jsonify({"status": "ok", "message": "Server is running"})

@app.get("/get-response/<job_id>")
def get_response(job_id):
    """Get the processed response for a job"""
    try:
        job_data_json = redis_conn.get(f'job:{job_id}')
        if job_data_json:
            job_data = json.loads(job_data_json)
            
            if job_data['status'] == 'completed':
                return job_data['result']
            elif job_data['status'] == 'failed':
                return f"<div class='message bot-message markdown-body'><strong>Bot:</strong> <em>❌ Error: {job_data.get('error', 'Unknown error')}</em></div>"
            else:
                return "<div class='message bot-message markdown-body'><strong>Bot:</strong> <em>⏳ Still processing...</em></div>"
        else:
            return "<div class='message bot-message markdown-body'><strong>Bot:</strong> <em>❌ Job not found</em></div>"
    except Exception as e:
        app.logger.error(f"Error getting response: {str(e)}")
        return "<div class='message bot-message markdown-body'><strong>Bot:</strong> <em>❌ Error retrieving response</em></div>"

@app.post("/chat")
def send_chat_message():
    # Try to get message from various sources
    message = request.values.get('message')
    if not message and request.is_json:
        json_data = request.get_json()
        if json_data:
            message = json_data.get('message')
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    app.logger.info(f"Received message: {message}")
    
    # Add to queue
    job_id = add_to_queue(message)
    
    # Check if this is an HTMX request
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if is_htmx:
        # Return processing message with polling
        processing_html = f"""
        <div id="bot-response-{job_id}" class="message bot-message markdown-body">
            <strong>Bot:</strong> <em>🤔 Thinking...</em>
        </div>
        <script>
            // Poll for the actual response
            let pollCount = 0;
            const maxPolls = 30; // 30 seconds max
            
            function pollForResponse() {{
                pollCount++;
                if (pollCount > maxPolls) {{
                    const botResponse = document.getElementById('bot-response-{job_id}');
                    if (botResponse) {{
                        botResponse.innerHTML = '<strong>Bot:</strong> <em>⏰ Timeout - please try again</em>';
                    }}
                    return;
                }}
                
                fetch('/get-response/{job_id}')
                    .then(response => response.text())
                    .then(html => {{
                        const botResponse = document.getElementById('bot-response-{job_id}');
                        if (botResponse) {{
                            if (html.includes('Still processing')) {{
                                // Still processing, poll again
                                setTimeout(pollForResponse, 1000);
                            }} else {{
                                // Got the final result
                                botResponse.outerHTML = html;
                            }}
                        }}
                    }})
                    .catch(error => {{
                        const botResponse = document.getElementById('bot-response-{job_id}');
                        if (botResponse) {{
                            botResponse.innerHTML = '<strong>Bot:</strong> <em>❌ Error processing your message</em>';
                        }}
                    }});
            }}
            
            // Start polling after a short delay
            setTimeout(pollForResponse, 1000);
        </script>
        """
        return processing_html
    else:
        # Return JSON for API requests
        return jsonify({
            'job_id': job_id,
            'status': 'completed',
            'message': 'Message processed'
        })

@app.get("/queue/stats")
def get_queue_stats():
    """Get queue statistics"""
    try:
        queue_length = redis_conn.llen('chat_queue')
        return jsonify({
            'queued': queue_length,
            'redis_connected': True
        })
    except Exception as e:
        app.logger.error(f"Error getting queue stats: {str(e)}")
        return jsonify({'error': 'Redis connection error', 'redis_connected': False}), 500

@app.post("/process-queue")
def process_queue_endpoint():
    """Manually process the queue"""
    try:
        process_queue()
        return jsonify({'status': 'success', 'message': 'Queue processed'})
    except Exception as e:
        app.logger.error(f"Error processing queue: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
