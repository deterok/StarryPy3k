"""
StarryPy Mail Plugin

Provides a mail system that allows users to send messages to players that
are not logged in. When the recipient next logs in, they will be notified
that they have new messages.

Author: medeor413
"""
import asyncio
import datetime

from base_plugin import StorageCommandPlugin
from utilities import Command, send_message


class Mail:
    def __init__(self, message, author):
        self.message = message
        self.time = datetime.datetime.now()
        self.author = author


class MailPlugin(StorageCommandPlugin):
    name = "mail"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {"max_mail_storage": 25}

    def __init__(self):
        super().__init__()
        self.max_mail = 0
        self.find_player = None

    def activate(self):
        super().activate()
        self.max_mail = self.plugin_config.max_mail_storage
        self.find_player = self.plugins.player_manager.find_player
        if 'mail' not in self.storage:
            self.storage['mail'] = {}

    def on_connect_success(self, data, connection):
        """
        Catch when a player successfully connects to the server, and send them
        a new mail message.
        :param data:
        :param connection:
        :return: True. Must always be true so the packet continues.
        """
        if self.storage['mail'][connection.player.uuid]['unread']:
            asyncio.ensure_future(self._display_unread(connection))
        return True

    def _display_unread(self, connection):
        yield from asyncio.sleep(3)
        unread_count = len(self.storage['mail'][connection.player.uuid][
            'unread'])
        mail_count = unread_count + len(self.storage['mail']
                                        [connection.player.uuid]['read'])
        yield from send_message(connection, "You have {} unread messages."
                                .format(unread_count))
        if mail_count > self.max_mail * 0.8:
            yield from send_message(connection, "Your mailbox is almost full!")

    @Command("sendmail",
             perm="mail.sendmail",
             doc="Send mail to a player, to be read later.",
             syntax="(user) (message)")
    def _sendmail(self, data, connection):
        if data:
            target = self.find_player(data[0])
            if not target:
                raise SyntaxWarning("Couldn't find target.")
            if not data[1]:
                raise SyntaxWarning("No message provided.")
            uid = target.uuid
            if uid not in self.storage['mail']:
                self.storage['mail'][uid] = {"unread": [], "read": []}
            mailbox = self.storage['mail'][uid]
            if len(mailbox['unread']) + len(mailbox['read']) >= self.max_mail:
                yield from send_message(connection, "{}'s mailbox is full!"
                                        .format(target.alias))
            else:
                mail = Mail(" ".join(data[1:]), connection.player)
                mailbox['unread'].insert(0, mail)
                yield from send_message(connection, "Mail delivered to {}."
                                        .format(target.alias))
                if target.logged_in:
                    yield from send_message(target.connection, "New mail from "
                                                               "{}!"
                                            .format(connection.player.alias))
        else:
            raise SyntaxWarning("No target provided.")

    @Command("readmail",
             perm="mail.readmail",
             doc="Read mail recieved from players. Give a number for a "
                 "specific mail, or no number for all unread mails.",
             syntax="[index]")
    def _readmail(self, data, connection):
        try:
            mailbox = self.storage['mail'][connection.player.uuid]
        except KeyError:
            self.storage['mail'][connection.player.uuid] = {"unread": [],
                                                            "read": []}
            mailbox = self.storage['mail'][connection.player.uuid]
        if data:
            try:
                index = int(data[0]) - 1
                mail = mailbox['unread'].pop(index)
                mailbox['read'].insert(0, mail)
            except ValueError:
                yield from send_message(connection, "Specify a valid number.")
            except IndexError:
                index -= len(mailbox['unread'])
                try:
                    mail = mailbox['read'][index]
                except IndexError:
                    yield from send_message(connection, "No mail with that "
                                                        "number.")
                    return
            yield from send_message(connection, "From {} at {}: \n{}"
                                    .format(mail.author.alias,
                                            mail.time.strftime("%H:%M"),
                                            mail.message))
        else:
            if mailbox['unread']:
                for mail in mailbox['unread']:
                    mailbox['read'].insert(0, mail)
                    yield from send_message(connection, "From {} at {}: \n{}"
                                            .format(mail.author.alias,
                                                    mail.time.strftime("%H:%M"),
                                                    mail.message))
                mailbox['unread'] = []
            else:
                yield from send_message(connection, "No unread mail to "
                                                    "display.")

    @Command("listmail",
             perm="mail.readmail",
             doc="List all mail, optionally in a specified category.",
             syntax="[category]")
    def _listmail(self, data, connection):
        try:
            mailbox = self.storage['mail'][connection.player.uuid]
        except KeyError:
            self.storage['mail'][connection.player.uuid] = {"unread": [],
                                                            "read": []}
            mailbox = self.storage['mail'][connection.player.uuid]
        if data:
            if data[0] == "unread":
                count = 1
                for mail in mailbox['unread']:
                    yield from send_message(connection, "* {}: From {} at {}"
                                            .format(count, mail.author.alias,
                                                    mail.time.strftime(
                                                        "%H:%M")))
                    count += 1
                if count == 1:
                    yield from send_message(connection, "No unread mail in "
                                                        "mailbox.")
            elif data[0] == "read":
                count = len(mailbox['unread']) + 1
                for mail in mailbox['read']:
                    yield from send_message(connection, "{}: From {} at {}"
                                            .format(count, mail.author.alias,
                                                    mail.time.strftime(
                                                        "%H:%M")))
                    count += 1
                if count == len(mailbox['unread']) + 1:
                    yield from send_message(connection, "No read mail in "
                                                        "mailbox.")
            else:
                raise SyntaxWarning("Invalid category. Valid categories are "
                                    "\"read\" and \"unread\".")
        else:
            count = 1
            for mail in mailbox['unread']:
                yield from send_message(connection, "* {}: From {} at {}"
                                        .format(count, mail.author.alias,
                                                mail.time.strftime("%H:%M")))
                count += 1
            for mail in mailbox['read']:
                yield from send_message(connection, "{}: From {} at {}"
                                        .format(count, mail.author.alias,
                                                mail.time.strftime("%H:%M")))
                count += 1
            if count == 1:
                yield from send_message(connection, "No mail in mailbox.")

    @Command("delmail",
             perm="mail.readmail",
             doc="Delete unwanted mail, by index or category.",
             syntax="(index or category)")
    def _delmail(self, data, connection):
        uid = connection.player.uuid
        try:
            mailbox = self.storage['mail'][uid]
        except KeyError:
            self.storage['mail'][uid] = {"unread": [], "read": []}
            mailbox = self.storage['mail'][uid]
        if data:
            if data[0] == "all":
                self.storage['mail'][uid] = {"unread": [], "read": []}
                yield from send_message(connection, "Deleted all mail.")
            elif data[0] == "unread":
                self.storage['mail'][uid]['unread'] = []
                yield from send_message(connection, "Deleted all unread mail.")
            elif data[0] == "read":
                self.storage['mail'][uid]['read'] = []
                yield from send_message(connection, "Deleted all read mail.")
            else:
                try:
                    index = int(data[0]) - 1
                    self.storage['mail'][uid]['unread'].pop(index)
                    yield from send_message(connection, "Deleted mail {}."
                                            .format(data[0]))
                except ValueError:
                    raise SyntaxWarning("Argument must be a category or "
                                        "number. Valid categories: \"read\","
                                        " \"unread\", \"all\"")
                except IndexError:
                    # noinspection PyUnboundLocalVariable
                    index -= len(mailbox['unread'])
                    try:
                        self.storage['mail'][uid]['read'].pop(index)
                        yield from send_message(connection, "Deleted mail {}."
                                                .format(data[0]))
                    except IndexError:
                        yield from send_message(connection, "No message at "
                                                            "that index.")
        else:
            raise SyntaxWarning("No argument provided.")