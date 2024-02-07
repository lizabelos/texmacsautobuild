from abc import ABC, abstractmethod
import os
import time
from threading import Thread
import logging
import paramiko
import re

from autobuild.texmacsrepo import TexmacsSVN, TexmacsOBS, get_global_texmacs_svn, get_global_texmacs_obs
from autobuild.utils import system_remote, launch_command
from autobuild.machine import Machine, MachineLock
from autobuild.ssh import SSHHelper

class TexmacsMachine(SSHHelper):
    
        def __init__(self, name, ip, username, machine):
            super().__init__(ip, username)

            self.name = name
            self.machine = machine
            self.command_queue = []
            
            self.logger = logging.getLogger("TexmacsMachine_" + self.name)

            # remove .log
            os.system("mkdir -p logs")
            if os.path.exists("logs/build_" + self.name + ".log"):
                os.remove("logs/build_" + self.name + ".log")

            # log into a file
            self.logger.setLevel(logging.DEBUG)
            self.fh = logging.FileHandler("logs/build_" + self.name + ".log")
            self.fh.setLevel(logging.DEBUG)
            self.logger.addHandler(self.fh)

            self.thread_continue = True
            self.thread = Thread(target=self._thread_main)
            self.thread.start()
        
        def _thread_main(self):
            while self.thread_continue:
                if len(self.command_queue) > 0:
                    command = self.command_queue.pop(0)
                    command()
                else:
                    time.sleep(1)
        
        def join(self):
            self.thread_continue = False
            self.thread.join()
        
        def wait(self):
            while len(self.command_queue) > 0:
                time.sleep(1)
        
        def set_logger_prefix(self, prefix):
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - ' + prefix + ' - %(message)s')
            self.fh.setFormatter(formatter)
        
        def log_error(self, prefix, message):
            self.set_logger_prefix(prefix)
            self.logger.error(message)

        def log_warning(self, prefix, message):
            self.set_logger_prefix(prefix)
            self.logger.warning(message)

        def log_info(self, prefix, message):
            self.set_logger_prefix(prefix)
            self.logger.info(message)

        def log_debug(self, prefix, message):
            self.set_logger_prefix(prefix)
            self.logger.debug(message)
        

        def system(self, command):
            current_dir = os.getcwd()
            self.log_debug("pulsar", "Launching command " + command + " in " + current_dir)
            command = command.replace("\\", "\\\\")
            text = launch_command(command, self.logger)
            return text

        @abstractmethod
        def duplicate_and_copy_patch(self):
            raise NotImplementedError
        
        @abstractmethod
        def copy_src_to_remote(self):
            raise NotImplementedError
        
        @abstractmethod
        def build_package(self):
            raise NotImplementedError
        
        @abstractmethod
        def copy_packages_from_remote(self):
            raise NotImplementedError

        @abstractmethod
        def test_package(self):
            raise NotImplementedError

        def _build(self):
            self.log_info("", "Waiting for machine " + self.name + " to be available")
            with MachineLock(self.machine, self.ip):
                self.log_info("", "Building on " + self.name)
                self.duplicate_and_copy_patch()

                self.log_info("", "Copying src to remote on " + self.name)
                self.copy_src_to_remote()
                
                self.log_info("", "Building on " + self.name)
                self.build_package()
                
                self.log_info("", "Copying packages from remote on " + self.name)
                self.copy_packages_from_remote()
                            
                self.log_info("", "Done building on " + self.name)

        def _test(self):
            self.log_info("", "Waiting for machine " + self.name + " to be available")
            with MachineLock(self.machine, self.ip):
                self.log_info("", "Testing on " + self.name)
                self.test_package()
                self.log_info("", "Done testing on " + self.name)
        
        def build(self):
            self.command_queue.append(lambda: self._build())
        
        def test(self):
            self.command_queue.append(lambda: self._test())


