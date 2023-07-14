from core.handler import Handler
from core.utils import *
import json

class JdtlsProjectGetClasspaths(Handler):
    name = "jdtls_project_get_classpaths"
    method = "workspace/executeCommand"
    send_document_uri = False
    command = "java.project.getClasspaths"

    def process_request(self, file_path, scope) -> dict:
        arguments = [path_to_uri(file_path), json.dumps(dict(scope=scope))]

        return dict(command=self.command, arguments=arguments)

    def process_response(self, response) -> None:
        if response is not None and len(response) > 0 and "classpaths" in response:
            classpaths = response['classpaths']
            eval_in_emacs("lsp-bridge-jdtls-project-get-classpaths-response", classpaths)
