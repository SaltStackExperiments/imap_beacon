import imaplib
import email
import logging
import salt.ext.six


__virtualname__ = 'watch_imap'

log = logging.getLogger(__name__)

_mail_handle = None

required_values = {
    'IMAP_SUBJECT_MATCH': {
        'type': str,
        'msg': 'Configuration or pillar watch_imap must '
               'contain a value for IMAP_SUBJECT_MATCH'
    },
    'IMAP_FROM_EMAIL': {
        'type': str,
        'msg': 'FROM_EMAIL is required - this is the username '
               'for authenticating to the IMAP server'
    },
    'IMAP_FROM_PWD': {
        'type': str,
        'msg': 'FROM_PWD is required - this is the password for '
               'authenticating to the IMAP server'

    },
    'IMAP_SERVER': {
        'type': str,
        'msg': 'IMAP_SERVER is required - the ip address or hostname for '
               'the IMAP server'
    },
    'IMAP_PORT': {
        'type': str,
        'default': 993,
        'msg': 'IMAP_PORT is required - the port used for connecting to'
               'the IMAP server'
    }
}


def validate(config):
    # Configuration for the watch_imap beacon should be a dictionary.
    if not isinstance(config, dict):
        return False, 'Configuration watch_imap must be a dictionary'
    # At a minimum, it needs a regex `subject_match` for email subjects to
    # match

    errors = []
    for k in salt.ext.six.iterkeys(required_values):
        if not get_value(config, k):
            errors.append(required_values[k]['msg'])
    if errors:
        return False, ','.join(errors)

    return True, 'Valid watch_imap Beacon Configuration'


def get_value(config, _key):
    return __salt__['pillar.get'](_key, config.get(_key))


def beacon(config):
    '''
    Connect to gmail, check for emails with subject matching config
    `subject_match`

    Example Config
    .. code-block:: yaml

       beacons:
         watch_imap:
           subject_match: Hello, World!
    '''

    ret = []
    log.debug('checking email...')
    # for msg in read_email_from_gmail(
    #         config.get('subject_match'),
    #         mark_as_read=config.get('mark_as_read', True)):
    for msg in read_email_from_gmail(config):
        ret.append({'tag': 'imap/msg', 'msg': msg})
    log.debug('done checking email...')

    return ret


# -------------------------------------------------
#
# Utility to read email from Gmail Using Python
#
# ------------------------------------------------


def read_email_from_gmail(config):
    global _mail_handle

    # This connection only needs to happen once
    if not _mail_handle:
        _mail_handle = imaplib.IMAP4_SSL(get_value(config, 'IMAP_SERVER'))
        _mail_handle.login(
                get_value(config, 'IMAP_FROM_EMAIL'),
                get_value(config, 'IMAP_FROM_PWD'))
        typ, data = _mail_handle.select('inbox')
        log.debug('there are %s messages in the box', data[0])

    search_string = '(SUBJECT "{}" UNSEEN)'.format(
            get_value(config, 'IMAP_SUBJECT_MATCH'))
    typ, data = _mail_handle.uid('search', None, search_string)

    id_list = data[0].split()
    log.debug('%s emails to parse', len(id_list))
    for i in id_list:  # (latest_email_id, first_email_id, -1):
        typ, data = _mail_handle.uid('fetch', i, '(RFC822)')
        if not data:
            continue
        log.debug('parsing email id: {}'.format(i))
        # for response_part in filter(lambda x: bool(x), data):
        for response_part in data:
            if isinstance(response_part, tuple):
                send_yield = True  # default to sending event
                msg = email.message_from_string(response_part[1])

                # Mark the email as read by default
                if get_value(config, 'IMAP_MARK_AS_READ'):
                    _mail_handle.uid('store', i, '+FLAGS', '\Seen')

                msg_return = {
                        'subject': msg['subject'],
                        'from': msg['from'],
                        'date': msg['date'],
                        'id': i,
                        # 'body': msg.get_payload()
                        }

                if send_yield:
                    yield msg_return
