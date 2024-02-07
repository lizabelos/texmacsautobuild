import os
import contextlib
from threading import Thread
import subprocess
import paramiko

@contextlib.contextmanager
def remember_cwd():
    curdir= os.getcwd()
    try: yield
    finally: os.chdir(curdir)

def launch_command(command, logger = None):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    outputs = []
    while True:
        line = p.stdout.readline()
        if not line:
            break
        line = line.rstrip()
        line = line.decode("utf-8")
        if logger is not None:
            logger.debug(line)
        outputs.append(line)
    return "\n".join(outputs)

def system_remote(command, remote, username, logger = None):
    return launch_command("ssh " + username + "@" + remote + " " + command, logger)
