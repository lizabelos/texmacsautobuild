from abc import ABC, abstractmethod
import os
import time
import subprocess
from threading import Thread
import logging
import paramiko

from autobuild.machine import Machine, MachineLocalProxmox
from autobuild.texmacsmachine import TexmacsMachine
from autobuild.texmacsrepo import TexmacsSVN, TexmacsOBS, get_global_texmacs_svn, get_global_texmacs_obs
from autobuild.utils import system_remote, launch_command

class TexmacsMachineMac(TexmacsMachine):

    def __init__(self, name, ip, username, machine, tmrepo="/Users/*username*/DEV/SDK"):
        super().__init__(name, ip, username, machine)
        self.tmrepo = tmrepo.replace("*username*", self.username)
    
    def duplicate_and_copy_patch(self):
        self.system("mkdir -p patched")
        self.patched_dir = "patched/" + self.name
        svn = get_global_texmacs_svn()
        self.system("rm -rf " + self.patched_dir)
        svn.duplicate_and_copy_patch(self.patched_dir, "patchs/patchmac")
    
    def copy_src_to_remote(self):
        self.launch_ssh_command("rm -rf /Users/" + self.username + "/DEV/texmacs")
        self.copy_host_to_remote(self.patched_dir + "/*", "/Users/" + self.username + "/DEV/texmacs")
    
    def build_package(self):
        commands = [
            "rm -rf ~/.TeXmacs/",
            "source TMenvOPT",
            "cd DEV",
            "rm -rf distr/*",
            "cd texmacs",
            "make distclean",
            "PKG_CONFIG_PATH=/Users/" + self.username + "/DEV/SDK/lib/pkgconfig ./configure --with-tmrepo=" + self.tmrepo,
            "make",
            "make PACKAGE",
        ]
        self.launch_ssh_commands(commands)
    
    def copy_packages_from_remote(self):
        self.system("mkdir -p distr")
        self.system("mkdir -p distr/" + self.name)
        self.copy_remote_to_host("/Users/" + self.username + "/DEV/distr/*", "distr/" + self.name)

    def test_package(self):
        commands = [
            "cd DEV",
            "rm -rf test",
            "mkdir test",
            "cp distr/macos/*.dmg test/texmacs.dmg",
            "cd test",
            "export TEXMACS_VOLUME=/Volumes/TeXmacs",
            "hdiutil attach texmacs.dmg",
            '$TEXMACS_VOLUME/TeXmacs.app/Contents/MacOS/TeXmacs --headless -x \'(begin (load-help-book "main/man-user-manual") (wrapped-print-to-file "$PWD/test.pdf"))\' -q',
            "hdiutil detach $TEXMACS_VOLUME"
        ]
        self.launch_ssh_commands(commands)
        self.copy_remote_to_host("/Users/" + self.username + "/DEV/test/test.pdf", "distr/" + self.name + "/test.pdf")



class TexmacsMachineWin(TexmacsMachine):

    def __init__(self, name, ip, username, machine):
        super().__init__(name, ip, username, machine)
        self.set_default_shell("C:\\msys64\\niv2\\msys2_shell.cmd -mingw32 -defterm -no-start -here")
        self.set_default_rsync("C:\\msys64\\usr\\bin\\rsync.exe")
    
    def duplicate_and_copy_patch(self):
        svn = get_global_texmacs_svn()
        os.system("mkdir -p patched")
        self.patched_dir = "patched/" + self.name
        self.system("rm -rf " + self.patched_dir)
        svn.duplicate_and_copy_patch(self.patched_dir, "patchs/patchwin")
    
    def copy_src_to_remote(self):
        commands = [
            "cd /c/msys64/niv2/home/magix",
            "rm -rf texmacs",
        ]
        self.launch_ssh_commands(commands)
        self.copy_host_to_remote(self.patched_dir + "/*", "/c/msys64/niv2/home/magix/texmacs")

    def build_package(self):
        commands = [
            "cd /c/msys64/niv2/home/magix",
            'export PATH="/c/Program Files (x86)/GnuWin32/bin":$PATH',
            "export with_sparkle=/WinSparkle-0.6.0",
            "rm -rf distr",
            "cd texmacs",
            "./configure --with-tmrepo=/SDK --with-qt=/Qt",
            "make",
            "make PACKAGE",
        ]
        self.launch_ssh_commands(commands)
            
    def copy_packages_from_remote(self):
        self.system("mkdir -p distr")
        self.system("rm -rf distr/" + self.name)
        self.system("mkdir -p distr/" + self.name)
        self.copy_remote_to_host("/c/msys64/niv2/home/magix/distr/*", "distr/" + self.name)

    def test_package(self):
        commands = [
            "cd /c/msys64/niv2/home/magix",
            "rm -rf test",
            "mkdir test",
            "cd distr/TeXmacs-Windows",
            "export TEXMACS_PATH=`pwd -W`",
            "export PATH=/SDK/bin:/WinSparkle-0.6.0/Release:$PWD/bin:$PATH",
            './bin/texmacs.exe --headless -x \'(begin (load-help-book "main/man-user-manual") (wrapped-print-to-file "C:/msys64/niv2/home/magix/test/test.pdf"))\' -q'
        ]
        self.launch_ssh_commands(commands)
        self.copy_remote_to_host("/niv2/home/magix/test/test.pdf", "distr/" + self.name + "/test.pdf")


