import os
from openai import OpenAI


class OpenAIAgent:
    def __init__(self, api_key, assistant_id):
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        self.thread = None

    def start_new_conversation(self):
        self.thread = self.client.beta.threads.create()

    def generate_response(self, user_message):
        # Adiciona mensagem do usuário à thread
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=user_message
        )

        # Executa o assistente
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant_id
        )

        # Aguarda a conclusão da execução
        while run.status != "completed":
            run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=run.id
            )

        # Recupera as mensagens do assistente
        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread.id
        )

        # Filtra apenas as respostas do assistente
        assistant_responses = [
            msg.content[0].text.value
            for msg in messages.data
            if msg.role == "assistant"
        ]

        return assistant_responses[0] if assistant_responses else ""