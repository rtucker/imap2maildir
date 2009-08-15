# simpleimap.py, originally from http://p.linode.com/2693 on 2009/07/22
# Copyright (c) 2009 Timothy J Fontaine <tjfontaine@gmail.com>
# Copyright (c) 2009 Ryan S. Tucker <rtucker@gmail.com>

import email
import imaplib
import platform
import re
import time

class __simplebase:
    def get_messages_by_folder(self, folder, charset=None):
        ids = self.get_ids_by_folder(folder)

        for m in self.get_messages_by_ids(ids):
            yield m

    def get_ids_by_folder(self, folder, charset=None):
        self.select(folder)
        status, data = self.search(charset, 'ALL')
        if status != 'OK':
            raise Exception(data)

        return data[0].split()

    def get_uids_by_folder(self, folder, charset=None):
        self.select(folder)
        status, data = self.uid('SEARCH', charset, 'ALL')
        if status != 'OK':
            raise Exception(data)

        return data[0].split()

    def get_summaries_by_folder(self, folder, charset=None):
        for i in self.get_uids_by_folder(folder, charset=None):
            yield self.get_summary_by_uid(int(i))

    def get_messages_by_ids(self, ids):
        for i in ids:
            yield self.get_message_by_id(int(i))

    def get_message_by_id(self, id):
        status, data = self.fetch(int(id), '(RFC822)')

        if status != 'OK':
            raise Exception(data)

        return email.message_from_string(data[0][1])

    def get_messages_by_uids(self, uids):
        for i in uids:
            yield self.get_message_by_uid(int(i))

    def get_message_by_uid(self, uid):
        status, data = self.uid('FETCH', uid, '(RFC822)')

        if status != 'OK':
            raise Exception(data)

        return email.message_from_string(data[0][1])

    def get_summaries_by_ids(self, ids):
        for i in ids:
            yield self.get_summary_by_id(int(i))

    def get_summary_by_id(self, id):
        uid = self.get_uid_by_id(int(id))
        if uid:
            return self.get_summary_by_uid(int(uid))

        return None

    def get_uids_by_ids(self, ids):
        for i in ids:
            yield self.get_uid_by_id(int(i))

    def get_uid_by_id(self, id):
        """Given a message number (id), returns the UID if it exists."""
        status, data = self.fetch(int(id), '(UID)')

        if status != 'OK':
            raise Exception(data)

        if data[0]:
            uidrg = re.compile('.*?UID\\s+(\\d+)',re.IGNORECASE|re.DOTALL)
            uidm = uidrg.match(data[0])
            if uidm:
                return int(uidm.group(1))

        return None

    def get_summaries_by_uids(self, uids):
        for i in uids:
            yield self.get_summary_by_uid(int(i))

    def get_summary_by_uid(self, uid):
        """Retrieve a dictionary of simple header information for a given uid.

        Requires: uid (unique numeric ID of message)
        Returns: {'uid': UID you requested,
                  'msgid': RFC822 Message ID,
                  'size': Size of message in bytes,
                  'date': IMAP's Internaldate for the message}
        """

        msgidrg = re.compile('.*?ENVELOPE \(.*?(<[^>]+>)',
                             re.IGNORECASE|re.DOTALL)
        sizerg = re.compile('.*?RFC822\\.SIZE\\s+(\\d+)',
                            re.IGNORECASE|re.DOTALL)
        daterg = re.compile('.*?INTERNALDATE\\s+(".*?")',
                            re.IGNORECASE|re.DOTALL)

        # Retrieve the message from the server.
        status, data = self.uid('FETCH', uid, 
                              '(ENVELOPE RFC822.SIZE INTERNALDATE)')

        if status != 'OK':
            return None

        msgid = size = date = None

        if data[0]:
            msgidm = msgidrg.match(data[0])
            sizem = sizerg.match(data[0])
            datem = daterg.match(data[0])    

            if msgidm: msgid = msgidm.group(1)
            if sizem: size = int(sizem.group(1))
            if datem: date = datem.group(1)

        if msgid or size or date:
            return {'uid': int(uid), 'msgid': msgid, 'size': size, 'date': date}
        else:
            return None

    def Folder(self, folder, charset=None):
        """Returns an instance of FolderClass."""
        return FolderClass(self, folder, charset)

