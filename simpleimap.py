# simpleimap.py, originally from http://p.linode.com/2693 on 2009/07/22
# Copyright (c) 2009 Timothy J Fontaine <tjfontaine@gmail.com>
# Copyright (c) 2009 Ryan S. Tucker <rtucker@gmail.com>

import imaplib
import email

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

class SimpleImap(imaplib.IMAP4, __simplebase):
    pass

class SimpleImapSSL(imaplib.IMAP4_SSL, __simplebase):
    pass
