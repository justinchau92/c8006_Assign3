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
#        password guessing attempts against SSH and block that IPaddr using Netfilter.
#
# ----------------------------------------------------------------------------*/

import time
import re
import os
import argparse
import threading
from Tkinter import *
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

#list of inputs you need
fields = 'Attempts', 'Scantime', 'Timeban'

# Adds this program as a crontab job
# will check the /etc/crontab file and check if the same command already exists
# -----------------------------------------------------------------------------------------
def cronAdd(entries):
    checker = 0
    
    Attempts = entries[0][1].get()

    # Convert the times to seconds
    Scantime = int(entries[1][1].get())
    Timeban = int(entries[2][1].get())

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
    parser.add_argument('-a', '--attempt', nargs=1, help='Max failed attempts before blocking the IPaddr.',
                        required=True, dest='attempt')

    parser.add_argument('-t', '--time', nargs=1,
                        help='Max time(min) window between attempts before blocking the IPaddr.', required=True,
                        dest='time')

    parser.add_argument('-b', '--block', nargs=1,
                        help='How long to block the IPaddr (minutes). Enter 0 for indefinite IPaddr block',
                        required=True, dest='block')
    args = parser.parse_args()


    Attempts = int(args.attempt[0])

    # MultIPaddrly the numbers by 60 to convert the minutes to seconds
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

# Creates a new user based on each new IPaddr addresses
# -----------------------------------------------------------------------------------------
def make_user(IPaddr, timeStampArray):
    user = User(IPaddr, timeStampArray)
    return user

# Class to store "users". It stores both IPaddr and
# time stamp array of each attempt.
# -----------------------------------------------------------------------------------------
class User(object):
    IPaddr = ""
    timeStampArray = []

    def __init__(self, IPaddr, timeStampArray):
        self.IPaddr = IPaddr
        self.timeStampArray = timeStampArray

# Block the user through an IPaddrtables command by their IPaddr address. It calls the
# unblock method right afterwards with the Timeban as the thread sleep
# -----------------------------------------------------------------------------------------
def Block_IPaddr(IPaddr):
    global Timeban
    # Convert Timeban back to minutes from seconds.
    Timebantemp = Timeban / 60
    if Timeban != 0:
        print "%s has been banned for %d minute(s)." % (IPaddr, Timebantemp)
    else:
        print "%s has been banned forever." % IPaddr
    command = "/usr/sbin/IPaddrtables -A INPUT -s %s -j DROP" % IPaddr
    os.system(command)
    if Timeban != 0:
        threading.Timer(Timeban, unBlock_IPaddr, [IPaddr]).start()


# Remove the IPaddrtables command that blocks that IPaddr
# -----------------------------------------------------------------------------------------
def unBlock_IPaddr(IPaddr):
    command = "/usr/sbin/IPaddrtables -D INPUT -s %s -j DROP" % IPaddr
    os.system(command)
    print ("User time ban over, %s has been unbanned") % IPaddr


# Main function
# -----------------------------------------------------------------------------------------
class Handler(FileSystemEventHandler):
    global Badattempt
    global BannedIPaddr
    global Attempts

    def on_modified(self, event):
        if event.src_path == "/var/log/secure":
            fileHandle = open('/var/log/secure')
            lineList = fileHandle.readlines()
            lastLine = lineList[len(lineList) - 1]
            secondLastLine = lineList[len(lineList) - 2]

            if "Failed password for" in lastLine:
                timeStampArray = []
                IPaddr = re.findall(r'[0-9]+(?:\.[0-9]+){3}', lastLine)
                timeStamp = re.findall(r'\d{2}:\d{2}:\d{2}', lastLine)
                if not Badattempt:
                    user = make_user(IPaddr[0], timeStampArray)
                    add_timestamp(user, timeStamp[0])
                    Badattempt.append(user)
                    print((user.IPaddr) + " failed login attempt")
                    # if user goes over the attempts max, block
                    if len(user.timeStampArray) >= Attempts:
                        IPaddr = user.IPaddr[0]
                        Block_IPaddr(IPaddr)
                else:
                    isnewuser = 0
                    for user in Badattempt:
                        if user.IPaddr == IPaddr[0]:
                            if timeStamp[0] not in user.timeStampArray:
                                add_timestamp(user, timeStamp[0])
                                print((user.IPaddr) + " failed login attempt")
                                isnewuser = 1
                                if len(user.timeStampArray) >= Attempts:
                                    arrayLength = len(user.timeStampArray)
                                    firstTimeStamp = user.timeStampArray[(arrayLength - Attempts)]
                                    lastTimeStamp = user.timeStampArray[(arrayLength - 1)]
                                    firstTime = Convert_time(firstTimeStamp)
                                    lastTime = Convert_time(lastTimeStamp)
                                    timeDifference = (lastTime - firstTime)
                                    if timeDifference <= Scantime:
                                        IPaddr = str(user.IPaddr)
                                        Block_IPaddr(IPaddr)
                    if isnewuser == 0:
                        user = make_user(IPaddr[0], timeStampArray)
                        add_timestamp(user, timeStamp[0])
                        Badattempt.append(user)
                        print((user.IPaddr) + " failed login attempt")
            # Empty the time stamp array if it already exists
            elif ("Accepted password for" in lastLine) or ("Accepted password for" in secondLastLine):
                IPaddr = re.findall(r'[0-9]+(?:\.[0-9]+){3}', secondLastLine)
                for user in Badattempt:
                    if user.IPaddr == IPaddr[0]:
                        user.timeStampArray = []
            elif 'Accepted password for' in lastLine:
                IPaddr = re.findall(r'[0-9]+(?:\.[0-9]+){3}', lastLine)
                if Badattempt:
                    for user in Badattempt:
                        if user.IPaddr == IPaddr[0]:
                            timeStampArray = []
                            
                            
#---------------------------------------------------
# makeform - method to create input box and labels
#
# root - the GUI form
# fields - list of inputs you want i.e (serverip, port)
#-------------------------------------------------
def makeform(root, fields):
	entries = []

	#for each field create an input
	for field in fields:
		row = Frame(root)
		lab = Label(row, width=15, text = field , anchor ='w')
		ent = Entry(row)
		ent.config(highlightbackground = "gray")
		row.pack(side=TOP, fill=X, padx=5, pady=5)
		lab.pack(side=LEFT)
		ent.pack(side=RIGHT,expand=YES, fill=X)
		entries.append((field,ent))
	return entries


if __name__ == "__main__":
    #Attempts, Scantime, Timeban = Arguments()
    #cronAdd(Attempts, Scantime, Timeban)
    
    root = Tk()
    ents = makeform(root,fields)
    
    buttonFrame = Frame(root)
    buttonFrame.pack(side=TOP,padx=5,pady=5)
    
    b1 = Button(root, text='Run', command=(lambda e=ents: cronAdd(e)))
    b1.pack(in_=buttonFrame , side=LEFT, padx=5,pady=5)
    
    event_handler = Handler()

    observer = Observer()
    observer.schedule(event_handler, path='/var/log', recursive=False)
    observer.start()

    Badattempt = []
    BannedIPaddr = []

    try:
        while True:
            time.sleep(0.01)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    
    root.title("Intrusion Dectection System")
    root.mainloop()

