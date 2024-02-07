from threading import Lock
import os
from autobuild.utils import system_remote
import time

class Machine:

    def __init__(self, name):
        self.name = name
        self.lock = Lock()
    
    def use(self, ip=None):
        self.lock.acquire()

    def release(self, ip=None):
        self.lock.release()
    

class MachineLocalProxmox(Machine):

    def __init__(self):
        super().__init__("local_proxmox")
    
    def use(self, ip=None):
        super().use(ip)
        
        # take the last digit of the ip
        full_ip = ip
        ip = ip.split(".")[-1]

        # check if the vm is already running
        status = system_remote("qm status " + ip, "127.0.0.1", "root") + system_remote("pct status " + ip, "127.0.0.1", "root")
        print(status)
        if "running" in status:
            # if it is
            self.to_release = False
        else:
            # if not, start it
            res = system_remote("qm start " + ip, "127.0.0.1", "root")
            print(res)
            res = system_remote("pct start " + ip, "127.0.0.1", "root")
            print(res)
            self.to_release = True
        
        # while the ip is not reachable
        while os.system("ping -c 1 " + full_ip) != 0:
            print("waiting for " + full_ip)
            time.sleep(10)

        print("ready")

        # enjoy !
    
    def release(self, ip=None):
        # take the last digit of the ip
        full_ip = ip
        ip = ip.split(".")[-1]

        if self.to_release:
            res = system_remote("qm shutdown " + ip, "127.0.0.1", "root")
            print(res)
            res = system_remote("pct shutdown " + ip, "127.0.0.1", "root")
            print(res)
        
            while os.system("ping -c 1 " + full_ip) == 0:
                time.sleep(10)

        super().release(ip)


class MachineLock:
    def __init__(self, machine, ip):
        self.machine = machine
        self.ip = ip

    def __enter__(self):
        self.machine.use(self.ip)
        return self

    def __exit__(self, type, value, traceback):
        self.machine.release(self.ip)
        return False