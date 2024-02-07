import os
import contextlib
from threading import Thread
import subprocess

from autobuild.utils import launch_command, remember_cwd

class OpenBuildService:

    def __init__(self, url, dst):
        self.url = url
        self.dst = dst

    def __str__(self):
        return "OBS: " + self.url + " -> " + self.dst

    def co(self):
        launch_command("osc co " + self.url + " -o " + self.dst)

    def up(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc up")
    
    def addall(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc add *")
            launch_command("osc add */*")
    
    def add(self, filename):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc add " + filename)

    def update_src(self, src_tgz_path, dst_tgz_path, dst_dsc_path):
        #os.chdir(self.dst)
        launch_command("cp " + src_tgz_path + " " + dst_tgz_path)
        self.update_dsc(dst_dsc_path, os.path.basename(dst_tgz_path))

    def commit(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc ci -m \"Update to latest version (autobuild script by liza)\"")
    
    def get_status(self, logger = None):
        with remember_cwd():
            os.chdir(self.dst)
            return launch_command("osc status", logger)

    def get_binaries_list(self, logger = None):
        with remember_cwd():
            os.chdir(self.dst)
            return launch_command("osc getbinaries help", logger)

    def download_binaries(self, pkg, dest, logger = None):
        # transform dest from relative (if relative) to absolute
        dest = os.path.abspath(dest)
        binaries_list = self.get_binaries_list(logger)
        for line in binaries_list.splitlines():
            if "Invalid" in line:
                continue
            try:
                for i in range(5):
                    line = line.replace("  ", " ")
                dirname = os.path.join(dest, line.replace(" ", "_"))
                print(f"Downloading binaries for {line} into {dirname}")
                with remember_cwd():
                    os.chdir(self.dst)
                    os.chdir(pkg)
                    # launch_command(f"osc getbinaries {line} -d {dirname}", logger)
                    print(f"osc getbinaries {line} -d {dirname}")
                    os.system(f"osc getbinaries {line} -d {dirname}")
                    if len(os.listdir(dirname)) < 3:
                        launch_command(f"rm -rf {dirname}", logger)
            except Exception as e:
                print(f"Error: {e}")
                continue
    
    def get_results(self, logger = None):
        with remember_cwd():
            os.chdir(self.dst)
            return launch_command("osc results", logger)
    
    def is_building(self):
        results = self.get_results()
        return "(building)" in results or "(finished)" in results or "(dispatching)" in results

