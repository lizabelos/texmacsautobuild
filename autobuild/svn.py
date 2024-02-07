import os
from threading import Thread, Lock

from autobuild.utils import launch_command, remember_cwd

class SVN:

    def __init__(self, url, dst):
        self.url = url
        self.dst = dst
        self.has_been_updated = False
        self.revision = ""
        self.mutex = Lock()

    def __str__(self):
        with self.mutex:
            return "SVN: " + self.url + " -> " + self.dst

    def co(self):
        with self.mutex:
            launch_command("svn co " + self.url + " " + self.dst)

    def up(self):
        with self.mutex:
            with remember_cwd():
                os.chdir(self.dst)
                cmd = launch_command("svn up")
                if "At revision" in cmd:
                    index = cmd.find("At revision")
                    index2 = cmd.find(".", index)
                    new_revision = cmd[index+12:index2]
                    if new_revision != self.revision:
                        print("Old revision: " + self.revision)
                        print("New revision: " + new_revision)
                        self.has_been_updated = self.revision != ""
                        self.revision = new_revision
                    else:
                        self.has_been_updated = False
                else:
                    self.has_been_updated = False

    def make_tgz(self, name):
        with self.mutex:
            # we want to create a tar.gz named name.tar.gz with a folder inside named name containing the content of self.dst in the current directory
            if os.path.isdir(name):
                launch_command("rm -rf " + name)
            os.rename(self.dst, name)
            launch_command("tar -czf " + name + ".tar.gz " + name)
            os.rename(name, self.dst)
    
    def duplicate(self, dst):
        with self.mutex:
            launch_command("cp -r " + self.dst + " " + dst)
            new_svn = SVN(self.url, dst)
            new_svn.has_been_updated = self.has_been_updated
            return new_svn
    
    def duplicate_and_copy_patch(self, dst, patch):
        new_svn = self.duplicate(dst)
        launch_command("cp -r " + patch + "/* " + dst)
        return new_svn