import datetime
import os
import contextlib, os
import time
from threading import Thread

@contextlib.contextmanager
def remember_cwd():
    curdir= os.getcwd()
    try: yield
    finally: os.chdir(curdir)

def launch_command(command):
    print(command)
    return os.popen(command).read()

def system_remote(command, remote, username, outptut_file=None):
    print(command)
    if outptut_file is None:
        os.system("ssh " + username + "@" + remote + " " + command)
    else:
        os.system("ssh " + username + "@" + remote + " '" + command + "' > " + outptut_file + " 2>&1")

def thread_system_remote(command, remote, username, outptut_file=None):
    t = Thread(target=system_remote, args=(command, remote, username, outptut_file))
    t.start()
    return t


class SVN:

    def __init__(self, url, dst):
        self.url = url
        self.dst = dst
        self.has_been_updated = False
        self.revision = ""

    def __str__(self):
        return "SVN: " + self.url + " -> " + self.dst

    def co(self):
        launch_command("svn co " + self.url + " " + self.dst)

    def up(self):
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

    def make_tgz(self):
        launch_command("tar czf " + self.dst + ".tar.gz " + self.dst)
    
    def duplicate(self, dst):
        launch_command("cp -r " + self.dst + " " + dst)
        new_svn = SVN(self.url, dst)
        new_svn.has_been_updated = self.has_been_updated
        return new_svn
    
    def duplicate_and_copy_patch(self, dst, patch):
        new_svn = self.duplicate(dst)
        launch_command("cp -r " + patch + "/* " + dst)
        return new_svn


