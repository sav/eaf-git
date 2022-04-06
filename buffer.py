#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2018 Andy Stewart
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

from PyQt6 import QtCore
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QThread
from core.webengine import BrowserBuffer
from core.utils import get_emacs_func_result, get_emacs_var, PostGui, message_to_emacs, eval_in_emacs
from pygit2 import (Repository, IndexEntry,
                    GIT_SORT_TOPOLOGICAL,
                    GIT_STATUS_CURRENT,
                    GIT_STATUS_INDEX_NEW,
                    GIT_STATUS_INDEX_MODIFIED,
                    GIT_STATUS_INDEX_DELETED,
                    GIT_STATUS_INDEX_RENAMED,
                    GIT_STATUS_INDEX_TYPECHANGE,
                    GIT_STATUS_WT_NEW,
                    GIT_STATUS_WT_MODIFIED,
                    GIT_STATUS_WT_DELETED,
                    GIT_STATUS_WT_TYPECHANGE,
                    GIT_STATUS_WT_RENAMED,
                    GIT_STATUS_WT_UNREADABLE,
                    GIT_STATUS_IGNORED,
                    GIT_STATUS_CONFLICTED,
                    GIT_CHECKOUT_FORCE,
                    discover_repository)
from datetime import datetime
from pathlib import Path
import os
import json
import shutil
import pygit2

GIT_STATUS_DICT = {
    GIT_STATUS_CURRENT: "Current",
    GIT_STATUS_INDEX_NEW: "New",
    GIT_STATUS_INDEX_MODIFIED: "Modified",
    GIT_STATUS_INDEX_DELETED: "Deleted",
    GIT_STATUS_INDEX_RENAMED: "Renamed",
    GIT_STATUS_INDEX_TYPECHANGE: "Typechange",
    GIT_STATUS_WT_NEW: "New",
    GIT_STATUS_WT_MODIFIED: "Modified",
    GIT_STATUS_WT_DELETED: "Deleted",
    GIT_STATUS_WT_TYPECHANGE: "Typechange",
    GIT_STATUS_WT_RENAMED: "Renamed",
    GIT_STATUS_WT_UNREADABLE: "Unreadable",
    GIT_STATUS_IGNORED: "Ignored",
    GIT_STATUS_CONFLICTED: "Conflicted"
}

