from euphutils import EuphUtils
import euphoria as eu

import time
import re
import agentid_room
import longmessage_room

spam_threshold_messages = 10
spam_threshold_time = 5

class BotBotBot(eu.ping_room.PingRoom, eu.chat_room.ChatRoom, agentid_room.AgentIdRoom, longmessage_room.LongMessageRoom):
    def __init__(self, room_name, password, nickname, creator, code_struct, bots):
        super().__init__(room_name, password)

        self.bots = bots

        # Bot data
        self.code_struct = code_struct

        # Bot info
        self.agent_id = None
        self.room_name = room_name
        self.nickname = nickname
        self.creator = creator
        self.help_text = EuphUtils.mention(self.nickname) + ' is a bot created by "' + creator + '"' + ('using ' + EuphUtils.mention(bots.botbot.nickname) if self.bots.botbot else '') + '.\n\n@' + self.nickname + ' responds to !ping, !help @' + self.nickname + ', and the following regexes:\n' + ('\n'.join(self.code_struct.get_regexes()) if len(self.code_struct.get_regexes()) > 0 else '(None)') + '\n\nTo pause this bot, use the command "!pause ' + EuphUtils.mention(self.nickname) + '".\nTo kill this bot, use the command "!kill ' + EuphUtils.mention(self.nickname) + '".'

        # Bot state
        self.paused = False
        self.start_time = time.time()
        self.last_times = []

        # Bot state info
        self.pause_text = ''
        self.generic_pause_text = 'To restore this bot, type "!restore ' + EuphUtils.mention(self.nickname) + '", or to kill this bot, type "!kill ' + EuphUtils.mention(self.nickname) + '".'

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

    def recv_message(self, content='', parent=None, this_message=None, sender='', sender_agent_id='', send_time=0, room_name=''):
        if EuphUtils.command('!kill', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            self.kill(msg_id=this_message)
        elif self.paused and EuphUtils.command('!restore', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            self.send_chat('/me is now restored.', this_message)
            self.paused = False
            self.start_time = time.time()
            self.pause_text = ''
        elif EuphUtils.command('!pause', self.nickname).match(content):
            if self.bots.is_bot(sender_agent_id):
                return
            if self.paused:
                self.send_chat('/me is already paused.', this_message)
                self.send_chat(self.generic_pause_text, this_message)
            else:
                self.paused = True
                self.pause_text = '/me has been paused by "' + sender + '".'
                self.send_chat(self.pause_text, this_message)
                self.send_chat(self.generic_pause_text, this_message)
        elif self.paused and EuphUtils.command('!help', self.nickname).match(content):
            self.send_chat(self.pause_text, this_message)
            self.send_chat(self.generic_pause_text, this_message)
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
                        self.paused = True
                        self.pause_text = '/me has been temporarily halted due to a possible spam attack being generated by this bot.'
                        self.send_chat(self.pause_text, this_message)
                        self.send_chat(self.generic_pause_text, this_message)
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

    def kill(self, announce=True, msg_id=None):
        if announce:
            self.send_chat('/me is now exiting.', msg_id)
        self.bots.remove(self)
        self.quit()