class TexmacsMachineOBS(TexmacsMachine):

    def __init__(self):
        super().__init__("obs", "obs", "obs", Machine("obs"))
    
    def duplicate_and_copy_patch(self):
        # Create patched .tar.gz
        svn = get_global_texmacs_svn()
        os.system("mkdir -p patched")
        self.patched_dir = "patched/" + self.name
        self.system("rm -rf " + self.patched_dir)
        patched = svn.duplicate_and_copy_patch(self.patched_dir, "patchs/patchobs")
        self.filename = "TeXmacs-" + svn.version + ".tar.gz"
        patched.make_tgz("TeXmacs-" + svn.version)

        # Compute checksums
        checksums_sha1 = self.system("sha1sum " + self.filename)
        checksums_sha1 = checksums_sha1.split(" ")[0]
        checksums_sha256 = self.system("sha256sum " + self.filename)
        checksums_sha256 = checksums_sha256.split(" ")[0]
        md5sum = self.system("md5sum " + self.filename)
        md5sum = md5sum.split(" ")[0]
        file_size = self.system("stat -c %s " + self.filename)
        file_size = file_size.replace("\n", "")

        # Remove old .tar.gz
        obs = get_global_texmacs_obs()
        self.system("rm -rf " + obs.dst + "/TeXmac*/*.tar.gz")

        # List recursively all files in obs.dst-template. Copy them to obs.dst and replace existing files
        self.system("cp -R " + obs.dst + "-template" + "/* " + obs.dst)

        # Walk through obs.dst and replace file named by __TGZ__ with the new .tar.gz
        for root, dirs, files in os.walk(obs.dst):
            for file in files:
                if file == "__TGZ__":
                    self.system("cp " + self.filename + " " + root + "/" + self.filename)
                    self.system("rm -rf " + root + "/__TGZ__")
        
        # Walk through obs.dst and replace file content with __VERSION__ by the new version
        for root, dirs, files in os.walk(obs.dst):
            for file in files:
                if file.endswith(".tar.tz"):
                    continue
                self.system("sed -i 's/__VERSION__/" + svn.version + "/g' " + root + "/" + file)
                self.system("sed -i 's/__SHA1__/" + checksums_sha1 + "/g' " + root + "/" + file)
                self.system("sed -i 's/__SHA256__/" + checksums_sha256 + "/g' " + root + "/" + file)
                self.system("sed -i 's/__MD5__/" + md5sum + "/g' " + root + "/" + file)
                self.system("sed -i 's/__SIZE__/" + file_size + "/g' " + root + "/" + file)
        
        # Remove generated .tar.gz
        self.system("rm -rf " + self.filename)
            
    def copy_src_to_remote(self):
        texmacs_obs = get_global_texmacs_obs()
        texmacs_obs.addall()
    
    def build_package(self):
        texmacs_obs = get_global_texmacs_obs()
        texmacs_obs.commit()
        self.log_debug("", "Waiting for 120 secondes for the build to finish")
        time.sleep(120)
        while texmacs_obs.is_building():
            self.log_debug("", "Still building. Waiting for 60 seconds")
            time.sleep(60)
        self.log_info("", texmacs_obs.get_results())
    
    def copy_packages_from_remote(self):
        self.system("mkdir -p distr")
        self.system("rm -rf distr/" + self.name)
        obs = get_global_texmacs_obs()
        obs.download_binaries("TeXmacs-QT5", "distr", self.logger)

    def test_package(self):
        pass


