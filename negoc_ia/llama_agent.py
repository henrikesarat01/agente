import requests
import json

class LlamaAgent:
    def __init__(self, model="llama3:latest"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate_response(self, system_prompt, history, products):
        # Monta o prompt concatenando system + histórico
        conversa = system_prompt + "\n\n"
        for msg in history:
            role = "Cliente" if msg["role"] == "user" else "ANA"
            conversa += f"{role}: {msg['content']}\n"
        conversa += "ANA:"  # indica que agora é a vez da IA responder

        # Faz requisição ao Ollama com stream=True
        response = requests.post(
            self.url,
            json={
                "model": self.model, 
                "prompt": conversa, 
                "temperature": 0.7, 
                "max_tokens": 512,
                "stream": True  # Ativa streaming
            },
            stream=True
        )
        response.raise_for_status()

        full_response = ""
        # Processa cada chunk da resposta streamada
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        full_response += chunk['response']
                    if chunk.get('done', False):
                        break
                except json.JSONDecodeError:
                    continue

        return full_response.strip()