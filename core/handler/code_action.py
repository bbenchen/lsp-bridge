from core.handler import Handler
from core.utils import *


class CodeAction(Handler):
    name = "code_action"
    method = "textDocument/codeAction"
    cancel_on_change = True
    provider = "code_action_provider"
    provider_message = "Current server not support code action."

    def process_request(self, lsp_server_name, diagnostics, range_start, range_end, action_kind) -> dict:
        self.action_kind = action_kind
        self.lsp_server_name = lsp_server_name

        range = {
            "start": range_start,
            "end": range_end
        }

        if isinstance(action_kind, str):
            context = {
                "diagnostics": diagnostics,
                "only": [action_kind]
            }
        else:
            context = {
                "diagnostics": diagnostics
            }

        return dict(range=range, context=context)

    def process_response(self, response) -> None:
        if response is not None and self.lsp_server_name == "jdtls":
            actions = []
            for action in response:
                if len(actions) == 0:
                    actions.append(action)
                else:
                    exists = False

                    for tmp_action in actions:
                        if action["title"] == tmp_action["title"]:
                            exists = True
                            break

                    if exists is False:
                        actions.append(action)
        else:
            actions = response

        remote_connection_info = get_remote_connection_info()
        if remote_connection_info != "":
            for item in actions:
                convert_workspace_edit_path_to_tramped_path(item["edit"], remote_connection_info)
        self.file_action.push_code_actions(actions, self.lsp_server_name, self.action_kind)
