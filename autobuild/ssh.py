from abc import ABC, abstractmethod
import os
import time
from threading import Thread
import logging
import paramiko
import re

class SSHHelper(ABC):
        
        def __init__(self, ip, username):
            self.ip = ip
            self.username = username
            self.default_shell = ""
            self.default_rsync = ""

            self.lines = []
            self.current_line = ""
            self.skip_empty_lines = False
        
        def log_error(self, prefix, message):
            print("ERROR: " + prefix + " - " + message)

        def log_warning(self, prefix, message):
            print("WARNING: " + prefix + " - " + message)

        def log_info(self, prefix, message):
            print("INFO: " + prefix + " - " + message)

        def log_debug(self, prefix, message):
            print("DEBUG: " + prefix + " - " + message)
        
        def set_default_rsync(self, rsync):
            self.default_rsync = rsync
        
        def rsync(self, src, dst):
            rsync_path_arg = ""
            if self.default_rsync != "":
                rsync_path_arg = "--rsync-path=" + self.default_rsync
            self.system("rsync -avz " + rsync_path_arg + " " + src + " " + dst)
        
        def copy_host_to_remote(self, src, dst):
            self.log_debug(self.ip, "Copying pulsar:" + src + " to " + self.ip + ":" + dst)
            # self.system("rsync -avz -e ssh " + src + " " + self.username + "@" + self.ip + ":" + dst)
            self.rsync(src, self.username + "@" + self.ip + ":" + dst)
        
        def copy_remote_to_host(self, src, dst):
            self.log_debug(self.ip, "Copying " + self.ip + ":" + src + " to pulsar:" + dst)
            self.rsync(self.username + "@" + self.ip + ":" + src, dst)

        def set_default_shell(self, shell):
            self.default_shell = shell
        
        def display_channel_text(self, line):
            if line.endswith("\r"):
                return
            if line == "":
                if self.skip_empty_lines:
                    return
                self.skip_empty_lines = True
            else:
                self.skip_empty_lines = False
            self.log_debug(self.ip, line)

        def process_channel_text(self, line):
            self.current_line += line
            if "\n" in line:
                self.current_line_split = self.current_line.split("\n")
                for i in range(len(self.current_line_split) - 1):
                    self.lines.append(self.current_line_split[i])
                    self.display_channel_text(self.current_line_split[i])
                self.current_line = self.current_line_split[-1]

        def read_channel_until(self, end = None, commandend = None, timeout = None):
            self.lines = []
            self.current_line = ""
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            start = time.time()
            while True:
                if not self.channel.recv_ready():
                    if timeout is not None:
                        if time.time() - start > timeout:
                            break
                    time.sleep(1)
                    continue
                start = time.time()
                line = self.channel.recv(1024)
                line = line.decode("utf-8")
                line = line.replace("\r\n", "\n")
                line = ansi_escape.sub('', line)
                    
                if commandend is not None:
                    line = line.replace(commandend, "---END---")
                self.process_channel_text(line)
                if end is not None:
                    if end in line:
                        break
            
            self.display_channel_text(self.current_line)
            text = "\n".join(self.lines)
            return text

        def launch_ssh_command(self, command, reset_connection = True):
            if reset_connection:
                self.log_debug(self.ip, "Connecting to " + self.ip)
                try:
                    self.ssh = paramiko.SSHClient()
                    self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.ssh.connect(self.ip, username=self.username, disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']})
                except Exception as e:
                    self.log_error(self.ip, "Failed to connect to " + self.ip + " with default algorithms, retrying with no disabled algorithms")
                    self.ssh = paramiko.SSHClient()
                    self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.ssh.connect(self.ip, username=self.username, disabled_algorithms={'pubkeys': []})
                self.log_debug(self.ip, "Connected to " + self.ip + "\n\n\n")

                self.channel = self.ssh.invoke_shell()
                self.read_channel_until(timeout = 10)
                self.channel.send("echo '+++END+++'\r\n")
                self.read_channel_until("+++END+++", "echo '+++END+++'")

                if self.default_shell != "":
                    self.log_debug(self.ip, "Launching default shell " + self.default_shell)
                    self.channel.send(self.default_shell.replace("\\", "\\\\") + "\n")
                    self.channel.send("echo '+++END+++'\r\n")
                    self.read_channel_until("+++END+++", "echo '+++END+++'")

            self.log_debug(self.ip, "Launching command " + command)
            self.channel.send(command.replace("\\", "\\\\") + "\r\n")
            self.channel.send("echo '+++END+++'\r\n")
            text = self.read_channel_until("+++END+++", "echo '+++END+++'")

            self.log_debug(self.ip, "Done launching command " + command + "\n\n\n")
            return text

                
        
        def launch_ssh_commands(self, commands):
            return "\n".join([self.launch_ssh_command(commands[i], i == 0) for i in range(len(commands))])