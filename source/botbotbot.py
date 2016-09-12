from botbot.euphutils import EuphUtils
from botbot.snapshot import Snapshot
import botbot.agentid_room as agentid_room
import botbot.longmessage_room as longmessage_room
import euphoria as eu

import time
import re
import uuid as uuid_module
import errno
import os

spam_threshold_messages = 10
spam_threshold_time = 5

class BotBotBot(eu.ping_room.PingRoom, eu.chat_room.ChatRoom, eu.nick_room.NickRoom, agentid_room.AgentIdRoom, longmessage_room.LongMessageRoom):
    def __init__(self, room_name, password, nickname, creator, code_struct, bots, paused=False, pause_text='', uuid=None):
        super().__init__(room_name, password)

        self.bots = bots

        # Bot data
        self.code_struct = code_struct

        # Bot info
        self.uuid = uuid or str(uuid_module.uuid4())
        self.filename = os.path.join(Snapshot.snapshot_dir, 'current', self.uuid + '.json')
        self.agent_id = None
        self.room_name = room_name
        self.password = password
        self.nickname = nickname
        self.creator = creator
        self.help_text = EuphUtils.mention(self.nickname) + ' is a bot created by "' + creator + '"' + (' using ' + EuphUtils.mention(bots.botbot.nickname) if self.bots.botbot else '') + '.\n\n@' + self.nickname + ' responds to !ping, !help @' + self.nickname + ', and the following regexes:\n' + ('\n'.join(self.code_struct.get_regexes()) if len(self.code_struct.get_regexes()) > 0 else '(None)') + '\n\nTo pause this bot, use the command "!pause ' + EuphUtils.mention(self.nickname) + '".\nTo kill this bot, use the command "!kill ' + EuphUtils.mention(self.nickname) + '".'

        # Bot state
        self.paused = paused
        self.start_time = time.time()
        self.last_times = []

        # Bot state info
        self.pause_text = pause_text
        self.generic_pause_text = 'To restore this bot, type "!restore ' + EuphUtils.mention(self.nickname) + '", or to kill this bot, type "!kill ' + EuphUtils.mention(self.nickname) + '".'

        self.write_to_file()

    def write_to_file(self):
        if Snapshot.is_enabled():
            try:
                os.makedirs(os.path.join(Snapshot.snapshot_dir, 'current'))
            except OSError as err:
                if err.errno != errno.EEXIST or not os.path.isdir(Snapshot.snapshot_dir):
                    traceback.print_exc()
            try:
                with open(self.filename, 'w') as f:
                    f.write(Snapshot.pack_bot(self))
                return True
            except OSError:
                traceback.print_exc()
        return False

    def handle_chat(self, message):
        if message.get('truncated'):
            return
        if message['sender']['id'] == self.agent_id:
            return
        if self.bots.botbot and message['sender']['id'] == self.bots.botbot.agent_id:
            return

        if 'parent' in message:
            self.recv_message(message['content'], message['parent'], message['id'], message['sender']['name'], message['sender']['id'], message['time'], self.room_name)
        else:
            self.recv_message(message['content'], None, message['id'], message['sender']['name'], message['sender']['id'], message['time'], self.room_name)

    def pause(self, pause_text=None, set_pause_text=True, reply_to=None):
        changed = False
        if not self.paused:
            self.paused = True
            changed = True
        if set_pause_text and pause_text and self.pause_text != pause_text:
            self.pause_text = pause_text
            changed = True
        elif not pause_text:
            # pause_text will be sent as a message later, so load the pause_text
            # from the instance variable
            pause_text = self.pause_text
        if changed:
            self.write_to_file()
        self.send_chat(pause_text, reply_to)
        self.send_chat(self.generic_pause_text, reply_to)

    def restore(self, reply_to=None):
        changed = False
        if self.paused:
            self.paused = False
            changed = True
        if self.pause_text != '':
            self.pause_text = ''
            changed = True
        self.start_time = time.time()
        self.send_chat('/me is now restored.', reply_to)
        if changed:
            self.write_to_file()

    def recv_message(self, content='', parent=None, this_message=None, sender='', sender_agent_id='', send_time=0, room_name=''):
        if EuphUtils.command('!kill', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            self.kill(msg_id=this_message)
        elif self.paused and EuphUtils.command('!restore', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            self.restore(this_message)
        elif EuphUtils.command('!pause', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            if self.paused:
                self.pause(pause_text='/me is already paused.', set_pause_text=False, reply_to=this_message)
            else:
                self.pause(pause_text='/me has been paused by "' + sender + '".', reply_to=this_message)
        elif self.paused and EuphUtils.command('!help', self.nickname).match(content):
            self.pause(reply_to=this_message)
        elif content == "!antighost":
            #just reset the nick to the same thing it already is
            self.change_nick(nickname)
        else:
            if not self.paused:
                messages = self.code_struct.get_messages(content, sender)
            else:
                messages = []
            if len(messages) > 0:
                self.last_times.append(time.time())
                while len(self.last_times) > spam_threshold_messages:
                    del self.last_times[0]
                if not self.paused and len(self.last_times) == spam_threshold_messages:
                    if self.last_times[-1] - self.last_times[0] <= spam_threshold_time:
                        # Spam detected!
                        self.pause(pause_text='/me has been temporarily halted due to a possible spam attack being generated by this bot.', reply_to=this_message)
                        return
                while len(self.last_times) > spam_threshold_messages - 1:
                    del self.last_times[0]
                for raw_message in messages:
                    message = raw_message
                    # This is probably how user variables will be implemented, too.
                    variables = {
                        'sender': sender,
                        '@sender': EuphUtils.mention(sender),
                        'room': room_name,
                        'uptimeutc': EuphUtils.uptime_utc(self.start_time),
                        'uptime': EuphUtils.uptime_dhms(self.start_time)
                    }
                    for i, j in variables.items():
                        message = message.replace('(' + i + ')', j)
                    if EuphUtils.command('!ping', '').match(message):
                        continue
                    match = re.match(r'!to\s+@(\S+)(?:\s+&(\S+))?\s+(.*)', message, re.IGNORECASE + re.DOTALL)
                    if match:
                        self.bots.interbot(match.group(1), match.group(2).lower() if match.group(2) else None, match.group(3), sender, sender_agent_id, send_time, room_name)
                        continue
                    match = re.match(r'!nick\s+(.*)', message, re.IGNORECASE + re.DOTALL)
                    if match:
                        self.change_nick(match.group(1))
                        continue
                    match = re.match(r'!break\b', message, re.IGNORECASE + re.DOTALL)
                    if match:
                        break
                    if len(message) == 0:
                        continue
                    self.send_chat(message, this_message)
            elif content.startswith('!'):
                if EuphUtils.command('ping', '').match(content[1:]):
                    self.send_chat('Pong!', this_message)
                elif EuphUtils.command('ping', self.nickname).match(content[1:]):
                    self.send_chat('Pong!', this_message)
                elif EuphUtils.command('help', self.nickname).match(content[1:]):
                    self.send_chat(self.help_text, this_message)
                elif EuphUtils.command('uptime', self.nickname).match(content[1:]):
                    if not self.paused:
                        self.send_chat(EuphUtils.uptime_str(self.start_time), this_message)
                    else:
                        self.send_chat('/me is paused, so it currently has no uptime.', this_message)

    def handle_nickreply(self, data):
        previous_nickname = self.nickname
        super().handle_nickreply(data)
        if self.nickname != previous_nickname:
            self.write_to_file()

    def kill(self, announce=True, msg_id=None, delete_file=True):
        if announce:
            self.send_chat('/me is now exiting.', msg_id)
        self.bots.remove(self)
        if delete_file and Snapshot.is_enabled():
            try:
                os.unlink(self.filename)
            except OSError:
                traceback.print_exc()
        self.quit()
