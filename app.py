from ollama import chat
from ollama import ChatResponse
from flask import Flask
from flask import request
import mistune

app = Flask(__name__)

@app.post("/chat")
def send_chat_message():
  data = request.get_json()
  message = data['message']
  app.logger.info(f"Recieved message: {message}")

  response: ChatResponse = chat(model='gemma3', messages=[
    {
      'role': 'user',
      'content': message,
    },
  ])

  markdown = mistune.html(response['message']['content'])

  app.logger.info(f"Returning response")
  return markdown