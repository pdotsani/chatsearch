from ollama import chat
from ollama import ChatResponse
from flask import Flask, request, render_template
import mistune

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.post("/chat")
def send_chat_message():
  message = request.form.get('message') or request.form.get_json('message')

  app.logger.info(f"Recieved message: {message}")

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
    
  return html

if __name__ == "__main__"
  app.run(host="0.0.0.0", port=5000)