class TexmacsMachineLinux(TexmacsMachine):

    def __init__(self, name, ip, username, machine):
        super().__init__(name, ip, username, machine)
    
    def duplicate_and_copy_patch(self):
        self.system("mkdir -p patched")
        self.patched_dir = "patched/" + self.name
        svn = get_global_texmacs_svn()
        self.system("rm -rf " + self.patched_dir)
        svn.duplicate_and_copy_patch(self.patched_dir, "patchs/patchubu16static")
    
    def copy_src_to_remote(self):
        self.launch_ssh_command("rm -rf /home/" + self.username + "/DEV/texmacs")
        self.copy_host_to_remote(self.patched_dir + "/*", "/home/" + self.username + "/DEV/texmacs")
    
    def build_package(self):
        commands = [
            "cd DEV",
            "rm -rf distr/*",
            "cd texmacs",
            "./configure --with-tmrepo=/home/magix/DEV/SDK",
            "make",
            "make PACKAGE",
        ]
        self.launch_ssh_commands(commands)
    
    def copy_packages_from_remote(self):
        self.system("mkdir -p distr")
        self.system("mkdir -p distr/" + self.name)
        self.copy_remote_to_host("/home/" + self.username + "/DEV/distr/*", "distr/" + self.name)

    def test_package(self):
        commands = [
            "rm -rf ~/.TeXmacs/",
            "cd DEV",
            "rm -rf test",
            "mkdir test",
            "cd distr/generic",
            "tar -xzf TeXmacs-*.tar.gz",
            "cd TeXmacs-*",
            "cd TeXmacs",
            "export TEXMACS_PATH=`pwd`",
            './bin/texmacs.bin --headless -x \'(begin (load-help-book "main/man-user-manual") (wrapped-print-to-file "/home/magix/DEV/test/test.pdf"))\' -q'
        ]
        self.launch_ssh_commands(commands)
        self.copy_remote_to_host("/home/" + self.username + "/DEV/test/test.pdf", "distr/" + self.name + "/test.pdf")



class TexmacsMachineAndroid(TexmacsMachine):

    def __init__(self, name, ip, username, machine):
        super().__init__(name, ip, username, machine)

    def duplicate_and_copy_patch(self):
        self.system("mkdir -p patched")
        self.patched_dir = "patched/" + self.name
        svn = get_global_texmacs_svn()
        self.system("rm -rf " + self.patched_dir)
        svn.duplicate_and_copy_patch(self.patched_dir, "patchs/patchandroid")

    def copy_src_to_remote(self):
        self.launch_ssh_command("rm -rf /home/" + self.username + "/DEV/texmacs/src")
        self.copy_host_to_remote(self.patched_dir + "/*", "/home/" + self.username + "/DEV/texmacs/src")

    def build_package(self):
        commands = [
            "cd texmacs-builder",
            "source set-devel-path",
            "make texmacs",
        ]
        self.launch_ssh_commands(commands)

    def copy_packages_from_remote(self):
        self.system("mkdir -p distr")
        self.system("rm -rf distr/" + self.name)
        self.system("mkdir -p distr/" + self.name)
        # copy texmacs-builder/texmacs/distr
        self.copy_remote_to_host("/home/" + self.username + "/texmacs-builder/texmacs/distr/*", "distr/" + self.name)
    
    def test_package(self):
        # todo
        pass


