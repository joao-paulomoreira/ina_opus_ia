import base64
import requests
import json
import threading
import time
from datetime import datetime
import logging
import os

class GithunLogHandler:
    """
    Handler personalizado para enviar logs para o GitHub periodicamente.
    Integra com o sistema de logging existente no projeto
    """
    
    def __init__(self, log_file="app_log.log", github_token=None, repo_owner=None, repo_name=None, interval_minutes=10, branch="main"):
        """Inicializa o handler para envio de logs ao GitHub

        Args:
            log_file (str): Caminho do arquivo de log existente
            github_token (str): Token de acesso ao GitHub
            repo_owner (str): Nome do usuário/Organização GitHub.
            repo_name (str): Repositório do GitHub.
            interval_minutes (int): Intervalo entre envio de logs, atualmente 10 minutos.
            branch (str): Branch do repositório, padrão "main".
        """
        
        self.log_file = log_file
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.interval_minutes = interval_minutes
        self.branch = branch
        self.thread = None
        self.logger = logging.getLogger("github_logger")
        
        def start_periodic_commits(self):
            """Inicia o processo de commits periodico dos logs"""
            
            if not all ([self.github_token, self.repo_owner, self.repo_name]):
                self.logger.error("Configurações do GitHub incompletas. Não é possível iniciar os commits periódicos.")
                return False
            
            if not os.path.exists(self.log_file):
                self.logger.error(f"Arquivo de log '{self.log_file}' não encontrado.")
                return False
            
            def periodic_commit():
                while True:
                    try:
                        time.sleep(self.interval_minutes * 10)
                        
                        self.commit_logs_to_github()
                    except Exception as e:
                        self.logger.error(f"Erro na thread de commit periódico: {str(e)}")
                        
            self.thread = threading.Thread(target=periodic_commit, daemon=True)
            self.thread.start()
            
            self.logger.info(f"Commits periódicos para GitHub cofigurados a cada {self.interval_minutes} minutos.")
            return True
        
        def commit_logs_to_github(self):
            """Envia os logs atuais para o GitHub"""
            
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_path = f"logs/app_log_{timestamp}.log"
                
                with open(self.log_file, "r", encoding="utf-8") as f:
                    log_content = f.read()
                    
                content_bytes = log_content.encode("utf-8")
                base64_content = base64.b64decode(content_bytes).decode("utf-8")
                
                commit_data = {
                    "message": f"Logs automáticos - {timestamp}",
                    "content": base64_content,
                    "branch": self.branch
                }
                
                api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{log_path}"
                
                headers = {
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                response = requests.put(
                api_url, 
                headers=headers, 
                data=json.dumps(commit_data)
                )
                
                if response.status_code in [201, 200]:
                    self.logger.info(f"Logs enviados com sucesso para: {log_path}")
                    return True
                else:
                    self.logger.error(f"Falha ao enviar logs:{response.status_code} - {response.text}")
                    return False
                
            except Exception as e:
                self.logger.erro(f"Erro ao fazer commit o dos logs: {str(e)}")
                return False