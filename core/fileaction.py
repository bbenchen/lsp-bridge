#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2022 Andy Stewart
#
# Author:     Andy Stewart <lazycat.manatee@gmail.com>
# Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from core.utils import get_command_result, eval_in_emacs, generate_request_id, get_emacs_var
import os
import random
import threading
import time

class FileAction(object):

    def __init__(self, filepath, lang_server):
        object.__init__(self)
        
        # Build request functions.
        for name in ["find_define", "find_references", "prepare_rename", "rename", "completion"]:
            self.build_request_function(name)
            
        # Init.
        self.filepath = filepath
        self.request_dict = {}
        self.completion_request_list = []
        self.find_define_request_list = []
        self.find_references_request_list = []
        self.prepare_rename_request_list = []
        self.rename_request_list = []
        self.last_change_file_time = -1
        self.last_change_file_line_text = ""
        self.last_change_cursor_time = -1
        self.completion_prefix_string = ""
        self.version = 1
        self.try_completion_timer = None
        
        # Read language server information.
        self.lang_server_info = None
        self.lang_server_info_path = ""
        if os.path.exists(lang_server):
            # If lang_server is real file path, we load the LSP server configuration from the user specified file.
            self.lang_server_info_path = lang_server
        else:
            # Otherwise, we load LSP server configuration from file lsp-bridge/langserver/lang_server.json.
            self.lang_server_info_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "langserver", "{}.json".format(lang_server))
            
        with open(self.lang_server_info_path) as f:
            import json
            self.lang_server_info = json.load(f)
        
        self.lsp_server = None

        # Generate initialize request id.
        self.initialize_id = generate_request_id()

        # Project path is same as file path if open an isolated file.
        # Otherwise use git root patch as project path.
        dir_path = os.path.dirname(filepath)
        self.project_path = filepath
        if get_command_result("cd {} ; git rev-parse --is-inside-work-tree".format(dir_path)) == "true":
            self.project_path = get_command_result("cd {} ; git rev-parse --show-toplevel".format(dir_path))

    def get_lsp_server_name(self):
        # We use project path and LSP server type as unique name.
        return "{}#{}".format(self.project_path, self.lang_server_info["name"])

    def change_file(self, start_row, start_character, end_row, end_character, range_length, change_text, row, column, before_char, line_text):
        # Send didChange request to LSP server.
        if self.lsp_server is not None:
            self.lsp_server.send_did_change_notification(
                self.filepath, self.version, start_row, start_character, end_row, end_character, range_length, change_text)
        else:
            # Please report bug if you got this message.
            print("IMPOSSIBLE HERE: change_file ", self.filepath, self.lsp_server)

        self.version += 1

        # Try cancel expired completion timer.
        if self.try_completion_timer is not None and self.try_completion_timer.is_alive():
            self.try_completion_timer.cancel()

        # Record last change information.
        self.last_change_file_time = time.time()
        self.last_change_file_line_text = line_text

        # Send textDocument/completion 100ms later.
        self.try_completion_timer = threading.Timer(0.1, lambda : self.completion(row, column, before_char))
        self.try_completion_timer.start()

    def change_cursor(self):
        # Record change cursor time.
        self.last_change_cursor_time = time.time()

    def build_request_function(self, name):
        def _do(*args):
            request_id = generate_request_id()
            getattr(self, "{}_request_list".format(name)).append(request_id)
            
            # Cache last change information to compare after receive LSP server response message.
            self.request_dict[request_id] = {
                "last_change_file_time": self.last_change_file_time,
                "last_change_cursor_time": self.last_change_cursor_time
            }

            if self.lsp_server is not None:
                args = (request_id, self.filepath, name) + args
                getattr(self.lsp_server, "send_{}_request".format(name))(*args)

        setattr(self, name, _do)

    def handle_server_response_message(self, request_id, request_type, response_result):
        if request_type == "completion":
            self.handle_completion_response(request_id, response_result)
        elif request_type == "find_define":
            self.handle_find_define_response(request_id, response_result)
        elif request_type == "find_references":
            self.handle_find_references_response(request_id, response_result)
        elif request_type == "prepare_rename":
            self.handle_prepare_rename_response(request_id, response_result)
        elif request_type == "rename":
            self.handle_rename_response(request_id, response_result)
                
    def handle_completion_response(self, request_id, response_result):
        # Stop send completion items to client if request id expired, or change file, or move cursor.
        if (request_id == self.completion_request_list[-1] and 
            self.request_dict[request_id]["last_change_file_time"] == self.last_change_file_time and 
            self.request_dict[request_id]["last_change_cursor_time"] == self.last_change_cursor_time):
            
            self.completion_prefix_string = self.calc_completion_prefix_string()
            
            completion_items = list(filter(lambda label: label.startswith(self.completion_prefix_string), 
                                           list(map(lambda item: item["label"], response_result["items"]))))
                    
            eval_in_emacs("lsp-bridge-record-completion-items", [self.filepath, completion_items])
            
    def calc_completion_prefix_string(self):
        string_after_dot = self.last_change_file_line_text[self.last_change_file_line_text.rfind(".") + 1:]
        split_strings = string_after_dot.split()
        if len(split_strings) > 0:
            return split_strings[-1]
        else:
            return ""
            
    def handle_find_define_response(self, request_id, response_result):
        # Stop send jump define if request id expired, or change file, or move cursor.
        if (request_id == self.find_define_request_list[-1] and 
            self.request_dict[request_id]["last_change_file_time"] == self.last_change_file_time and 
            self.request_dict[request_id]["last_change_cursor_time"] == self.last_change_cursor_time):
            
            if response_result:
                try:
                    file_info = response_result[0]
                    filepath = file_info["uri"][len("file://"):]
                    row = file_info["range"]["start"]["line"]
                    column = file_info["range"]["start"]["character"]
                    eval_in_emacs("lsp-bridge-jump-to-define", [filepath, row, column])
                except:
                    print("* Failed information about find_define response.")
                    import traceback
                    traceback.print_exc()
            else:
                eval_in_emacs("message", ["Can't find define."])
                
    def handle_find_references_response(self, request_id, response_result):
        if request_id == self.find_references_request_list[-1]:
            print(response_result)
            
    def handle_prepare_rename_response(self, request_id, response_result):
        if request_id == self.prepare_rename_request_list[-1]:
            eval_in_emacs("lsp-bridge-rename-highlight", [
                self.filepath,
                response_result["start"]["line"],
                response_result["start"]["character"],
                response_result["end"]["character"]
            ])
            
    def handle_rename_response(self, request_id, response_result):
        if request_id == self.rename_request_list[-1]:
            if response_result:
                try:
                    counter = 0
                    rename_files = []
                    for rename_info in response_result["documentChanges"]:
                        (rename_file, rename_counter) = self.rename_symbol_in_file(rename_info)
                        rename_files.append(rename_file)
                        counter += rename_counter
                        
                    eval_in_emacs("lsp-bridge-rename-finish", [rename_files, counter])
                except:
                    print("* Failed information about rename response.")
                    import traceback
                    traceback.print_exc()
            
    def rename_symbol_in_file(self, rename_info):
        rename_file = rename_info["textDocument"]["uri"]
        if rename_file.startswith("file://"):
            rename_file = rename_file[len("file://"):]
            
        lines = []
        rename_counter = 0
        
        with open(rename_file, "r") as f:
            lines = f.readlines()
            
            line_offset_dict = {}
            
            edits = rename_info["edits"]
            for edit_info in edits:
                # Get replace line.
                replace_line = edit_info["range"]["start"]["line"]
                
                # Get current line offset, if previous edit is same as current line.
                # We need add changed offset to make sure current edit has right column.
                replace_line_offset = 0
                if replace_line in line_offset_dict:
                    replace_line_offset = line_offset_dict[replace_line]
                else:
                    line_offset_dict[replace_line] = 0
                
                # Calculate replace column offset.
                replace_column_start = edit_info["range"]["start"]["character"] + replace_line_offset
                replace_column_end = edit_info["range"]["end"]["character"] + replace_line_offset
                
                # Get current line.
                line_content = lines[replace_line]
                
                # Get new changed offset.
                new_text = edit_info["newText"]
                replace_offset = len(new_text) - (replace_column_end - replace_column_start)
                
                # Overlapping new changed offset.
                line_offset_dict[replace_line] = line_offset_dict[replace_line] + replace_offset
                
                # Replace current line.
                new_line_content = line_content[:replace_column_start] + new_text + line_content[replace_column_end:]
                lines[replace_line] = new_line_content
                
                rename_counter += 1
                
        with open(rename_file, "w") as f:
            f.writelines(lines)
            
        return (rename_file, rename_counter)