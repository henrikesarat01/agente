import os
import json
from datetime import datetime


class Storage:
    def __init__(self, storage_dir="data"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def save_session(self, session_data):
        """Salva nova sessão em disco"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{timestamp}.json"
        filepath = os.path.join(self.storage_dir, filename)

        with open(filepath, "w") as f:
            json.dump(session_data, f)

        return filename

    def update_session(self, filename, session_data):
        """Atualiza sessão existente"""
        filepath = os.path.join(self.storage_dir, filename)
        session_data["updated_at"] = datetime.now().isoformat()

        with open(filepath, "w") as f:
            json.dump(session_data, f)

    def load_session(self, filename):
        """Carrega sessão do disco"""
        filepath = os.path.join(self.storage_dir, filename)

        with open(filepath) as f:
            return json.load(f)

    def list_sessions(self, search_term=None):
        """Lista todas as sessões com filtro opcional"""
        sessions = []

        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.storage_dir, filename)

                try:
                    with open(filepath) as f:
                        data = json.load(f)
                        data["filename"] = filename

                        # Aplicar filtro de busca
                        if not search_term or (
                                search_term.lower() in data.get("client_name", "").lower() or
                                search_term in data.get("client_phone", "")
                        ):
                            sessions.append(data)

                except Exception as e:
                    print(f"Error loading {filename}: {str(e)}")

        # Ordenar por data de criação (mais recente primeiro)
        sessions.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        return sessions