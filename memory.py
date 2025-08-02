from datetime import datetime
class ShortMemory:
    def __init__(self):
        self.history = []

    def add(self, role, content):
        """Adiciona mensagem ao histórico"""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_history(self):
        """Retorna cópia do histórico"""
        return self.history.copy()

    def clear(self):
        """Limpa memória de curto prazo"""
        self.history = []

    def load_history(self, history):
        """Carrega histórico existente"""
        self.history = history