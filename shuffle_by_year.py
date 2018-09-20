#!/usr/bin/env python

# Q&D script to sort mail into subfolders by year.
# Reduces the burden upon the filesystem gnomes.

DIRPATH = "/stor0/backups/imapbak/rtucker/Fastmail-rey_fmgirl_com"

import email
import mailbox
import imap2maildir
import sys
import time
import os

def main():
    db = imap2maildir.open_sql_session(DIRPATH + "/.imap2maildir.sqlite")
    mbox = mailbox.Maildir(DIRPATH, False)

    try:

        counter = 0
        c = db.cursor()

        for result in db.execute("select mailfile,folder from seenmessages where folder is null or folder = ''"):
            key = result[0]
            msg = mbox.get_message(key)

            year = None

            if 'Date' in msg:
                ttup = email.utils.parsedate(msg['Date'])
                if ttup:
                    year = ttup[0]

            if year is None:
                tstamp = msg.get_date()
                year = time.gmtime(tstamp).tm_year
                print(key + " has no valid Date header; going with " + str(year))

            ybox = mbox.add_folder(str(year))

            ybox.lock()
            newkey = ybox.add(msg)
            ybox.flush()
            ybox.unlock()

            c.execute("update seenmessages set mailfile = ?, folder = ? where mailfile = ?", (newkey, year, key))

            mbox.lock()
            mbox.discard(key)
            mbox.flush()
            mbox.unlock()

            print("moved " + key + " to " + str(year) + "/" + newkey)

            counter += 1

            if counter % 25 == 0:
                print("committing db")
                db.commit()
                sys.stdout.flush()

                if os.path.exists(".STOP"):
                    print("stop requested")
                    os.unlink(".STOP")
                    break

    finally:
        mbox.unlock()
        db.commit()

if __name__ == "__main__":
    main()