class FolderClass:
    """Class for instantiating a folder instance."""
    def __init__(self, parent, folder='INBOX', charset=None):
        self.__folder = folder
        self.__charset = charset
        self.__parent = parent
        self.__keepaliver = self.__keepaliver_none__
        self.host = parent.host
        self.folder = folder

    def __len__(self):
        status, data = self.__parent.select(self.__folder)
        if status != 'OK':
            raise Exception(data)

        return int(data[0])

    def __keepaliver__(self, keepaliver):
        self.__keepaliver = keepaliver

    def __keepaliver_none__(self):
        pass

    def __turbo__(self, turbo, turbodb, turboarg):
        """Enable turbo mode.  Not very general right now; mostly specific
        to imap2maildir.  Alas."""
        self.__turbo = turbo
        self.__turbodb = turbodb
        self.__turboarg = turboarg
        self.__turbocounter = 0

    def turbocounter(self, reset=False):
        if self.__turbo:
            oldvalue = self.__turbocounter
            if reset:
                self.__turbocounter = 0
            return oldvalue
        else:
            return 0

    def Messages(self):
        for m in self.__parent.get_messages_by_folder(self.__folder, self.__charset):
            yield m

    def Summaries(self):
        if self.__turbo:
            self.__parent.select(self.__folder)
            for u in self.Uids():
                if not self.__turbo(self.__turbodb, self.__turboarg, uid=u):
                    summ = self.__parent.get_summary_by_uid(u)
                    if summ:
                        yield summ
                else:
                    # long hangtimes can suck
                    self.__keepaliver()
                    self.__turbocounter += 1
        else:
            for s in self.__parent.get_summaries_by_folder(self.__folder, self.__charset):
                yield s

    def Ids(self):
        for i in self.__parent.get_ids_by_folder(self.__folder, self.__charset):
            yield i

    def Uids(self):
        for u in self.__parent.get_uids_by_folder(self.__folder, self.__charset):
            yield u

class Server:
    """Class for instantiating a server instance"""
    def __init__(self, hostname=None, username=None, password=None, port=None, ssl=True):
        self.__hostname = hostname
        self.__username = username
        self.__password = password
        self.__ssl = ssl
        self.__connection = None
        self.__lastnoop = 0

        if port:
            self.__port = port
        elif ssl:
            self.__port = 993
        else:
            self.__port = 143

        if self.__hostname and self.__username and self.__password:
            self.Connect()

    def Connect(self):
        if self.__ssl:
            self.__connection = SimpleImapSSL(self.__hostname, self.__port)
        else:
            self.__connection = SimpleImap(self.__hostname, self.__port)

        self.__connection.login(self.__username, self.__password)

    def Get(self):
        return self.__connection

    def Keepalive(self):
        """Call me occasionally just to make sure everything's OK..."""
        if self.__lastnoop + 30 < time.time():
            self.__connection.noop()
            self.__lastnoop = time.time()

class SimpleImap(imaplib.IMAP4, __simplebase):
    pass

class SimpleImapSSL(imaplib.IMAP4_SSL, __simplebase):
    def read(self, n):
        if 'Windows' in platform.platform():
            # Override the read() function; fixes a problem on Windows
            # when it tries to eat too much.  http://bugs.python.org/issue1441530
            if n <= 1000000:
                return imaplib.IMAP4_SSL.read (self, n)
            else:
                soFar = 0
                result = ""
                while soFar < n:
                    thisFragmentSize = min(maxRead, n-soFar)
                    fragment =\
                        imaplib.IMAP4_SSL.read (self, thisFragmentSize)
                    result += fragment
                    soFar += thisFragmentSize # only a few, so not a tragic o/head
            return result
        else:
            return imaplib.IMAP4_SSL.read (self, n)

