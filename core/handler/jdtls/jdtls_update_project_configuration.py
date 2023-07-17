from core.handler import Handler
from core.utils import *

class JdtlsUpdateProjectConfiguration(Handler):
    name = "jdtls_update_project_configuration"
    method = "java/projectConfigurationUpdate"
    send_document_uri = False

    def process_request(self, file_path) -> dict:
        project_path = get_project_path(file_path)
        project_uri = path_to_uri(project_path)

        return dict(uri=project_uri)

    def process_response(self, response) -> None:
        pass