def pretty_date(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    elif not time:
        diff = 0
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff // 60) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(second_diff // 3600) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff // 7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff // 30) + " months ago"
    return str(day_diff // 365) + " years ago"

def get_command_result(command_string):
    import subprocess
        
    process = subprocess.Popen(command_string, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.wait()
    return "".join(process.stdout.readlines())

class AppBuffer(BrowserBuffer):
    def __init__(self, buffer_id, url, arguments):
        BrowserBuffer.__init__(self, buffer_id, url, arguments, False)

        self.stage_status = []
        self.unstage_status = []
        self.untrack_status = []
        
        self.branch_status = []
        
        self.fetch_status_threads = []
        self.fetch_log_threads = []
        self.fetch_submodule_threads = []
        self.fetch_branch_threads = []
        self.fetch_pull_threads = []
        self.fetch_unpush_threads = []
        
        self.git_push_threads = []

        self.url = os.path.expanduser(self.url)
        self.repo = Repository(self.url)
        self.repo_root = self.url
            
        self.repo_path = os.path.sep.join(list(filter(lambda x: x != '', self.repo_root.split(os.path.sep)))[-2:])

        self.last_commit_id = str(self.repo.head.target)[:7]
        self.last_commit = self.repo.revparse_single(str(self.repo.head.target))
        self.last_commit_message = self.last_commit.message.splitlines()[0]
        
        self.load_index_html(__file__)
        
    def init_app(self):
        self.init_vars()
        self.update_git_info()

    def update_git_info(self):
        self.fetch_unpush_info()
        self.fetch_status_info()
        self.fetch_log_info()
        self.fetch_submodule_info()
        self.fetch_branch_info()

    def init_vars(self):
        if self.theme_mode == "dark":
            if self.theme_background_color == "#000000":
                select_color = "#333333"
            else:
                select_color = QColor(self.theme_background_color).darker(120).name()
        else:
            if self.theme_background_color == "#FFFFFF":
                select_color = "#EEEEEE"
            else:
                select_color = QColor(self.theme_background_color).darker(110).name()

        (text_color, nav_item_color, info_color, date_color, id_color, author_color) = get_emacs_func_result(
            "get-emacs-face-foregrounds",
            ["default",
             "font-lock-function-name-face",
             "font-lock-keyword-face",
             "font-lock-builtin-face",
             "font-lock-comment-face",
             "font-lock-string-face"])

        self.buffer_widget.eval_js('''init(\"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", \"{}\", {})'''.format(
            self.theme_background_color, self.theme_foreground_color, select_color, QColor(self.theme_background_color).darker(110).name(),
            text_color, nav_item_color, info_color,
            date_color, id_color, author_color,
            self.repo_path, self.last_commit_id, self.last_commit_message,
            self.get_keybinding_info()))

    def fetch_status_info(self):
        thread = FetchStatusThread(self.repo)
        thread.fetch_result.connect(self.update_status_info)
        self.fetch_status_threads.append(thread)
        thread.start()
        
    @PostGui()
    def update_status_info(self, stage_status, unstage_status, untrack_status):
        self.buffer_widget.eval_js('''updateStatusInfo({}, {}, {})'''.format(json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status)))

    def get_keybinding_info(self):
        js_keybindig = get_emacs_var("eaf-git-js-keybinding")
        js_keybindig_dict = {}
        
        for keybindig_list in js_keybindig:
            module_name = keybindig_list[0]
            module_keybinding_dict = {}
            
            for key_value in keybindig_list[1:][0]:
                module_keybinding_dict[key_value[0]] = {
                    "command": key_value[1][0],
                    "description": key_value[1][1]
                }
                
            js_keybindig_dict[module_name] = module_keybinding_dict    

        return js_keybindig_dict
        
    def fetch_unpush_info(self):
        thread = FetchUnpushThread(self.repo, self.repo_root)
        thread.fetch_result.connect(self.update_unpush_info)
        self.fetch_unpush_threads.append(thread)
        thread.start()
        
    @PostGui()
    def update_unpush_info(self, info):
        self.buffer_widget.eval_js('''updateUnpushInfo({})'''.format(json.dumps(
            {"info": info}
        )))

    def fetch_log_info(self):
        thread = FetchLogThread(self.repo)
        thread.fetch_result.connect(self.update_log_info)
        self.fetch_log_threads.append(thread)
        thread.start()

    @PostGui()
    def update_log_info(self, log):
        self.buffer_widget.eval_js('''updateLogInfo({})'''.format(json.dumps(log)))

    def fetch_submodule_info(self):
        thread = FetchSubmoduleThread(self.repo)
        thread.fetch_result.connect(self.update_submodule_info)
        self.fetch_submodule_threads.append(thread)
        thread.start()

    @PostGui()
    def update_submodule_info(self, submodule):
        self.buffer_widget.eval_js('''updateSubmoduleInfo({})'''.format(json.dumps(submodule)))

    def fetch_branch_info(self):
        thread = FetchBranchThread(self.repo)
        thread.fetch_result.connect(self.update_branch_info)
        self.fetch_branch_threads.append(thread)
        thread.start()

    @PostGui()
    def update_branch_info(self, branch_list):
        self.update_branch_list(branch_list)

    @QtCore.pyqtSlot()
    def copy_change_files_to_mirror_repo(self):
        status = list(filter(lambda info: info[1] != GIT_STATUS_IGNORED, list(self.repo.status().items())))
        
        if len(status) > 0:
            self.send_input_message("Copy changes file to: ", "copy_changes_file_to_mirror", "file", self.repo_root)
        else:
            message_to_emacs("No file need submitted, nothing to copy.")
            
    def handle_input_response(self, callback_tag, result_content):
        if callback_tag == "copy_changes_file_to_mirror":
            self.handle_copy_changes_file_to_mirror(result_content)
        elif callback_tag == "delete_untrack_file":
            self.handle_delete_untrack_file()
        elif callback_tag == "delete_unstage_file":
            self.handle_delete_unstage_file()
        elif callback_tag == "delete_stage_file":
            self.handle_delete_stage_file()
        elif callback_tag == "delete_untrack_files":
            self.handle_delete_untrack_files()
        elif callback_tag == "delete_unstage_files":
            self.handle_delete_unstage_files()
        elif callback_tag == "delete_stage_files":
            self.handle_delete_stage_files()
        elif callback_tag == "commit_stage_files":
            self.handle_commit_stage_files(result_content)
        elif callback_tag == "commit_all_files":
            self.handle_commit_all_files(result_content)
        elif callback_tag == "commit_and_push":
            self.handle_commit_and_push(result_content)
        elif callback_tag == "checkout_all_files":
            self.handle_checkout_all_files()
        elif callback_tag == "search_text_forward":
            self.buffer_widget._search_text(result_content)
        elif callback_tag == "search_text_backward":
            self.buffer_widget._search_text(result_content, True)
        elif callback_tag == "new_branch":
            self.handle_new_branch(result_content)
        elif callback_tag == "delete_branch":
            self.handle_delete_branch()
            
    def cancel_input_response(self, callback_tag):
        ''' Cancel input message.'''
        if callback_tag == "search_text_forward" or callback_tag == "search_text_backward":
            self.buffer_widget.clean_search_and_select()
            
    def handle_copy_changes_file_to_mirror(self, target_repo_dir):
        status = list(filter(lambda info: info[1] != GIT_STATUS_IGNORED, list(self.repo.status().items())))
        files = list(map(lambda info: info[0], status))
        
        for file in files:
            shutil.copy(os.path.join(self.repo_root, file), os.path.join(target_repo_dir, file))
            
        message_to_emacs("Copy {} files to {}".format(len(files), os.path.join(target_repo_dir)))    

    @QtCore.pyqtSlot(str, str)
    def show_commit_diff(self, commit_id, previous_commit_id):
        eval_in_emacs("eaf-git-show-commit-diff", [self.repo.diff(previous_commit_id, commit_id).patch])
        
    @QtCore.pyqtSlot(str, str)
    def update_diff(self, type, file):
        
        diff_string = ""
        
        if type == "untrack":
            if file == "":
                for status in self.untrack_status:
                    with open(os.path.join(self.repo_root, status["file"])) as f:
                        diff_string += "Untrack file: {}\n\n".format(status["file"])
                        diff_string += f.read()
                        diff_string += "\n"
            else:
                with open(os.path.join(self.repo_root, file)) as f:
                    diff_string = f.read()
        elif type == "stage":
            if file == "":
                diff_string = get_command_result("cd {}; git diff --color --staged".format(self.repo_root))
            else:
                diff_string = get_command_result("cd {}; git diff --color --staged {}".format(self.repo_root, file))
        elif type == "unstage":
            if file == "":
                diff_string = get_command_result("cd {}; git diff --color".format(self.repo_root))
            else:
                diff_string = get_command_result("cd {}; git diff --color {}".format(self.repo_root, file))
                
        self.buffer_widget.eval_js('''updateChangeDiff({})'''.format(json.dumps(diff_string)))        
        
    @QtCore.pyqtSlot()
    def status_commit_stage(self):
        self.send_input_message("Commit stage files with message: ", "commit_stage_files")
    
    @QtCore.pyqtSlot()
    def status_commit_all(self):
        self.send_input_message("Commit all files with message: ", "commit_all_files")
    
    @QtCore.pyqtSlot()
    def status_commit_and_push(self):
        self.send_input_message("Commit all files with message: ", "commit_and_push")
    
    @QtCore.pyqtSlot(str, int)
    def status_stage_file(self, type, file_index):
        if type == "untrack":
            if file_index == -1:
                self.stage_untrack_files()
            else:
                self.stage_untrack_file(self.untrack_status[file_index])
        elif type == "unstage":
            if file_index == -1:
                self.stage_unstage_files()
            else:
                self.stage_unstage_file(self.unstage_status[file_index])
    
    def git_add_file(self, path):
        index = self.repo.index
        index.add(path)
        index.write()
        
    def git_reset_file(self, path):
        index = self.repo.index

        # Remove path from the index
        index.remove(path)

        # Restore object from db
        obj = self.repo.revparse_single('HEAD').tree[path] # Get object from db
        index.add(IndexEntry(path, obj.id, obj.filemode)) # Add to index

        # Write index
        index.write()
        
    def git_checkout_file(self, paths=[]):
        self.repo.checkout(self.repo.lookup_reference(self.repo.head.name), paths=paths, strategy=GIT_CHECKOUT_FORCE)
        
    def stage_untrack_files(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        for file_info in untrack_status:
            self.git_add_file(file_info["file"])
        stage_status += untrack_status
        untrack_status = []
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
            
    def stage_unstage_files(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        for file_info in unstage_status:
            self.git_add_file(file_info["file"])
        stage_status += unstage_status
        unstage_status = []
        
        select_item_type = "stage"
        select_item_index = -1
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
    
    def stage_untrack_file(self, file_info):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        self.git_add_file(file_info["file"])
        
        stage_status.append(file_info)
        untrack_file_index = untrack_status.index(file_info)
        untrack_status.remove(file_info)
        
        select_item_type = ""
        select_item_index = -1
        if len(untrack_status) > 0:
            select_item_type = "untrack"
            select_item_index = max(untrack_file_index - 1, 0)
        elif len(unstage_status) > 0:
            select_item_type = "unstage"
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
    
    def stage_unstage_file(self, file_info):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        self.git_add_file(file_info["file"])
        
        stage_status.append(file_info)
        unstage_file_index = unstage_status.index(file_info)
        unstage_status.remove(file_info)
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
            select_item_index = max(unstage_file_index - 1, 0)
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))

    @QtCore.pyqtSlot(str, int)
    def status_delete_file(self, type, file_index):
        if type == "untrack":
            if file_index == -1:
                self.send_input_message("Discard untracked files?", "delete_untrack_files", "yes-or-no")
            else:
                self.delete_untrack_file(self.untrack_status[file_index])
        elif type == "unstage":
            if file_index == -1:
                self.send_input_message("Discard unstaged files?", "delete_unstage_files", "yes-or-no")
            else:
                self.delete_unstage_file(self.unstage_status[file_index])
        elif type == "stage":
            if file_index == -1:
                self.send_input_message("Discard staged files?", "delete_stage_files", "yes-or-no")
            else:
                self.delete_stage_file(self.stage_status[file_index])

    def delete_untrack_file(self, file_info):
        self.delete_untrack_mark_file = file_info
        self.send_input_message("Discard untracked changes in {}?".format(file_info["file"]), "delete_untrack_file", "yes-or-no")
    
    def delete_unstage_file(self, file_info):
        self.delete_unstage_mark_file = file_info
        self.send_input_message("Discard unstaged changes in {}?".format(file_info["file"]), "delete_unstage_file", "yes-or-no")
    
    def delete_stage_file(self, file_info):
        self.delete_stage_mark_file = file_info
        self.send_input_message("Discard staged changes in {}?".format(file_info["file"]), "delete_stage_file", "yes-or-no")
        
    def handle_delete_untrack_files(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        delete_file_number = len(self.untrack_status)
        
        for untrack_file in self.untrack_status:
            os.remove(os.path.join(self.repo_root, untrack_file["file"]))
        
        untrack_status = []
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
        
        if delete_file_number > 1:
            message_to_emacs("Delete {} files.".format(delete_file_number))
        else:
            message_to_emacs("Delete 1 file.")

    def handle_delete_unstage_files(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        for file_info in unstage_status:
            self.git_checkout_file([file_info["file"]])
            
        unstage_status = []
        
        select_item_type = ""
        select_item_index = -1
        if len(untrack_status) > 0:
            select_item_type = "untrack"
        else:
            select_item_type = "stage"
            
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))

    def handle_delete_stage_files(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        for file_info in stage_status:
            self.git_reset_file(file_info["file"])
            self.git_checkout_file([file_info["file"]])
        
        stage_status = []
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
        elif len(untrack_status) > 0:
            select_item_type = "untrack"
            
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
        
    def handle_commit_stage_files(self, message):
        tree = self.repo.index.write_tree()
        parent, ref = self.repo.resolve_refish(refish=self.repo.head.name)
        self.repo.create_commit(
            ref.name,
            self.repo.default_signature,
            self.repo.default_signature,
            message,
            tree,
            [parent.oid])
        
        self.fetch_unpush_info()
        self.fetch_log_info()

        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        stage_status = []
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
        elif len(untrack_status) > 0:
            select_item_type = "untrack"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
        
        message_to_emacs("Commit stage files with: {}".format(message))
    
    def handle_commit_all_files(self, message):
        self.repo.index.add_all()
        self.repo.index.write()
        
        tree = self.repo.index.write_tree()
        parent, ref = self.repo.resolve_refish(refish=self.repo.head.name)
        self.repo.create_commit(
            ref.name,
            self.repo.default_signature,
            self.repo.default_signature,
            message,
            tree,
            [parent.oid])
        
        self.fetch_unpush_info()
        self.fetch_log_info()
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps([]), json.dumps([]), json.dumps([]),
            "", -1))
        
        message_to_emacs("Commit stage files with: {}".format(message))

    def handle_commit_and_push(self, message):
        self.handle_commit_all_files(message)
        self.status_push()
        
    def handle_delete_untrack_file(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        untrack_file_index = untrack_status.index(self.delete_untrack_mark_file)
        untrack_status.remove(self.delete_untrack_mark_file)
        os.remove(os.path.join(self.repo_root, self.delete_untrack_mark_file["file"]))
        
        select_item_type = ""
        select_item_index = -1
        if len(untrack_status) > 0:
            select_item_type = "untrack"
            select_item_index = max(untrack_file_index - 1, 0)
        elif len(unstage_status) > 0:
            select_item_type = "unstage"
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
        
        message_to_emacs("Delete file {}".format(self.delete_untrack_mark_file["file"]))
    
    def handle_delete_unstage_file(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        self.git_checkout_file([self.delete_unstage_mark_file["file"]])
        
        unstage_file_index = unstage_status.index(self.delete_unstage_mark_file)
        unstage_status.remove(self.delete_unstage_mark_file)
        
        select_item_type = ""
        select_item_index = -1
        if len(unstage_status) > 0:
            select_item_type = "unstage"
            select_item_index = max(unstage_file_index - 1, 0)
        else:
            select_item_type = "stage"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))

    def handle_delete_stage_file(self):
        untrack_status = self.untrack_status
        unstage_status = self.unstage_status
        stage_status = self.stage_status
        
        self.git_reset_file(self.delete_stage_mark_file["file"])
        self.git_checkout_file([self.delete_stage_mark_file["file"]])
        
        stage_file_index = stage_status.index(self.delete_stage_mark_file)
        stage_status.remove(self.delete_stage_mark_file)
        
        select_item_type = ""
        select_item_index = -1
        if len(stage_status) > 0:
            select_item_type = "stage"
            select_item_index = max(stage_file_index - 1, 0)
        elif len(unstage_status) > 0:
            select_item_type = "unstage"
        elif len(unstage_status) > 0:
            select_item_type = "untrack"
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps(stage_status), json.dumps(unstage_status), json.dumps(untrack_status),
            select_item_type, select_item_index))
    
    @QtCore.pyqtSlot(list)
    def vue_update_stage_status(self, stage_status):
        self.stage_status = stage_status

    @QtCore.pyqtSlot(list)
    def vue_update_unstage_status(self, unstage_status):
        self.unstage_status = unstage_status

    @QtCore.pyqtSlot(list)
    def vue_update_untrack_status(self, untrack_status):
        self.untrack_status = untrack_status

    @QtCore.pyqtSlot(list)
    def vue_update_branch_status(self, branch_status):
        self.branch_status = branch_status
        
    @QtCore.pyqtSlot()
    def status_pull(self):
        message_to_emacs("Git pull...")
        thread = GitPullThread(self.repo_root)
        thread.pull_result.connect(message_to_emacs)
        self.fetch_pull_threads.append(thread)
        thread.start()

    @QtCore.pyqtSlot()
    def status_push(self):
        message_to_emacs("Git push...")
        thread = GitPushThread(self.repo_root)
        thread.push_result.connect(self.handle_status_push)
        self.git_push_threads.append(thread)
        thread.start()
        
    def handle_status_push(self, message):
        self.fetch_unpush_info()
        self.fetch_log_info()
        
        message_to_emacs(message)

    @QtCore.pyqtSlot()
    def status_checkout_all(self):
        self.send_input_message("Checkout all changes.", "checkout_all_files", "yes-or-no")
        
    def handle_checkout_all_files(self):
        self.git_checkout_file()
        
        self.buffer_widget.eval_js('''updateSelectInfo({}, {}, {}, \"{}\", {})'''.format(
            json.dumps([]), json.dumps([]), json.dumps([]),
            "", -1))
        
        message_to_emacs("Checkout all.")
        
    @QtCore.pyqtSlot()
    def log_search_forward(self):
        self.search_text_forward()

    @QtCore.pyqtSlot()
    def log_search_backward(self):
        self.search_text_backward()
        
    @QtCore.pyqtSlot()
    def branch_new(self):
        self.send_input_message("New branch: ", "new_branch")
        
    def handle_new_branch(self, branch_name):
        if branch_name in self.branch_status:
            message_to_emacs("Branch '{}' has exists.".format(branch_name))
        else:
            branch_list = self.branch_status
            branch_list.append(branch_name)
            
            self.repo.branches.local.create(branch_name, self.repo.revparse_single('HEAD'))
            self.update_branch_list(branch_list)
            
            message_to_emacs("Create branch '{}'.".format(branch_name))
            
    @QtCore.pyqtSlot(str)
    def branch_delete(self, branch_name):
        self.delete_branch_name = branch_name
        self.send_input_message("Delete branch '{}': ".format(branch_name), "delete_branch", "yes-or-no")
        
    def handle_delete_branch(self):
        branch_list = self.branch_status
        branch_list.remove(self.delete_branch_name)
        self.repo.branches.local.delete(self.delete_branch_name)
        
        self.update_branch_list(branch_list)
        
        message_to_emacs("Delete branch '{}'".format(self.delete_branch_name))
        
    def update_branch_list(self, branch_list):
        self.buffer_widget.eval_js('''updateBranchInfo(\"{}\", {})'''.format(self.repo.head.shorthand, json.dumps(branch_list)))
        
    @QtCore.pyqtSlot(str)
    def branch_switch(self, branch_name):
        # Tips
        # When switch the branch, the uncommitted changes will be copied over to the new branch. 
        # However you cannot pull/fetch/rebase, unless you stash or commit. 
        # Because Git will prevent that to stop from overwriting any uncommitted code.
        branch = self.repo.lookup_branch(branch_name)
        ref = self.repo.lookup_reference(branch.name)
        self.repo.checkout(ref)
        
        self.update_git_info()
        
        message_to_emacs("Switch to branch '{}'".format(branch_name))
        
