from core.handler import Handler
from core.utils import *

class JdtlsProjectIsTestFile(Handler):
    name = "jdtls_project_is_test_file"
    method = "workspace/executeCommand"
    send_document_uri = False
    command = "java.project.isTestFile"

    def process_request(self, file_path) -> dict:
        file_uri = path_to_uri(file_path)

        return dict(command=self.command, arguments=[file_uri])

    def process_response(self, response) -> None:
        eval_in_emacs("lsp-bridge-jdtls-project-is-test-file-response", response)
