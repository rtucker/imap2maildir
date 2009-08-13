# simpleimap.py, originally from http://p.linode.com/2693 on 2009/07/22
# Copyright (c) 2009 Timothy J Fontaine <tjfontaine@gmail.com>
# Copyright (c) 2009 Ryan S. Tucker <rtucker@gmail.com>

import email
import imaplib
import re

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
        status, data = self.search(charset, 'ALL')
        if status != 'OK':
            raise Exception(data)

        for i in data[0].split():
                yield self.get_uid_by_id(i)

    def get_summaries_by_folder(self, folder, charset=None):
        for i in self.get_uids_by_folder(folder, charset=None):
            yield self.get_summary_by_uid(i)

    def get_messages_by_ids(self, ids):
        for i in ids:
            yield self.get_message_by_id(i)

    def get_message_by_id(self, id):
        status, data = self.fetch(id, '(RFC822)')

        if status != 'OK':
            raise Exception(data)

        return email.message_from_string(data[0][1])

    def get_messages_by_uids(self, uids):
        for i in uids:
            yield self.get_message_by_uid(i)

    def get_message_by_uid(self, uid):
        status, data = self.uid('FETCH', uid, '(RFC822)')

        if status != 'OK':
            raise Exception(data)

        return email.message_from_string(data[0][1])

    def get_summaries_by_ids(self, ids):
        for i in ids:
            yield self.get_summary_by_id(i)

    def get_summary_by_id(self, id):
        uid = self.get_uid_by_id(id)
        if uid:
            return self.get_summary_by_uid(uid)

        return None

    def get_uids_by_ids(self, ids):
        for i in ids:
            yield self.get_uid_by_id(i)

    def get_uid_by_id(self, id):
        """Given a message number (id), returns the UID if it exists."""
        status, data = self.fetch(id, '(UID)')

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
            yield self.get_summary_by_uid(i)

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
            raise Exception(data)

        msgid = size = date = None

        if data[0]:
            msgidm = msgidrg.match(data[0])
            sizem = sizerg.match(data[0])
            datem = daterg.match(data[0])    

            if msgidm: msgid = msgidm.group(1)
            if sizem: size = int(sizem.group(1))
            if datem: date = datem.group(1)

        if msgid or size or date:
            return {'uid': uid, 'msgid': msgid, 'size': size, 'date': date}
        else:
            return None

class SimpleImap(imaplib.IMAP4, __simplebase):
    pass

class SimpleImapSSL(imaplib.IMAP4_SSL, __simplebase):
    pass