class FetchLogThread(QThread):

    fetch_result = QtCore.pyqtSignal(list)

    def __init__(self, repo):
        QThread.__init__(self)

        self.repo = repo

    def run(self):
        git_log = []

        try:
            index = 0
            for commit in self.repo.walk(self.repo.head.target):
                git_log.append({
                    "id": str(commit.id),
                    "index": index,
                    "time": pretty_date(int(commit.commit_time)),
                    "author": commit.author.name,
                    "message": commit.message.splitlines()[0]
                })
                
                index += 1
        except KeyError:
            import traceback
            traceback.print_exc()

        self.fetch_result.emit(git_log)

class FetchSubmoduleThread(QThread):

    fetch_result = QtCore.pyqtSignal(list)

    def __init__(self, repo):
        QThread.__init__(self)

        self.repo = repo

    def run(self):
        self.fetch_result.emit(self.repo.listall_submodules())

class FetchBranchThread(QThread):

    fetch_result = QtCore.pyqtSignal(list)

    def __init__(self, repo):
        QThread.__init__(self)

        self.repo = repo

    def run(self):
        self.fetch_result.emit(self.repo.listall_branches())

class FetchStatusThread(QThread):

    fetch_result = QtCore.pyqtSignal(list, list, list)

    def __init__(self, repo):
        QThread.__init__(self)

        self.repo = repo

    def run(self):
        status = list(filter(lambda info: info[1] != GIT_STATUS_IGNORED, list(self.repo.status().items())))
        
        (stage_status, unstage_status, untrack_status) = self.parse_status(status)
        
        self.fetch_result.emit(stage_status, unstage_status, untrack_status)
        
    def parse_status(self, status):
        stage_status = []
        unstage_status = []
        untrack_status = []
        
        for info in status:
            if info[1] in GIT_STATUS_DICT:
                self.append_file_to_status_list(info, info[1], stage_status, unstage_status, untrack_status)
            else:
                first_dict = GIT_STATUS_DICT
                second_dict = GIT_STATUS_DICT
                
                for first_key in first_dict:
                    for second_key in second_dict:
                        if info[1] == first_key | second_key:
                            self.append_file_to_status_list(info, first_key, stage_status, unstage_status, untrack_status)
                            self.append_file_to_status_list(info, second_key, stage_status, unstage_status, untrack_status)
                            
        return (stage_status, unstage_status, untrack_status)                    
                            
    def append_file_to_status_list(self, info, type_key, stage_status, unstage_status, untrack_status):
        status = {
            "file": info[0],
            "type": GIT_STATUS_DICT[type_key]
        }
        
        if type_key in [GIT_STATUS_INDEX_MODIFIED, GIT_STATUS_INDEX_DELETED, GIT_STATUS_INDEX_RENAMED, GIT_STATUS_INDEX_TYPECHANGE]:
            if status not in stage_status:
                stage_status.append(status)
        elif type_key in [GIT_STATUS_WT_NEW]:
            if status not in untrack_status:
                untrack_status.append(status)
        else:
            if status not in unstage_status:
                unstage_status.append(status)
        
class GitPullThread(QThread):

    pull_result = QtCore.pyqtSignal(str)

    def __init__(self, repo_root):
        QThread.__init__(self)

        self.repo_root = repo_root
        
    def run(self):
        self.pull_result.emit(get_command_result("cd {}; git pull".format(self.repo_root)).strip())        

class GitPushThread(QThread):

    push_result = QtCore.pyqtSignal(str)

    def __init__(self, repo_root):
        QThread.__init__(self)

        self.repo_root = repo_root

    def run(self):
        result = get_command_result("cd {}; git push".format(self.repo_root)).strip()
        if result == "":
            result = "Git push successfully."
        self.push_result.emit(result)

class FetchUnpushThread(QThread):

    fetch_result = QtCore.pyqtSignal(str)

    def __init__(self, repo, repo_root):
        QThread.__init__(self)

        self.repo = repo
        self.repo_root = repo_root

    def run(self):
        result = get_command_result("cd {}; git log origin/{}..HEAD".format(self.repo_root, self.repo.head.shorthand))
        self.fetch_result.emit(result)         
        
