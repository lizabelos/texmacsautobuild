import os
import re
from threading import Thread, Lock

from autobuild.utils import system_remote, remember_cwd
from autobuild.svn import SVN
from autobuild.openbuildservice import OpenBuildService

class TexmacsSVN(SVN):

    def __init__(self, dst):
        super().__init__("svn://svn.savannah.gnu.org/texmacs/trunk/src", dst)
        self.version = ""

    def get_version(self):
        return self.version
    
    def co(self):
        super().co()
        self.version = self._parseTexmacsVersion()
    
    def up(self):
        super().up()
        self.version = self._parseTexmacsVersion()
    
    def highestVersion(self, version1, version2):
        version1_int = []
        version2_int = []
        # split version1 and version2 into list of integers
        try:
            version1_split = version1.split(".")
            version1_int = [int(x) for x in version1_split]
        except:
            return version2

        try:
            version2_split = version2.split(".")
            version2_int = [int(x) for x in version2_split]
        except:
            return version1
        
        version1_int.append(0)
        version1_int.append(0)
        version2_int.append(0)
        version2_int.append(0)
    
        # compare each integer
        for i in range(len(version1_int) - 2):
            if version1_int[i] > version2_int[i]:
                return version1
            elif version1_int[i] < version2_int[i]:
                return version2
        # if we reach this point, version1 == version2
        return version1

    def _parseTexmacsVersion(self):
        with self.mutex:
            file_content = ""
            with remember_cwd():
                os.chdir(self.dst)
                # open TeXmacs/doc/about/changes/change-log.en.tm
                with open("TeXmacs/doc/about/changes/change-log.en.tm", "r", encoding='latin-1') as f:
                    file_content = f.read()
            # some lines may contains (2.1.2) or (2.1)
            # we want to extract 2.1.2
            expression = re.compile(r"\((\d+\.\d+(\.\d+)?)\)")
            matches = expression.findall(file_content)
            version = "0.0.0"
            for match in matches:
                version = self.highestVersion(version, match[0])
            print("TeXmacs version: " + version)
            return version

class TexmacsOBS(OpenBuildService):

    def __init__(self, dst):
        super().__init__("home:jmnotin:TeXmacs", dst)

texmacs_svn = None
texmacs_svn_mutex = Lock()
def get_global_texmacs_svn():
    global texmacs_svn_mutex
    with texmacs_svn_mutex:
        global texmacs_svn
        if texmacs_svn is None:
            os.system("mkdir -p repos")
            os.system("rm -rf repos/texmacs")
            texmacs_svn = TexmacsSVN("repos/texmacs")
            texmacs_svn.co()
        return texmacs_svn

texmacs_obs = None
texmacs_obs_mutex = Lock()

def get_global_texmacs_obs():
    global texmacs_obs_mutex
    with texmacs_obs_mutex:
        global texmacs_obs
        if texmacs_obs is None:
            os.system("mkdir -p repos")
            os.system("rm -rf repos/home:jmnotin:TeXmacs")
            texmacs_obs = TexmacsOBS("repos/home:jmnotin:TeXmacs")
            texmacs_obs.co()
        return texmacs_obs