def create_patch(local_dir, ip, username, remote_dir, patch_dir):
    num_changes = 0

    # copy the remote directory to the temporary directory
    if not os.path.exists("tmp"):
        os.system("mkdir tmp")
        os.system("rsync -avz " + username + "@" + ip + ":" + remote_dir + "/*" + " tmp")

    # create the patch directory
    # os.system("mkdir -p " + patch_dir)

    # each file that is new or modified is copied to the patch directory
    for root, dirs, files in os.walk("tmp"):
        root_purged = root.replace("tmp", "")
        if root_purged.startswith("/"):
            root_purged = root_purged[1:]
        for file in files:
            local_file = local_dir + "/" + root_purged + "/" + file
            remote_file = root + "/" + file
            patched_file = patch_dir + "/" + root_purged + "/" + file

            if "/." in root_purged or file.startswith("."):
                continue
            if "~" in file or "~" in root_purged:
                continue
            if file == "configure":
                continue
            if file.endswith(".log"):
                continue
            if "ice-9" in root_purged:
                continue
            if "TeXmacs" in root_purged and "TeXmacs/progs" not in root_purged:
                continue
            if not os.path.exists(local_file):
                remote_content = open(remote_file, "r", encoding="latin-1").read()
                remote_content = ''.join(e.lower() for e in remote_content if e.isalnum())
                if "android" not in file and "Android" not in file and "ANDROID" not in file and "java" not in file and "JNI" not in file and "qt" not in file and "Qt" not in file:
                    if "android" not in remote_content or "qt" not in remote_content:
                        continue
                os.system("mkdir -p " + patch_dir + "/" + root_purged)
                os.system("cp " + remote_file + " " + patched_file)
                num_changes += 1
                continue

            local_content = open(local_file, "r", encoding="latin-1").read()
            remote_content = open(remote_file, "r", encoding="latin-1").read()

            # keep only alphanumeric characters
            local_content = ''.join(e.lower() for e in local_content if e.isalnum())
            remote_content = ''.join(e.lower() for e in remote_content if e.isalnum())
            if local_content == remote_content:
                continue

            if "android" not in file and "Android" not in file and "ANDROID" not in file and "java" not in file and "JNI" not in file and "qt" not in file and "Qt" not in file:
                if "android" not in remote_content or "qt" not in remote_content:
                    continue

            # run diff to compare the local and remote files
            diff = ""
            try:
                diff = launch_command("diff " + local_file + " " + remote_file)
            except:
                print("Error in diff " + local_file + " " + remote_file)
            if diff != "":
                print(diff)
                os.system("mkdir -p " + patch_dir + "/" + root_purged)
                os.system("cp " + remote_file + " " + patched_file)
                num_changes += 1
    
    # remove the temporary directory
    # os.system("rm -rf tmp")

    return num_changes


# os.system("rm -rf patchs/patchandroid")
# os.system("mkdir -p patchs/patchandroid")
# create_patch("repos/texmacs", "192.168.200.107", "magix", "/home/magix/texmacs-builder/texmacs/src", "patchs/patchandroid")


#os.system("rm -rf logs repos/home:jmnotin:TeXmacs repos/texmacs patched distr")

machines = {
    "proxmox": MachineLocalProxmox(),
    "macm1": Machine("macm1"),
    "macintel": Machine("macintel"),
    "castafiore": Machine("castafiore"),
}

texmacs_build_systems = [
  #TexmacsMachineLinux("ubu16static", "192.168.200.100", "magix", machines["proxmox"]),
  #TexmacsMachineMac("macintel", "192.168.112.7", "magix", machines["macintel"]),
  #TexmacsMachineMac("macm1", "192.168.112.9", "magix", machines["macm1"]),
  #TexmacsMachineMac("castafiore", "192.168.200.3", "magix", machines["castafiore"], "/Users/magix/DEV/SDK/MacOSX10.6/"),
  #TexmacsMachineWin("Windows11", "192.168.200.103", "magix", machines["proxmox"]),
  TexmacsMachineOBS(),
  #TexmacsMachineAndroid("Android", "192.168.200.107", "magix", machines["proxmox"]),
]


get_global_texmacs_obs()


for machine in texmacs_build_systems:
    machine.build()
    
for machine in texmacs_build_systems:
    machine.test()

for machine in texmacs_build_systems:
    machine.wait()

for machine in texmacs_build_systems:
    machine.join()