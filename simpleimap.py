# simpleimap.py, originally from http://p.linode.com/2693 on 2009/07/22
# Copyright (c) 2009 Timothy J Fontaine <tjfontaine@gmail.com>
# Copyright (c) 2009 Ryan S. Tucker <rtucker@gmail.com>

import email
import imaplib
import platform
import re
import time

class __simplebase:
    def parseFetch(self, text):
        """Given a string (e.g. '1 (ENVELOPE...'), breaks it down into
        a useful format.

        Based on Helder Guerreiro <helder@paxjulia.com>'s
        imaplib2 sexp.py: http://code.google.com/p/webpymail/
        """

        literal_re = re.compile(r'^{(\d+)}\r\n')
        simple_re = re.compile(r'^([^ ()]+)')
        quoted_re = re.compile(r'^"((?:[^"\\]|\\"|\\)*?)"')

        pos = 0
        length = len(text)
        current = ''
        result = []
        cur_result = result
        level = [ cur_result ]

        # Scanner
        while pos < length:

            # Quoted literal:
            if text[pos] == '"':
                quoted = quoted_re.match(text[pos:])
                if quoted:
                    cur_result.append( quoted.groups()[0] )
                    pos += quoted.end() - 1

            # Numbered literal:
            elif text[pos] == '{':
                lit = literal_re.match(text[pos:])
                if lit:
                    start = pos+lit.end()
                    end = pos+lit.end()+int(lit.groups()[0])
                    pos = end - 1
                    cur_result.append( text[ start:end ] )

            # Simple literal
            elif text[pos] not in '() ':
                simple = simple_re.match(text[pos:])
                if simple:
                    tmp = simple.groups()[0]
                    if tmp.isdigit():
                        tmp = int(tmp)
                    elif tmp == 'NIL':
                        tmp = None
                    cur_result.append( tmp )
                    pos += simple.end() - 1

            # Level handling, if we find a '(' we must add another list, if we
            # find a ')' we must return to the previous list.
            elif text[pos] == '(':
                cur_result.append([])
                cur_result = cur_result[-1]
                level.append(cur_result)

            elif text[pos] == ')':
                try:
                    cur_result = level[-2]
                    del level[-1]
                except IndexError:
                    raise ValueError('Unexpected parenthesis at pos %d' % pos)

            pos += 1

        # We now have a list of lists.  Dict this a bit...
        outerdict = self.__listdictor(result)
        replydict = {}

        for i in outerdict.keys():
            replydict[i] = self.__listdictor(outerdict[i])

        return replydict

    def __listdictor(self, inlist):
        outdict = {}

        for i in xrange(0,len(inlist),2):
            outdict[inlist[i]] = inlist[i+1]

        return outdict

    def parseInternalDate(self, resp):
        """Takes IMAP INTERNALDATE and turns it into a Python time
        tuple referenced to GMT.

        Based from: http://code.google.com/p/webpymail/
        """

        Mon2num = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

        InternalDate = re.compile(
                        r'(?P<day>[ 0123][0-9])-(?P<mon>[A-Z][a-z][a-z])-(?P<year>[0-9][0-9][0-9][0-9])'
                        r' (?P<hour>[0-9][0-9]):(?P<min>[0-9][0-9]):(?P<sec>[0-9][0-9])'
                        r' (?P<zonen>[-+])(?P<zoneh>[0-9][0-9])(?P<zonem>[0-9][0-9])'
                        )

        mo = InternalDate.match(resp)
        if not mo:
            return None

        mon = Mon2num[mo.group('mon')]
        zonen = mo.group('zonen')

        day = int(mo.group('day'))
        year = int(mo.group('year'))
        hour = int(mo.group('hour'))
        min = int(mo.group('min'))
        sec = int(mo.group('sec'))
        zoneh = int(mo.group('zoneh'))
        zonem = int(mo.group('zonem'))

        zone = (zoneh*60 + zonem)*60

        # handle negative offsets
        if zonen == '-':
            zone = -zone

        tt = (year, mon, day, hour, min, sec, -1, -1, -1)

        utc = time.mktime(tt)

        # Following is necessary because the time module has no 'mkgmtime'.
        # 'mktime' assumes arg in local timezone, so adds timezone/altzone.

        lt = time.localtime(utc)
        if time.daylight and lt[-1]:
            zone = zone + time.altzone
        else:
            zone = zone + time.timezone

        return time.localtime(utc - zone)

    def get_messages_by_folder(self, folder, charset=None, search='ALL'):
        ids = self.get_ids_by_folder(folder, search)

        for m in self.get_messages_by_ids(ids):
            yield m

    def get_ids_by_folder(self, folder, charset=None, search='ALL'):
        self.select(folder)
        status, data = self.search(charset, search)
        if status != 'OK':
            raise Exception(data)

        return data[0].split()

    def get_uids_by_folder(self, folder, charset=None, search='ALL'):
        self.select(folder)
        status, data = self.uid('SEARCH', charset, search)
        if status != 'OK':
            raise Exception(data)

        return data[0].split()

    def get_summaries_by_folder(self, folder, charset=None, search='ALL'):
        for i in self.get_uids_by_folder(folder, charset, search):
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
        """Retrieve a dictionary of simple header information for a given id.

        Requires: id (Sequence number of message)
        Returns: {'uid': UID you requested,
                  'msgid': RFC822 Message ID,
                  'size': Size of message in bytes,
                  'date': IMAP's Internaldate for the message,
                  'envelope': Envelope data}
        """

        # Retrieve the message from the server.
        status, data = self.fetch(id, '(UID ENVELOPE RFC822.SIZE INTERNALDATE)')

        if status != 'OK':
            return None

        return self.parse_summary_data(data)

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
                  'date': IMAP's Internaldate for the message,
                  'envelope': Envelope data}
        """

        # Retrieve the message from the server.
        status, data = self.uid('FETCH', uid, 
                              '(UID ENVELOPE RFC822.SIZE INTERNALDATE)')

        if status != 'OK':
            return None

        return self.parse_summary_data(data)

    def parse_summary_data(self, data):
        """Takes the data result (second parameter) of a self.uid or
        self.fetch for (UID ENVELOPE RFC822.SIZE INTERNALDATE) and returns
        a dict of simple header information.

        Requires: self.uid[1] or self.fetch[1]
        Returns: {'uid': UID you requested,
                  'msgid': RFC822 Message ID,
                  'size': Size of message in bytes,
                  'date': IMAP's Internaldate for the message,
                  'envelope': Envelope data}
        """

        uid = date = envdate = envfrom = msgid = size = None

        if data[0]:
            # Grab a list of things in the FETCH response.
            fetchresult = self.parseFetch(data[0])
            contents = fetchresult[fetchresult.keys()[0]]

            uid = contents['UID']
            date = contents['INTERNALDATE']
            envdate = contents['ENVELOPE'][0]
            if contents['ENVELOPE'][2][0][2] and contents['ENVELOPE'][2][0][3]:
                envfrom = '@'.join(contents['ENVELOPE'][2][0][2:])
            else:
                # No From: header.  Woaaah.
                envfrom = 'MAILER-DAEMON'
            msgid = contents['ENVELOPE'][9]
            size = int(contents['RFC822.SIZE'])

        if msgid or size or date:
            return {'uid': int(uid), 'msgid': msgid, 'size': size, 'date': date, 'envfrom': envfrom, 'envdate': envdate}
        else:
            return None

    def Folder(self, folder, charset=None):
        """Returns an instance of FolderClass."""
        return FolderClass(self, folder, charset)

class FolderClass:
    """Class for instantiating a folder instance.

    TODO: Trap exceptions like:
    ssl.SSLError: [Errno 8] _ssl.c:1325: EOF occurred in violation of protocol
    by trying to reconnect to the server.
    (Raised up via get_summary_by_uid in Summaries when IMAP server boogers.)
    """
    def __init__(self, parent, folder='INBOX', charset=None):
        self.__folder = folder
        self.__charset = charset
        self.__parent = parent
        self.__keepaliver = self.__keepaliver_none__
        self.__turbo = None
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

    def __turbo__(self, turbofunction):
        """Calls turbofunction(uid) for every uid, only yielding those
        where turbofunction returns False.  Set to None to disable."""
        self.__turbo = turbofunction
        self.__turbocounter = 0

    def turbocounter(self, reset=False):
        if self.__turbo:
            oldvalue = self.__turbocounter
            if reset:
                self.__turbocounter = 0
            return oldvalue
        else:
            return 0

    def Messages(self, search='ALL'):
        for m in self.__parent.get_messages_by_folder(self.__folder, self.__charset, search):
            yield m

    def Summaries(self, search='ALL'):
        if self.__turbo:
            self.__parent.select(self.__folder)
            for u in self.Uids():
                if not self.__turbo(u):
                    summ = self.__parent.get_summary_by_uid(u)
                    if summ:
                        yield summ
                else:
                    # long hangtimes can suck
                    self.__keepaliver()
                    self.__turbocounter += 1
        else:
            for s in self.__parent.get_summaries_by_folder(self.__folder, self.__charset, search):
                yield s

    def Ids(self, search='ALL'):
        for i in self.__parent.get_ids_by_folder(self.__folder, self.__charset, search):
            yield i

    def Uids(self, search='ALL'):
        for u in self.__parent.get_uids_by_folder(self.__folder, self.__charset, search):
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
    if platform.python_version().startswith('2.6.'):
        def readline(self):
            """Read line from remote.  Overrides built-in method to fix
            infinite loop problem when EOF occurs, since sslobj.read
            returns '' on EOF."""
            self.sslobj.suppress_ragged_eofs = False
            line = []
            while 1:
                char = self.sslobj.read(1)
                line.append(char)
                if char == "\n": return ''.join(line)

    if 'Windows' in platform.platform():
        def read(self, n):
            """Read 'size' bytes from remote.  (Contains workaround)"""
            maxRead = 1000000
            # Override the read() function; fixes a problem on Windows
            # when it tries to eat too much.  http://bugs.python.org/issue1441530
            if n <= maxRead:
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