class OpenBuildService:

    def __init__(self, url):
        self.url = url
        self.dst = url

    def __str__(self):
        return "OBS: " + self.url + " -> " + self.dst

    def co(self):
        launch_command("osc co " + self.url)

    def up(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc up")
    
    def addall(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc add *")

    def update_src(self, src_tgz_path, dst_tgz_path, dst_dsc_path):
        #os.chdir(self.dst)
        launch_command("cp " + src_tgz_path + " " + dst_tgz_path)
        self.update_dsc(dst_dsc_path, os.path.basename(dst_tgz_path))

    def commit(self):
        with remember_cwd():
            os.chdir(self.dst)
            launch_command("osc ci -m \"Update to latest version\"")

    def update_dsc(self, dst_dsc_path, file_to_update):

        with remember_cwd():
            # split dst_dsc_path into path and filename
            path = os.path.dirname(dst_dsc_path)
            filename = os.path.basename(dst_dsc_path)
            os.chdir(path)

            # compute checksums
            checksums_sha1 = launch_command("sha1sum " + file_to_update)
            checksums_sha1 = checksums_sha1.split(" ")[0]
            checksums_sha256 = launch_command("sha256sum " + file_to_update)
            checksums_sha256 = checksums_sha256.split(" ")[0]
            md5sum = launch_command("md5sum " + file_to_update)
            md5sum = md5sum.split(" ")[0]
            file_size = launch_command("stat -c %s " + file_to_update)
            file_size = file_size.replace("\n", "")

            # update dsc file
            with open(filename, "r") as f:
                lines = f.readlines()
            with open(filename, "w") as f:
                currentState = "none"
                for line in lines:
                    if line.startswith("Checksums-Sha1:"):
                        currentState = "sha1"
                        f.write(line)
                        continue
                    elif line.startswith("Checksums-Sha256:"):
                        currentState = "sha256"
                        f.write(line)
                        continue
                    elif line.startswith("Files:"):
                        currentState = "files"
                        f.write(line)
                        continue
                    elif line.startswith(" "):
                        if currentState == "sha1" and file_to_update in line:
                            print("sha1")
                            f.write(" " + checksums_sha1 + " " + file_size + " " + file_to_update + "\n")
                            continue
                        elif currentState == "sha256" and file_to_update in line:
                            f.write(" " + checksums_sha256 + " " + file_size + " " + file_to_update + "\n")
                            continue
                        elif currentState == "files" and file_to_update in line:
                            f.write(" " + md5sum + " " + file_size + " " + file_to_update + "\n")
                            continue
                    f.write(line)


def highestVersion(version1, version2):
    print("Comparing " + version1 + " and " + version2)
    
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
    
    # compare each integer
    for i in range(len(version1_int)):
        if version1_int[i] > version2_int[i]:
            return version1
        elif version1_int[i] < version2_int[i]:
            return version2
    # if we reach this point, version1 == version2
    return version1

def parseTexmacsVersion(folder, oldversion=""):
    lines = []
    with remember_cwd():
        os.chdir(folder)
        # open TeXmacs/doc/about/changes/change-log.en.tm
        with open("TeXmacs/doc/about/changes/change-log.en.tm", "r", encoding='latin-1') as f:
            lines = f.readlines()
    # find the line with the version
    # some lines may contains <TeXmacs|2.1.2>
    # we want to extract 2.1.2
    version = oldversion
    for line in lines:
        if "<TeXmacs|" in line:
            index = line.find("<TeXmacs|")
            index2 = line.find(">", index)
            version = highestVersion(version, line[index+9:index2])
    return version

def replaceRecursivelyInFileName(folder, old, new):
    print("Recursively replacing " + old + " with " + new + " in " + folder)
    for filename in os.listdir(folder):
        filename = folder + "/" + filename
        if old in filename:
            print("Renaming " + filename + " to " + filename.replace(old, new))
            os.rename(filename, filename.replace(old, new))
        if os.path.isdir(filename):
            replaceRecursivelyInFileName(filename, old, new)

def replaceRecursivelyInFileContentWithExtension(folder, old, new, extension):
    print("Recursively replacing " + old + " with " + new + " in " + folder + " with extension " + extension)
    for filename in os.listdir(folder):
        filename = folder + "/" + filename
        if os.path.isdir(filename):
            replaceRecursivelyInFileContentWithExtension(filename, old, new, extension)
        elif filename.endswith(extension):
            print("Replacing in " + filename)
            with open(filename, "r") as f:
                lines = f.readlines()
            with open(filename, "w") as f:
                for line in lines:
                    f.write(line.replace(old, new))

def recursivelyMakeAllDiffsEmpy(folder):
    print("Recursively making all diffs empty in " + folder)
    for filename in os.listdir(folder):
        filename = folder + "/" + filename
        if os.path.isdir(filename):
            recursivelyMakeAllDiffsEmpy(filename)
        elif filename.endswith(".diff"):
            print("Making " + filename + " empty")
            with open(filename, "w") as f:
                f.write("")

def main():
    os.system("rm -rf texmacs")
    os.system("rm -rf texmacs-patched*")

    texmacs_svn = SVN("svn://svn.savannah.gnu.org/texmacs/trunk/src", "texmacs")
    texmacs_svn.co()

    version = ""
    if os.path.isfile("version"):
        with open("version", "r") as f:
            version = f.read()
    else:
        with open("version", "w") as f:
            version = parseTexmacsVersion(texmacs_svn.dst)
            f.write(version)

    first_time = True

    while True:
        texmacs_svn.up()
        if texmacs_svn.has_been_updated or first_time:
            print("New version available")

            os.system("rm -rf texmacs-patched*")
            texmacs_svn_patched = texmacs_svn.duplicate_and_copy_patch("texmacs-patched", "/home/magix/pulsar/autobuild/patchubu16static")

            oldversion = version
            newversion = parseTexmacsVersion(texmacs_svn_patched.dst, version)

            os.system("rm -rf /home/magix/DEV/texmacs")
            os.system("rm -rf /home/magix/DEV/distr/*")
            os.system("cp -r texmacs-patched /home/magix/DEV/texmacs")
            with remember_cwd():
                os.chdir("/home/magix/DEV/texmacs")
                os.system("./configure --with-tmrepo=/home/magix/DEV/SDK >/home/magix/pulsar/ubu16-tmstatic.log 2>&1")
                os.system("make >>/home/magix/pulsar/ubu16-tmstatic.log 2>&1")
                os.system("make PACKAGE >>/home/magix/pulsar/ubu16-tmstatic.log 2>&1")

            version = newversion
            with open("version", "w") as f:
                f.write(version)

            print("New version updated")
        else:
            print("No new version available")
        first_time = False
        texmacs_svn.has_been_updated = False
        print("Sleeping for 5 minutes")
        time.sleep(300)



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
