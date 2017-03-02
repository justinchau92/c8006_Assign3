#!/usr/bin/python
# -----------------------------------------------------------------------------
# FUNCTION:       IDS
#
# DATE:           February 27, 2017
#
# DESIGNERS:      Paul Cabanez, Justin Chau
#
# PROGRAMMERS:    Paul Cabanez, Justin Chau
#
# NOTES: simple monitor application that will detect
#        password guessing attempts against SSH and block that IP using Netfilter.
#
# ----------------------------------------------------------------------------*/

import time
import re
import os
import argparse
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Adds this program as a crontab job
# will check the /etc/crontab file and check if the same command already exists
# -----------------------------------------------------------------------------------------
def cronAdd(Attempts, Scantime, Timeban):
    checker = 0

    # Convert the times to seconds
    Scantime = Scantime / 60
    Timeban = Timeban / 60

    filepath = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.basename(__file__)
    cronJob = '@reboot /usr/bin/python %s/%s -a %s -t %s -b %s' % (
    filepath, filename, Attempts, Scantime, Timeban)
    with open('/etc/crontab', 'r') as crontab:
        for line in crontab:
            if cronJob not in line:
                if checker != 1:
                    checker = 0
            else:
                checker = 1
    if checker == 0:
        crontab = open('/etc/crontab', 'a')
        crontab.seek(0, 2)
        command = '@reboot /usr/bin/python %s/%s -a %s -t %s -b %s' % (
        filepath, filename, Attempts, Scantime, Timeban)
        crontab.write(command)
        crontab.close()
    os.system('crontab /etc/crontab')


# Initialize all the parameters through arguments
# -----------------------------------------------------------------------------------------
def Arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--attempt', nargs=1, help='Max failed attempts before blocking the IP.',
                        required=True, dest='attempt')

    parser.add_argument('-t', '--time', nargs=1,
                        help='Max time(min) window between attempts before blocking the IP.', required=True,
                        dest='time')

    parser.add_argument('-b', '--block', nargs=1,
                        help='How long to block the IP (minutes). Enter 0 for indefinite IP block',
                        required=True, dest='block')
    args = parser.parse_args()


    Attempts = int(args.attempt[0])

    # Multiply the numbers by 60 to convert the minutes to seconds
    Scantime = int(args.time[0])
    Scantime = Scantime * 60

    Timeban = int(args.block[0])
    Timeban = Timeban * 60

    return Attempts, Scantime, Timeban

# Convert the timestamp format of X:X:X to a format that is able
# to be operated on.
# -----------------------------------------------------------------------------------------
def Convert_time(time):
    timeArray = time.split(':')
    hours = int(timeArray[0])
    hours = hours * 3600
    minutes = int(timeArray[1])
    minutes = minutes * 60
    seconds = int(timeArray[2])
    totalTime = hours + minutes + seconds
    return totalTime

# Add the new timestamp of the event to the respective user's
# time stamp array
# -----------------------------------------------------------------------------------------
def add_timestamp(user, timeStamp):
    user.timeStampArray.append(timeStamp)

# Creates a new user based on each new IP addresses
# -----------------------------------------------------------------------------------------
def make_user(ip, timeStampArray):
    user = User(ip, timeStampArray)
    return user

# Class to store "users". It stores both IP and
# time stamp array of each attempt.
# -----------------------------------------------------------------------------------------
class User(object):
    ip = ""
    timeStampArray = []

    def __init__(self, ip, timeStampArray):
        self.ip = ip
        self.timeStampArray = timeStampArray

# Block the user through an IPtables command by their IP address. It calls the
# unblock method right afterwards with the Timeban as the thread sleep
# -----------------------------------------------------------------------------------------
def Block_IP(IP):
    global Timeban
    # Convert Timeban back to minutes from seconds.
    Timebantemp = Timeban / 60
    if Timeban != 0:
        print "%s has been banned for %d minutes." % (IP, Timebantemp)
    else:
        print "%s has been banned forever." % IP
    command = "/usr/sbin/iptables -A INPUT -s %s -j DROP" % IP
    os.system(command)
    if Timeban != 0:
        threading.Timer(Timeban, unBlock_IP, [IP]).start()


# Remove the IPtables command that blocks that IP
# -----------------------------------------------------------------------------------------
def unBlock_IP(IP):
    command = "/usr/sbin/iptables -D INPUT -s %s -j DROP" % IP
    os.system(command)
    print ("User Time Ban Over - %s has been unbanned") % IP


# Main function
# -----------------------------------------------------------------------------------------
class MyHandler(FileSystemEventHandler):
    global Badattempts
    global BannedIP
    global Attempts

    def on_modified(self, event):

        if event.src_path == "/var/log/secure":
            fileHandle = open('/var/log/secure')
            lineList = fileHandle.readlines()
            lastLine = lineList[len(lineList) - 1]
            secondLastLine = lineList[len(lineList) - 2]

            if "Failed password for" in lastLine:
                timeStampArray = []
                ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}', lastLine)
                timeStamp = re.findall(r'\d{2}:\d{2}:\d{2}', lastLine)

                if not Badattempts:
                    user = make_user(ip[0], timeStampArray)
                    add_timestamp(user, timeStamp[0])

                    Badattempts.append(user)
                    print "%s's failed login attempts time stamps (%d total): %s " % (
                    user.ip, len(user.timeStampArray), user.timeStampArray)

                    if len(user.timeStampArray) >= Attempts:
                        IP = user.ip[0]
                        Block_IP(IP)

                else:
                    isnewuser = 0
                    for user in Badattempts:
                        if user.ip == ip[0]:

                            if timeStamp[0] not in user.timeStampArray:
                                add_timestamp(user, timeStamp[0])
                                print "%s's failed login attempts time stamps (%d total): %s " % (
                                user.ip, len(user.timeStampArray), user.timeStampArray)
                                isnewuser = 1
                                if len(user.timeStampArray) >= Attempts:
                                    arrayLength = len(user.timeStampArray)
                                    firstTimeStamp = user.timeStampArray[(arrayLength - Attempts)]
                                    lastTimeStamp = user.timeStampArray[(arrayLength - 1)]
                                    firstTime = Convert_time(firstTimeStamp)
                                    lastTime = Convert_time(lastTimeStamp)
                                    timeDifference = (lastTime - firstTime)
                                    if timeDifference <= Scantime:
                                        IP = str(user.ip)
                                        Block_IP(IP)

                    if isnewuser == 0:
                        user = make_user(ip[0], timeStampArray)
                        add_timestamp(user, timeStamp[0])
                        Badattempts.append(user)
                        print "%s's failed login attempts time stamps (%d total): %s " % (
                        user.ip, len(user.timeStampArray), user.timeStampArray)

            # Empty the time stamp array if it already exists
            elif ("Accepted password for" in lastLine) or ("Accepted password for" in secondLastLine):
                ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}', secondLastLine)
                for user in Badattempts:
                    if user.ip == ip[0]:
                        user.timeStampArray = []

            elif 'Accepted password for' in lastLine:
                ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}', lastLine)
                if Badattempts:
                    for user in Badattempts:
                        if user.ip == ip[0]:
                            timeStampArray = []


if __name__ == "__main__":
    Attempts, Scantime, Timeban = Arguments()
    cronAdd(Attempts, Scantime, Timeban)
    event_handler = MyHandler()

    observer = Observer()
    observer.schedule(event_handler, path='/var/log', recursive=False)
    observer.start()

    Badattempts = []
    BannedIP = []

    try:
        while True:
            time.sleep(0.01)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
