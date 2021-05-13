# https://github.com/dinukasal/VoIPBot

import sys
import threading
import time
import pjsua as pj
from dotenv import dotenv_values

class Application:
    def __init__(self):
        self.current_call = None
        self.recorder_id = None
        self.player_id = None
        self.call_slot = None
        self.recorder_slot = None
        self.lib = pj.Lib()

    def run(self, domain, user, password):
        try:
            mediaconfig = pj.MediaConfig()
            mediaconfig.quality = 10
            self.lib.init(log_cfg=pj.LogConfig(level=4, callback=self.log_cb), media_cfg=mediaconfig)
            transport = self.lib.create_transport(pj.TransportType.UDP, pj.TransportConfig())
            self.lib.start()

            # Put your sIP client credentials here
            acc = self.lib.create_account(pj.AccountConfig(domain=domain, username=user, password=password))

            acc_cb = MyAccountCallback(app=self, account=acc)
            acc.set_callback(acc_cb)
            acc_cb.wait()

            print "\n"
            print "Registration complete, status=", acc.info().reg_status, \
                "(" + acc.info().reg_reason + ")"

            if len(sys.argv) > 1:
                lck = self.lib.auto_lock()

            my_sip_uri = "sip:" + transport.info().host + \
                         ":" + str(transport.info().port)

            # Menu loop
            while True:
                print "My SIP URI is", my_sip_uri
                print "Menu: h=hangup call, q=quit"

                input = sys.stdin.readline().rstrip("\r\n")

                if input == "h":
                    if not self.current_call:
                        print "There is no call"
                        continue
                    self.current_call.hangup()
                    self.reset_all()

                elif input == "q":
                    break

            # shutdown the library
            transport = None

            self.lib.destroy()
            self.lib = None

        except pj.Error, e:
            print "Exception: " + str(e)
            self.lib.destroy()
            lib = None
        pass

    def reset_all(self):
        self.current_call = None
        self.recorder_id = None
        self.player_id = None
        self.call_slot = None

    def is_line_busy(self):
        return self.current_call is not None

    def set_current_call(self, call):
        self.current_call = call

    def get_current_call(self):
        return self.current_call

    def get_call_slot(self):
        return self.call_slot

    def set_call_slot(self, slot):
        self.call_slot = slot

    def hangup(self):
        self.current_call.hangup()

    def log_cb(self, level, str, len):
        print str,

    def get_player_id(self):
        return self.player_id

    def set_player_id(self, id):
        self.player_id = id

    def play_wav(self, file):
        # Play wav file back to user
        self.player_id = self.lib.create_player(file, loop=False)
        player_slot = self.lib.player_get_slot(self.player_id)
        # Connect the audio player to the call
        self.lib.conf_connect(player_slot, self.call_slot)

    def start_record_wav(self, file):
        recorder_id = self.lib.create_recorder(file)
        self.recorder_slot = self.lib.recorder_get_slot(recorder_id)
        # Connect sound device to wav record file
        self.lib.conf_connect(0, self.recorder_slot)
        self.lib.conf_connect(self.call_slot, self.recorder_slot)
        return recorder_id

    def stop_record_wav(self, recorder_id):
        self.lib.recorder_destroy(recorder_id)

    def set_default_sound_device(self):
        self.lib.set_snd_dev(0, 0)

    def on_media_inactive(self):
        playerslot = self.lib.player_get_slot(self.player_id)
        self.lib.conf_disconnect(playerslot, 0)
        self.lib.conf_disconnect(0, self.recorder_slot)
        self.lib.conf_disconnect(self.call_slot, self.recorder_slot)


class MyAccountCallback(pj.AccountCallback):
    sem = None

    def __init__(self, app, account):
        self.app = app
        pj.AccountCallback.__init__(self, account)

    def wait(self):
        self.sem = threading.Semaphore(0)
        self.sem.acquire()

    def on_reg_state(self):
        if self.sem:
            if self.account.info().reg_status >= 200:
                self.sem.release()

    def on_incoming_call(self, call):
        if self.app.is_line_busy():
            call.answer(486, "Busy")
            return

        print "Incoming call from ", call.info().remote_uri
        self.app.set_current_call(call)
        current_call = self.app.get_current_call()
        call_cb = MyCallCallback(self.app, current_call)
        current_call.set_callback(call_cb)

        current_call.answer(180)
        # Hold ringing tone for 3 seconds
        time.sleep(3)
        current_call.answer(200)
        # Listen to user and respond
        self.listen_and_respond()

    def listen_and_respond(self):
        recorder_slot = self.app.start_record_wav("data/input1.wav")
        # Listen for 8 seconds, naive implementation
        time.sleep(8)
        self.app.stop_record_wav(recorder_slot)
        # Play wav file back to user
        self.app.play_wav("data/speech.wav")
        # Wait for the thing to be read for a few seconds then hang up
        time.sleep(23)
        self.app.hangup()


class MyCallCallback(pj.CallCallback):

    def __init__(self, app, call=None):
        self.app = app
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        current_call = self.app.get_current_call()
        print "Call with", self.call.info().remote_uri,
        print "is", self.call.info().state_text,
        print "last code = ", self.call.info().last_code,
        print "(" + self.call.info().last_reason + ")"

        if self.call.info().state == pj.CallState.DISCONNECTED:
            self.app.reset_all()
            print 'Current call is', current_call

    def on_media_state(self):
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # connect call to sound device
            call_slot = self.call.info().conf_slot
            pj.Lib.instance().conf_connect(call_slot, 0)
            pj.Lib.instance().conf_connect(0, call_slot)
            self.app.set_call_slot(call_slot)
            self.app.set_default_sound_device()
            print "Media is now active"

        else:
            self.app.on_media_inactive()
            print "Media is inactive"


def main():
    config = dotenv_values(".env")
    app = Application()
    app.run(str(config.get('SIP_DOMAIN')), str(config.get('SIP_USER')), str(config.get('SIP_USER_PASSWORD')))

if __name__ == "__main__":
    main()